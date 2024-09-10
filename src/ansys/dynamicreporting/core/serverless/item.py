from dataclasses import field
from datetime import datetime
from html.parser import HTMLParser as BaseHTMLParser
import io
from pathlib import Path
import pickle
import platform
from typing import Optional
import uuid

from PIL import Image as PILImage
from django.core.files import File as DjangoFile
from django.template.loader import render_to_string
from django.utils import timezone
import numpy

from ..adr_utils import table_attr
from ..exceptions import ADRException
from ..utils import report_utils
from ..utils.geofile_processing import file_is_3d_geometry, rebuild_3d_geometry
from .base import BaseModel, Validator


class Session(BaseModel):
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    hostname: str = field(compare=False, kw_only=True, default=str(platform.node))
    platform: str = field(compare=False, kw_only=True, default=str(report_utils.enve_arch))
    application: str = field(compare=False, kw_only=True, default="Python API")
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


class StringContent(Validator):
    def process(self, value, obj):
        if not isinstance(value, str):
            raise TypeError("Expected content to be a string")
        return value


class HTMLContent(StringContent):
    def process(self, value, obj):
        html_str = super().process(value, obj)
        if not HTMLParser().validate(html_str):
            raise ValueError("Expected content to contain valid HTML")
        return html_str


class TableContent(Validator):
    def process(self, value, obj):
        if not isinstance(value, numpy.ndarray):
            raise TypeError("Expected content to be a numpy array")
        if value.dtype.kind not in ["S", "f"]:
            raise TypeError("Expected content to be a numpy array of bytes or float type.")
        if len(value.shape) != 2:
            raise ValueError("Expected content to be a 2 dimensional numpy array.")
        return value


class TreeContent(Validator):
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
        self._validate_tree(value)
        return value


class FileValidator(StringContent):
    ALLOWED_EXT = None

    def process(self, value, obj):
        file_str = super().process(value, obj)
        file_path = Path(file_str)
        if not file_path.is_file():
            raise ValueError("Expected content to be a file path")

        file = DjangoFile(file_path.open(mode="rb"))

        # check file type
        file_ext = Path(file.name).suffix.lower()
        if self.ALLOWED_EXT is not None and file_ext.replace(".", "") not in self.ALLOWED_EXT:
            raise ValueError(f"File type {file_ext} is not supported by {obj.__class__}")
        # check for empty files
        if file.size == 0:
            raise ValueError("The file specified is empty")

        # save a ref on the object.
        setattr(obj, "_file", file)
        return file_str


class ImageContent(FileValidator):
    ALLOWED_EXT = ("png", "jpg", "tif", "tiff")

    def process(self, value, obj):
        file_str = super().process(value, obj)
        file_ext = Path(obj._file.name).suffix.lower()
        img_bytes = obj._file.read()
        image = PILImage.open(io.BytesIO(img_bytes))
        if file_ext in (".tif", ".tiff"):
            metadata = report_utils.is_enhanced(image)
            if not metadata:
                raise ADRException("The enhanced image is empty")
        obj._width, obj._height = image.size
        return file_str


class AnimContent(FileValidator):
    ALLOWED_EXT = ("mp4",)


class SceneContent(FileValidator):
    ALLOWED_EXT = ("stl", "ply", "csf", "avz", "scdoc", "glb")


class FileContent(FileValidator):
    ALLOWED_EXT = None


class SimplePayloadMixin:
    @classmethod
    def serialize_from_orm(cls, orm_instance):
        from data.extremely_ugly_hacks import safe_unpickle

        obj = super().serialize_from_orm(orm_instance)
        obj.content = safe_unpickle(obj._orm_instance.payloaddata)
        return obj

    def save(self, **kwargs):
        self._orm_instance.payloaddata = pickle.dumps(self.content, protocol=0)
        super().save(**kwargs)


class FilePayloadMixin:
    _file: DjangoFile = field(init=False, compare=False, default=None)

    @classmethod
    def serialize_from_orm(cls, orm_instance):
        obj = super().serialize_from_orm(orm_instance)
        obj.content = obj._orm_instance.payloadfile.path
        return obj

    def save(self, **kwargs):
        file_name = Path(self._file.name).name
        self._orm_instance.payloadfile = f"{str(self.guid)}_{file_name}"
        # more general path, save the file into the media directory
        with open(self._orm_instance.get_payload_server_pathname(), "wb") as out_file:
            for chunk in self._file.chunks():
                out_file.write(chunk)  # chunk -> bytes
        super().save(**kwargs)


