from dataclasses import field
from datetime import datetime
from html.parser import HTMLParser as BaseHTMLParser
import io
from pathlib import Path
import pickle
import platform
import uuid

from PIL import Image as PILImage
from django.core.files import File as DjangoFile
from django.template.loader import render_to_string
from django.utils import timezone
import numpy

from ..adr_utils import table_attr
from ..exceptions import ADRException
from ..utils import report_utils
from ..utils.geofile_processing import file_is_3d_geometry, get_avz_directory, rebuild_3d_geometry
from ..utils.report_utils import is_enhanced
from .base import BaseModel, StrEnum, Validator


class Session(BaseModel):
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    hostname: str = field(compare=False, kw_only=True, default=str(platform.node()))
    platform: str = field(compare=False, kw_only=True, default=str(report_utils.enve_arch()))
    application: str = field(compare=False, kw_only=True, default="Serverless ADR Python API")
    version: str = field(compare=False, kw_only=True, default="1.0")
    _orm_model: str = "data.models.Session"


class Dataset(BaseModel):
    filename: str = field(compare=False, kw_only=True, default="none")
    dirname: str = field(compare=False, kw_only=True, default="")
    format: str = field(compare=False, kw_only=True, default="none")
    numparts: int = field(compare=False, kw_only=True, default=0)
    numelements: int = field(compare=False, kw_only=True, default=0)
    _orm_model: str = "data.models.Dataset"


class HTMLParser(BaseHTMLParser):
    def __init__(self):
        super().__init__()
        self._start_tags = []

    def handle_starttag(self, tag, attrs):
        self._start_tags.append(tag)

    def validate(self, string):
        self.feed(string)
        for tag in self._start_tags:
            if tag:
                return True
        return False

    def reset(self):
        super().reset()
        self._start_tags = []


class ItemContent(Validator):
    def process(self, value, obj):
        if value is None:
            raise ValueError("Content cannot be None")
        return value


class StringContent(ItemContent):
    def process(self, value, obj):
        value = super().process(value, obj)
        if not isinstance(value, str):
            raise TypeError("Expected content to be a string")
        return value


class HTMLContent(StringContent):
    def process(self, value, obj):
        html_str = super().process(value, obj)
        if not HTMLParser().validate(html_str):
            raise ValueError("Expected content to contain valid HTML")
        return html_str


class TableContent(ItemContent):
    def process(self, value, obj):
        value = super().process(value, obj)
        if not isinstance(value, numpy.ndarray):
            raise TypeError("Expected content to be a numpy array")
        if value.dtype.kind not in ("S", "f"):
            raise TypeError("Expected content to be a numpy array of bytes or float type.")
        if len(value.shape) != 2:
            raise ValueError("Expected content to be a 2 dimensional numpy array.")
        return value


class TreeContent(ItemContent):
    ALLOWED_VALUE_TYPES = (float, int, datetime, str, bool, uuid.UUID, type(None))

    def _validate_tree_value(self, value):
        # if it's a list of values, validate them recursively.
        if isinstance(value, list):
            for v in value:
                self._validate_tree_value(v)
        else:
            type_ = type(value)
            if type_ not in self.ALLOWED_VALUE_TYPES:
                raise ValueError(f"{str(type_)} is not a valid 'value' type in a tree")

    def _validate_tree(self, tree):
        if not isinstance(tree, list):
            raise ValueError("The tree content must be a list of dictionaries")
        for elem in tree:
            if not isinstance(elem, dict):
                raise ValueError("The tree content must be a list of dictionaries")
            if "key" not in elem:
                raise ValueError("Tree content dictionaries must have a 'key' key")
            if "name" not in elem:
                raise ValueError("Tree content dictionaries must have a 'name' key")
            if "value" not in elem:
                raise ValueError("Tree content dictionaries must have a 'value' key")
            if "children" in elem:
                self._validate_tree(elem["children"])
            # validate tree value
            self._validate_tree_value(elem["value"])

    def process(self, value, obj):
        value = super().process(value, obj)
        self._validate_tree(value)
        return value


class FileValidator(StringContent):
    ALLOWED_EXT = None

    def process(self, value, obj):
        file_str = super().process(value, obj)
        file_path = Path(file_str)
        if not file_path.is_file():
            raise ValueError(
                f"Expected content to be a file path: "
                f"'{file_path}' does not exist or is not a file."
            )
        with file_path.open(mode="rb") as f:
            file = DjangoFile(f)
        # check file type
        file_ext = Path(file.name).suffix.lower().lstrip(".")
        if self.ALLOWED_EXT is not None and file_ext not in self.ALLOWED_EXT:
            raise ValueError(f"File type {file_ext} is not supported by {obj.__class__}")
        # check for empty files
        if file.size == 0:
            raise ValueError("The file specified is empty")
        # save a ref on the object.
        obj._file = file
        obj._file_ext = file_ext
        return file_str


class ImageContent(FileValidator):
    ENHANCED_EXT = ("tif", "tiff")
    ALLOWED_EXT = ("png", "jpg") + ENHANCED_EXT

    def process(self, value, obj):
        file_str = super().process(value, obj)
        with obj._file.open(mode="rb") as f:
            img_bytes = f.read()
        image = PILImage.open(io.BytesIO(img_bytes))
        if obj._file_ext in self.ENHANCED_EXT:
            metadata = is_enhanced(image)
            if not metadata:
                raise ADRException("The enhanced image is empty")
            obj._enhanced = True
        obj._width, obj._height = image.size
        image.close()
        return file_str


class AnimContent(FileValidator):
    ALLOWED_EXT = ("mp4",)


class SceneContent(FileValidator):
    ALLOWED_EXT = ("stl", "ply", "csf", "avz", "scdoc", "scdocx", "dsco", "glb", "obj")


class FileContent(FileValidator):
    ALLOWED_EXT = None


class SimplePayloadMixin:
    @classmethod
    def from_db(cls, orm_instance, **kwargs):
        from data.extremely_ugly_hacks import safe_unpickle

        obj = super().from_db(orm_instance, **kwargs)
        obj.content = safe_unpickle(obj._orm_instance.payloaddata)
        return obj

    def save(self, **kwargs):
        self._orm_instance.payloaddata = pickle.dumps(self.content, protocol=0)
        super().save(**kwargs)


class FilePayloadMixin:
    _file: DjangoFile = field(init=False, compare=False, default=None)
    _file_ext: str = field(init=False, compare=False, default="")

    @property
    def file_path(self):
        try:
            return self._orm_instance.payloadfile.path
        except (AttributeError, ValueError):
            # If the file path is not set, return None
            return None

    @property
    def has_file(self):
        return self.file_path is not None and Path(self.file_path).is_file()

    @property
    def file_ext(self):
        try:
            return Path(self._orm_instance.payloadfile.path).suffix.lower().lstrip(".")
        except (AttributeError, ValueError):
            # If the file path is not set, return None
            return None

    @classmethod
    def from_db(cls, orm_instance, **kwargs):
        obj = super().from_db(orm_instance, **kwargs)
        obj.content = obj._orm_instance.payloadfile.path
        return obj

    @staticmethod
    def _save_file(target_path, content):
        if Path(target_path).is_file():
            return
        with open(target_path, "wb") as out_file:
            if isinstance(content, bytes):
                out_file.write(content)
            else:
                with content.open(mode="rb") as f:
                    for chunk in f.chunks():
                        out_file.write(chunk)

    def save(self, **kwargs):
        self._orm_instance.payloadfile = f"{self.guid}_{self.type}.{self._file_ext}"
        # Save file to the target path
        self._save_file(self.file_path, self._file)
        # save ORM instance
        super().save(**kwargs)

    def delete(self, **kwargs):
        from data.utils import delete_item_media

        delete_item_media(self._orm_instance.guid)
        return super().delete(**kwargs)


class ItemType(StrEnum):
    STRING = "string"
    HTML = "html"
    TABLE = "table"
    TREE = "tree"
    IMAGE = "image"
    ANIMATION = "anim"
    SCENE = "scene"
    FILE = "file"
    NONE = "none"