class Item(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    source: str = field(compare=False, kw_only=True, default="")
    sequence: int = field(compare=False, kw_only=True, default=0)
    session: Session = field(compare=False, kw_only=True, default=None)
    dataset: Dataset = field(compare=False, kw_only=True, default=None)
    type: str = "none"
    _orm_model: str = "data.models.Item"

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
        if self.content is None:
            raise ADRException(extra_detail=f"The item {self.guid} must have some content to save")
        super().save(**kwargs)

    def delete(self, **kwargs):
        from data.utils import delete_item_media

        delete_item_media(self._orm_instance.guid)
        return super().delete(**kwargs)

    @classmethod
    def get(cls, **kwargs):
        new_kwargs = {"type": cls.type, **kwargs} if cls.type != "none" else kwargs
        return super().get(**new_kwargs)

    @classmethod
    def filter(cls, **kwargs):
        new_kwargs = {"type": cls.type, **kwargs} if cls.type != "none" else kwargs
        return super().filter(**new_kwargs)

    @classmethod
    def find(cls, **kwargs):
        if cls.type == "none":
            return super().find(**kwargs)
        query = kwargs.pop("query", "")
        if "i_type|cont" in query:
            raise ADRException(
                extra_detail="The 'i_type' filter is not required if using a subclass of Item"
            )
        new_kwargs = {**kwargs, "query": f"A|i_type|cont|{cls.type};{query}"}
        return super().find(**new_kwargs)

    def render(self, context=None, request=None) -> Optional[str]:
        if context is None:
            context = {}
        ctx = {**context, "request": request, "ansys_version": None}
        try:
            ctx["HTML"] = self._orm_instance.render(ctx)
        except Exception as e:
            from ceireports.utils import get_render_error_html

            ctx["HTML"] = get_render_error_html(e, target="report item", guid=self.guid)

        return render_to_string("data/item_detail_simple.html", context=ctx, request=request)


class String(SimplePayloadMixin, Item):
    content: StringContent = StringContent()
    type: str = "string"


class Text(String):
    pass


class HTML(String):
    content: HTMLContent = HTMLContent()
    type: str = "html"


class Table(Item):
    content: TableContent = TableContent()
    type: str = "table"
    _properties: tuple = table_attr

    @classmethod
    def serialize_from_orm(cls, orm_instance):
        from data.extremely_ugly_hacks import safe_unpickle

        obj = super().serialize_from_orm(orm_instance)
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
        for prop in self._properties:
            value = getattr(self, prop, None)
            if value is not None:
                payload[prop] = value
        self._orm_instance.payloaddata = pickle.dumps(payload, protocol=0)
        super().save(**kwargs)


class Plot(Table):
    pass


class Tree(SimplePayloadMixin, Item):
    content: TreeContent = TreeContent()
    type: str = "tree"


class Image(FilePayloadMixin, Item):
    _width: int = field(compare=False, init=False, default=0)
    _height: int = field(compare=False, init=False, default=0)
    content: ImageContent = ImageContent()
    type: str = "image"

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height


class Animation(FilePayloadMixin, Item):
    content: AnimContent = AnimContent()
    type: str = "anim"


class Movie(Animation):
    pass


class Scene(FilePayloadMixin, Item):
    content: SceneContent = SceneContent()
    type: str = "scene"

    def save(self, **kwargs):
        super().save(**kwargs)
        rebuild_3d_geometry(
            self._orm_instance.get_payload_server_pathname(),
            self._orm_instance.get_unique_id(),
            exec_basis="",
        )


class File(FilePayloadMixin, Item):
    content: FileContent = FileContent()
    type: str = "file"

    def save(self, **kwargs):
        super().save(**kwargs)
        file_name = Path(self._file.name).name
        if file_is_3d_geometry(file_name):
            rebuild_3d_geometry(
                self._orm_instance.get_payload_server_pathname(),
                self._orm_instance.get_unique_id(),
                exec_basis="",
            )