class Item(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    source: str = field(compare=False, kw_only=True, default="")
    sequence: int = field(compare=False, kw_only=True, default=0)
    session: Session = field(compare=False, kw_only=True, default=None)
    dataset: Dataset = field(compare=False, kw_only=True, default=None)
    content: ItemContent = ItemContent()
    type: str = ItemType.NONE  # todo: make this read-only
    _orm_model: str = "data.models.Item"
    _type_registry = {}  # Class-level registry of subclasses keyed by type
    _in_memory: bool = field(compare=False, kw_only=True, default=False)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically register the subclass based on its type attribute
        Item._type_registry[cls.type] = cls

    def __post_init__(self):
        if self.__class__ is Item:
            raise ADRException("Cannot instantiate Item directly. Use the Item.create() method.")
        super().__post_init__()

    def save(self, **kwargs):
        if self.session is None or self.dataset is None:
            raise ADRException(extra_detail="A session and a dataset are required to save an item")
        if not self.session.saved:
            raise Session.NotSaved(
                extra_detail="Failed to save item because the session is not saved"
            )
        if not self.dataset.saved:
            raise Dataset.NotSaved(
                extra_detail="Failed to save item because the dataset is not saved"
            )
        super().save(**kwargs)

    @classmethod
    def from_db(cls, orm_instance, **kwargs):
        # Create a new instance of the correct subclass
        if cls is Item:
            # Get the class based on the type attribute
            item_cls = cls._type_registry[orm_instance.type]
            return item_cls.from_db(orm_instance, **kwargs)

        return super().from_db(orm_instance, **kwargs)

    @classmethod
    def create(cls, **kwargs):
        # Create a new instance of the correct subclass
        if cls is Item:
            # Get the class based on the type attribute
            try:
                item_cls = cls._type_registry[kwargs.pop("type")]
            except KeyError:
                raise ADRException("The 'type' must be passed when using the Item class")
            return item_cls.create(**kwargs)

        new_kwargs = {"type": cls.type, **kwargs}
        return super().create(**new_kwargs)

    @classmethod
    def _validate_kwargs(cls, **kwargs):
        if "content" in kwargs:
            raise ValueError("'content' kwarg is not supported for get and filter methods")
        return {"type": cls.type, **kwargs} if cls.type != "none" else kwargs

    @classmethod
    def get(cls, **kwargs):
        return super().get(**cls._validate_kwargs(**kwargs))

    @classmethod
    def filter(cls, **kwargs):
        return super().filter(**cls._validate_kwargs(**kwargs))

    @classmethod
    def find(cls, query="", **kwargs):
        if cls is Item:
            return super().find(query=query, **kwargs)
        if "i_type|" in query:
            raise ADRException(
                extra_detail="The 'i_type' filter is not allowed if using a subclass of Item"
            )
        return super().find(query=f"A|i_type|cont|{cls.type};{query}", **kwargs)  # noqa: E702

    def render(self, *, context=None, request=None) -> str | None:
        if context is None:
            context = {}
        ctx = {
            "request": request,
            "ansys_version": None,
            "plotly": int(context.get("plotly", 0)),  # default referenced in the header via static
            "format": context.get("format", None),
        }
        try:
            ctx["HTML"] = self._orm_instance.render(ctx)
        except Exception as e:
            from ceireports.utils import get_render_error_html

            ctx["HTML"] = get_render_error_html(e, target="report item", guid=self.guid)

        return render_to_string("data/item_detail_simple.html", context=ctx, request=request)


class String(SimplePayloadMixin, Item):
    content: StringContent = StringContent()
    type: str = ItemType.STRING


class HTML(String):
    content: HTMLContent = HTMLContent()
    type: str = ItemType.HTML


class Table(Item):
    content: TableContent = TableContent()
    type: str = ItemType.TABLE
    _payload_properties: tuple = (  # for backwards compatibility
        "rowlbls",
        "collbls",
    )
    _properties: tuple = table_attr + _payload_properties

    @classmethod
    def from_db(cls, orm_instance, **kwargs):
        from data.extremely_ugly_hacks import safe_unpickle

        obj = super().from_db(orm_instance, **kwargs)
        payload = safe_unpickle(obj._orm_instance.payloaddata)
        obj.content = payload.pop("array", None)
        for prop in cls._properties:
            if prop in payload:
                setattr(obj, prop, payload[prop])
        return obj

    def save(self, **kwargs):
        payload = {
            "array": self.content,
        }
        for prop in self.__class__._properties:
            value = getattr(self, prop, None)
            if value is not None:
                payload[prop] = value
        self._orm_instance.payloaddata = pickle.dumps(payload, protocol=0)
        super().save(**kwargs)


class Tree(SimplePayloadMixin, Item):
    content: TreeContent = TreeContent()
    type: str = ItemType.TREE


class Image(FilePayloadMixin, Item):
    _width: int = field(compare=False, init=False, default=0)
    _height: int = field(compare=False, init=False, default=0)
    _enhanced: bool = field(compare=False, init=False, default=False)
    content: ImageContent = ImageContent()
    type: str = ItemType.IMAGE

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def enhanced(self):
        return self._enhanced

    def save(self, **kwargs):
        with self._file.open(mode="rb") as f:
            img_bytes = f.read()
        image = PILImage.open(io.BytesIO(img_bytes))
        # Determine final file name and format
        target_ext = "png" if not self._enhanced else self._file_ext
        self._orm_instance.payloadfile = f"{self.guid}_image.{target_ext}"
        # Save the image
        if self._file_ext != target_ext and target_ext == "png":
            # Convert to PNG format
            self._file_ext = target_ext
            try:
                image.save(self.file_path, format=self._file_ext.upper())
            except OSError as e:
                raise ADRException(f"Error converting image to {self._file_ext}: {e}") from e
        else:  # save image as is (if enhanced or already PNG)
            self._save_file(self.file_path, img_bytes)
        image.close()
        super().save(**kwargs)


class Animation(FilePayloadMixin, Item):
    content: AnimContent = AnimContent()
    type: str = ItemType.ANIMATION


class Scene(FilePayloadMixin, Item):
    content: SceneContent = SceneContent()
    type: str = ItemType.SCENE

    def save(self, **kwargs):
        super().save(**kwargs)
        if not Path(get_avz_directory(self.file_path)).exists():
            rebuild_3d_geometry(self.file_path)


class File(FilePayloadMixin, Item):
    content: FileContent = FileContent()
    type: str = ItemType.FILE

    def save(self, **kwargs):
        super().save(**kwargs)
        if (
            file_is_3d_geometry(self.file_path)
            and not Path(get_avz_directory(self.file_path)).exists()
        ):
            rebuild_3d_geometry(self.file_path)
