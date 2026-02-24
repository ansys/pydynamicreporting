# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Serverless ADR item models and content validators.

This module defines the high-level objects that are persisted and rendered by
the serverless ADR API:

* :class:`Session` – execution context for a reporting run.
* :class:`Dataset` – input dataset metadata.
* :class:`Item` and its subclasses – persisted payloads such as strings,
  HTML fragments, tables, trees, images, animations, scenes, and generic files.
* Content validators – descriptors that enforce type- and shape-correct
  payloads (for example :class:`TableContent`, :class:`TreeContent`).
* Payload mixins – helpers for storing content either as pickled blobs or
  as files in the media storage.
"""

from dataclasses import field
from datetime import datetime
from html.parser import HTMLParser as BaseHTMLParser
import io
from pathlib import Path
import pickle  # nosec B403
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
    """Execution context for a reporting run.

    A :class:`Session` captures environment information for a single ADR
    execution, such as host name, platform, and application version. It is
    referenced by :class:`Item` instances to group related content.
    """

    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    """Session creation timestamp, defaulting to the current time."""

    hostname: str = field(compare=False, kw_only=True, default=str(platform.node()))
    """Hostname where the session was created."""

    platform: str = field(
        compare=False,
        kw_only=True,
        default=str(report_utils.enve_arch()),
    )
    """Platform/architecture identifier (for example ``"win64"``)."""

    application: str = field(
        compare=False,
        kw_only=True,
        default="Serverless ADR Python API",
    )
    """Application name that produced the session."""

    version: str = field(compare=False, kw_only=True, default="1.0")
    """Application version string."""

    _orm_model: str = "data.models.Session"


class Dataset(BaseModel):
    """Metadata describing a source dataset used for reporting."""

    filename: str = field(compare=False, kw_only=True, default="none")
    """Dataset file name (without directory)."""

    dirname: str = field(compare=False, kw_only=True, default="")
    """Directory containing the dataset."""

    format: str = field(compare=False, kw_only=True, default="none")
    """Dataset format identifier (for example ``"hdf5"``)."""

    numparts: int = field(compare=False, kw_only=True, default=0)
    """Number of parts in the dataset."""

    numelements: int = field(compare=False, kw_only=True, default=0)
    """Number of elements (for example rows or mesh elements) in the dataset."""

    _orm_model: str = "data.models.Dataset"


class HTMLParser(BaseHTMLParser):
    """Minimal HTML parser used to validate HTML content.

    The parser records all encountered start tags and exposes a
    :meth:`validate` utility that returns ``True`` if at least one tag
    has been seen.
    """

    def __init__(self):
        """Initialize an empty parser state."""
        super().__init__()
        self._start_tags = []

    def handle_starttag(self, tag, attrs):
        """Record each start tag encountered during parsing."""
        self._start_tags.append(tag)

    def validate(self, string):
        """Return ``True`` if the input string contains at least one tag."""
        self.feed(string)
        for tag in self._start_tags:
            if tag:
                return True
        return False

    def reset(self):
        """Reset the parser state and clear any recorded tags."""
        super().reset()
        self._start_tags = []


class ItemContent(Validator):
    """Base validator for item payloads.

    This descriptor ensures that ``None`` is never accepted as content; all
    concrete subclasses perform additional type- or shape-specific checks.
    """

    def process(self, value, obj):
        """Validate that content is not ``None``."""
        if value is None:
            raise ValueError("Content cannot be None")
        return value


class StringContent(ItemContent):
    """Validator for string-based item content."""

    def process(self, value, obj):
        """Validate that content is a string."""
        value = super().process(value, obj)
        if not isinstance(value, str):
            raise TypeError("Expected content to be a string")
        return value


class HTMLContent(StringContent):
    """Validator for simple HTML fragments."""

    def process(self, value, obj):
        """Validate that content is a non-empty HTML fragment."""
        html_str = super().process(value, obj)
        if not HTMLParser().validate(html_str):
            raise ValueError("Expected content to contain valid HTML")
        return html_str


class TableContent(ItemContent):
    """Validator for 2D table payloads backed by NumPy arrays."""

    def process(self, value, obj):
        """Validate a 2D :class:`numpy.ndarray` table."""
        value = super().process(value, obj)
        if not isinstance(value, numpy.ndarray):
            raise TypeError("Expected content to be a numpy array")
        if value.dtype.kind not in ("S", "f"):
            raise TypeError("Expected content to be a numpy array of bytes or float type.")
        if len(value.shape) != 2:
            raise ValueError("Expected content to be a 2 dimensional numpy array.")
        return value


class TreeContent(ItemContent):
    """Validator for hierarchical tree payloads.

    A tree is represented as a list of dictionaries with the following keys:

    * ``"key"`` – unique identifier for the node.
    * ``"name"`` – human-readable label.
    * ``"value"`` – scalar value or list of scalar values.
    * ``"children"`` – optional list of child node dictionaries.

    Only a limited set of scalar value types is allowed for ``"value"``.
    """

    ALLOWED_VALUE_TYPES = (float, int, datetime, str, bool, uuid.UUID, type(None))

    def _validate_tree_value(self, value):
        """Validate a single tree value or a list of values."""
        # if it's a list of values, validate them recursively.
        if isinstance(value, list):
            for v in value:
                self._validate_tree_value(v)
        else:
            type_ = type(value)
            if type_ not in self.ALLOWED_VALUE_TYPES:
                raise ValueError(f"{str(type_)} is not a valid 'value' type in a tree")

    def _validate_tree(self, tree):
        """Validate the full tree structure."""
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
        """Validate a tree payload."""
        value = super().process(value, obj)
        self._validate_tree(value)
        return value


class FileValidator(StringContent):
    """Base validator for file-path-based content.

    The validator ensures that the file exists, is non-empty, and that its
    extension matches any allowed set for the concrete validator subclass.
    It also caches the opened :class:`~django.core.files.File` and detected
    extension on the owning object for later use.
    """

    ALLOWED_EXT = None

    def process(self, value, obj):
        """Validate that content is a path to a readable file."""
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
        file_name = file.name if file.name is not None else file_path.name
        file_ext = Path(file_name).suffix.lower().lstrip(".")
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
    """Validator for image payloads, including enhanced images."""

    ENHANCED_EXT = ("tif", "tiff")
    ALLOWED_EXT = ("png", "jpg") + ENHANCED_EXT

    def process(self, value, obj):
        """Validate an image file and record its metadata."""
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
    """Validator for animation/video payloads."""

    ALLOWED_EXT = ("mp4",)


class SceneContent(FileValidator):
    """Validator for 3D scene and geometry payloads."""

    ALLOWED_EXT = ("stl", "ply", "csf", "avz", "scdoc", "scdocx", "dsco", "glb", "obj")


class FileContent(FileValidator):
    """Validator for generic file payloads.

    This validator accepts any file extension, only enforcing existence
    and non-empty content.
    """

    ALLOWED_EXT = None


class SimplePayloadMixin:
    """Mixin for items whose payload is stored as a pickled blob.

    Classes using this mixin are expected to store their value in the
    ``payloaddata`` field of the corresponding ORM model.
    """

    @classmethod
    def _from_db(cls: type["Item"], orm_instance, parent=None, **kwargs):
        """Reconstruct content from the ORM ``payloaddata`` field."""
        from data.extremely_ugly_hacks import safe_unpickle

        obj = super(SimplePayloadMixin, cls)._from_db(orm_instance, parent=parent, **kwargs)
        orm_instance_obj = obj._orm_instance
        if orm_instance_obj is None:
            raise ADRException("Failed to load payload data because ORM instance is missing.")
        obj.content = safe_unpickle(getattr(obj._orm_instance, "payloaddata"))
        return obj

    def save(self: "Item", **kwargs):
        """Serialize the current content into the ORM ``payloaddata`` field.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to the database ``save`` method of
            the underlying ORM instance. For eg: The ``using`` argument can be
            used to select the target database alias.

        Raises
        ------
        IntegrityError
            If the database reports an integrity violation while saving.
        InvalidFieldError
            If invalid field names or values are supplied (via decorator).
        Exception
            Any other unexpected exception is propagated unchanged.
        """
        orm_instance = self._orm_instance
        if orm_instance is None:
            raise ADRException("Failed to save payload data because ORM instance is missing.")
        setattr(orm_instance, "payloaddata", pickle.dumps(self.content, protocol=0))
        Item.save(self, **kwargs)


class FilePayloadMixin:
    """Mixin for items whose payload is stored as a file.

    The file path is tracked via the ORM ``payloadfile`` field, while a
    cached :class:`~django.core.files.File` and file extension are stored
    on the object for convenience.
    """

    _file: DjangoFile | None = None
    _file_ext: str = ""
    _orm_instance: object | None = None
    guid: str = ""
    type: str = ""

    @property
    def file_path(self):
        """Absolute path to the payload file, if available.

        Returns
        -------
        str or None
            File path or ``None`` if no file has been associated yet.
        """
        try:
            orm_instance = self._orm_instance
            if orm_instance is None:
                return None
            return getattr(getattr(orm_instance, "payloadfile"), "path")
        except (AttributeError, ValueError):
            # If the file path is not set, return None
            return None

    @property
    def has_file(self):
        """Whether a payload file exists on disk."""
        return self.file_path is not None and Path(self.file_path).is_file()

    @property
    def file_ext(self):
        """File extension of the payload file, without the leading dot."""
        try:
            orm_instance = self._orm_instance
            if orm_instance is None:
                return None
            payload_file = getattr(orm_instance, "payloadfile")
            return Path(getattr(payload_file, "path")).suffix.lower().lstrip(".")
        except (AttributeError, ValueError):
            # If the file path is not set, return None
            return None

    @classmethod
    def _from_db(cls: type["Item"], orm_instance, parent=None, **kwargs):
        """Reconstruct file-backed content from the ORM instance."""
        obj = super(FilePayloadMixin, cls)._from_db(orm_instance, parent=parent, **kwargs)
        orm_instance_obj = obj._orm_instance
        if orm_instance_obj is None:
            raise ADRException("Failed to load payload file because ORM instance is missing.")
        obj.content = getattr(orm_instance_obj, "payloadfile").path
        return obj

    @staticmethod
    def _save_file(target_path, content):
        """Persist payload content to the given file path."""
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
        """Save the payload file and ORM instance.

        The file name is derived from the item GUID and type, and the
        content is written to disk before saving the ORM instance.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to the database ``save`` method of
            the underlying ORM instance. For eg: The ``using`` argument can be
            used to select the target database alias.

        Raises
        ------
        IntegrityError
            If the database reports an integrity violation while saving.
        InvalidFieldError
            If invalid field names or values are supplied (via decorator).
        Exception
            Any other unexpected exception is propagated unchanged.
        """
        orm_instance = self._orm_instance
        if orm_instance is None:
            raise ADRException("Failed to save payload file because ORM instance is missing.")
        setattr(orm_instance, "payloadfile", f"{self.guid}_{self.type}.{self._file_ext}")
        if self._file is None:
            raise ADRException("Failed to save payload file because file content is missing.")
        file_path = self.file_path
        if file_path is None:
            raise ADRException("Failed to save payload file because target path is missing.")
        # Save file to the target path
        self._save_file(file_path, self._file)
        # save ORM instance
        parent_save = getattr(super(FilePayloadMixin, self), "save", None)
        if parent_save is None:
            raise ADRException("Failed to save payload file because parent save is unavailable.")
        parent_save(**kwargs)

    def delete(self):
        """Delete the payload file and then the ORM instance."""
        from data.utils import delete_item_media

        orm_instance = self._orm_instance
        if orm_instance is not None:
            delete_item_media(getattr(orm_instance, "guid"))
        parent_delete = getattr(super(FilePayloadMixin, self), "delete", None)
        if parent_delete is None:
            raise ADRException(
                "Failed to delete payload file because parent delete is unavailable."
            )
        return parent_delete()


class ItemType(StrEnum):
    """Enumeration of supported item payload types."""

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
    """Base class for all persisted report items.

    Items are typed containers of content linked to a :class:`Session`
    and a :class:`Dataset`. Concrete subclasses define the content
    validator and ``type`` string and are registered automatically so
    that :meth:`_from_db` and :meth:`create` can dispatch to the correct
    subclass based on the stored type.
    """

    name: str = field(compare=False, kw_only=True, default="")
    """Human-readable name for the item."""

    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    """Timestamp when the item was created."""

    source: str = field(compare=False, kw_only=True, default="")
    """Optional free-form source identifier for this item."""

    sequence: int = field(compare=False, kw_only=True, default=0)
    """Sequence index for ordering items within a dataset/session."""

    session: Session | None = field(compare=False, kw_only=True, default=None)
    """Session that owns this item."""

    dataset: Dataset | None = field(compare=False, kw_only=True, default=None)
    """Dataset associated with this item."""

    content: ItemContent = ItemContent()
    """Payload content for the item."""

    type: str = ItemType.NONE  # todo: make this read-only
    """Item type identifier, normally set by subclasses."""

    _orm_model: str = "data.models.Item"
    _type_registry = {}  # Class-level registry of subclasses keyed by type
    _in_memory: bool = field(compare=False, kw_only=True, default=False)

    def __init_subclass__(cls, **kwargs):
        """Register concrete subclasses in the type registry."""
        super().__init_subclass__(**kwargs)
        # Automatically register the subclass based on its type attribute
        Item._type_registry[cls.type] = cls

    def __post_init__(self):
        """Validate that the base class is not instantiated directly."""
        if self.__class__ is Item:
            raise ADRException("Cannot instantiate Item directly. Use the Item.create() method.")
        super().__post_init__()

    def save(self, **kwargs):
        """Save the item, enforcing that session and dataset are persisted.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to the database ``save`` method of
            the underlying ORM instance. For eg: The ``using`` argument can be
            used to select the target database alias.

        Raises
        ------
        ADRException
            If the session or dataset is missing.
        Session.NotSaved
            If the associated session has not been saved.
        Dataset.NotSaved
            If the associated dataset has not been saved.
        """
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
    def _from_db(cls, orm_instance, parent=None, **kwargs):
        """Reconstruct an item or item subclass from the ORM instance.

        If called on :class:`Item` itself, this method dispatches to the
        appropriate registered subclass based on the ``type`` field.
        """
        # Create a new instance of the correct subclass
        if cls is Item:
            # Get the class based on the type attribute
            item_cls = cls._type_registry[orm_instance.type]
            return item_cls._from_db(orm_instance, parent=parent, **kwargs)

        return super()._from_db(orm_instance, parent=parent, **kwargs)

    @classmethod
    def create(cls, **kwargs):
        """Factory-style creation that dispatches to the correct subclass.

        When invoked on :class:`Item`, the caller must provide a
        ``type`` keyword argument identifying the desired item type. For
        concrete subclasses, ``type`` is injected automatically.

        Parameters
        ----------
        **kwargs
            Fields required by the concrete item type. When called on
            :class:`Item`, must include ``type``. Eg: ``type="table", content=my_array``.

        Returns
        -------
        Item
            Newly created and saved item instance.

        Raises
        ------
        ADRException
            If ``type`` is missing when called on :class:`Item`.
        """
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
        """Normalize kwargs for typed query methods.

        The ``content`` kwarg is not supported for :meth:`get` and
        :meth:`filter`, and type-scoped subclasses automatically inject a
        ``type`` filter.
        """
        if "content" in kwargs:
            raise ValueError("'content' kwarg is not supported for get and filter methods")
        return {"type": cls.type, **kwargs} if cls.type != "none" else kwargs

    @classmethod
    def get(cls, **kwargs):
        """
        Retrieve a single item instance, scoped by subclass type.

        Parameters
        ----------
        **kwargs
            Key-value filters to find the item. Eg: ``name="My Item"``

        Returns
        -------
        Item
            Newly created and saved item instance.

        Raises
        ------
        ADRException
            If ``type`` is missing when called on :class:`Item`.

        """
        return super().get(**cls._validate_kwargs(**kwargs))

    @classmethod
    def filter(cls, **kwargs):
        """Return a collection of items, scoped by subclass type.

        Parameters
        ----------
        **kwargs
            Key-value filters to find matching items. Eg: ``source="Simulation 1"``

        Returns
        -------
        ObjectSet
            Collection of matching items.
        """
        return super().filter(**cls._validate_kwargs(**kwargs))

    @classmethod
    def find(cls, query=""):
        """Search for items using an ADR query string.

        For typed subclasses, an ``i_type`` filter is not allowed.

        Parameters
        ----------
        query : str, default: ""
            Free-text or domain-specific search query.

        Returns
        -------
        ObjectSet
            Collection of matching items.

        Raises
        ------
        ADRException
            If an explicit ``i_type`` filter is provided when using a
            subclass of :class:`Item`.
        """
        if cls is Item:
            return super().find(query=query)
        if "i_type|" in query:
            raise ADRException(
                extra_detail="The 'i_type' filter is not allowed if using a subclass of Item"
            )
        return super().find(query=f"A|i_type|cont|{cls.type};{query}")  # noqa: E702

    def render(self, *, context=None, request=None) -> str | None:
        """Render the item as HTML.

        Parameters
        ----------
        context : dict or None, optional
            Context dictionary passed to the underlying rendering logic.
            The ``plotly`` and ``format`` keys may be used to control
            output. If omitted, a minimal default is used.
        request : HttpRequest or None, optional
            Django request object, if available.

        Returns
        -------
        str or None
            Rendered HTML string for the item.
        """
        if context is None:
            context = {}
        ctx = {
            "request": request,
            "ansys_version": None,
            "plotly": int(context.get("plotly", 0)),  # default referenced in the header via static
            "format": context.get("format", None),
        }
        try:
            orm_instance = self._orm_instance
            if orm_instance is None:
                raise ADRException("Item ORM instance is not initialized.")
            render_method = getattr(orm_instance, "render", None)
            if render_method is None:
                raise ADRException("Item render function is not available on ORM instance.")
            ctx["HTML"] = render_method(ctx)
        except Exception as e:
            from ceireports.utils import get_render_error_html

            ctx["HTML"] = get_render_error_html(e, target="report item", guid=self.guid)

        return render_to_string("data/item_detail_simple.html", context=ctx, request=request)


class String(SimplePayloadMixin, Item):
    """Item representing a plain string payload."""

    content: StringContent = StringContent()
    """Validated string content for this item."""

    type: str = ItemType.STRING
    """Item type identifier for string items."""


class HTML(String):
    """Item representing an HTML fragment."""

    content: HTMLContent = HTMLContent()
    """Validated HTML fragment content for this item."""

    type: str = ItemType.HTML
    """Item type identifier for HTML items."""


class Table(Item):
    """Item representing a 2D table backed by a NumPy array.

    The array is stored in the ORM ``payloaddata`` field together with
    additional payload properties such as row and column labels.
    """

    content: TableContent = TableContent()
    """Validated 2D NumPy array content for this table item."""

    type: str = ItemType.TABLE
    """Item type identifier for table items."""

    _payload_properties: tuple = (  # for backwards compatibility
        "rowlbls",
        "collbls",
    )
    _properties: tuple = table_attr + _payload_properties

    @classmethod
    def _from_db(cls, orm_instance, parent=None, **kwargs):
        """Rebuild the table array and payload properties from ``payloaddata``."""
        from data.extremely_ugly_hacks import safe_unpickle

        obj = super()._from_db(orm_instance, parent=parent, **kwargs)
        orm_instance_obj = obj._orm_instance
        if orm_instance_obj is None:
            raise ADRException("Failed to load table payload because ORM instance is missing.")
        payload = safe_unpickle(orm_instance_obj.payloaddata)
        obj.content = payload.pop("array", None)
        for prop in cls._properties:
            if prop in payload:
                setattr(obj, prop, payload[prop])
        return obj

    def save(self, **kwargs):
        """Serialize the table array and payload properties into ``payloaddata``.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to the database ``save`` method of
            the underlying ORM instance. For eg: The ``using`` argument can be
            used to select the target database alias.

        Raises
        ------
        IntegrityError
            If the database reports an integrity violation while saving.
        InvalidFieldError
            If invalid field names or values are supplied (via decorator).
        Exception
            Any other unexpected exception is propagated unchanged.
        """
        payload = {
            "array": self.content,
        }
        for prop in self.__class__._properties:
            value = getattr(self, prop, None)
            if value is not None:
                payload[prop] = value
        orm_instance = self._orm_instance
        if orm_instance is None:
            raise ADRException("Failed to save table payload because ORM instance is missing.")
        setattr(orm_instance, "payloaddata", pickle.dumps(payload, protocol=0))
        super().save(**kwargs)


class Tree(SimplePayloadMixin, Item):
    """Item representing a hierarchical tree payload."""

    content: TreeContent = TreeContent()
    """Validated tree structure content for this item."""

    type: str = ItemType.TREE
    """Item type identifier for tree items."""


class Image(FilePayloadMixin, Item):
    """Item representing an image payload, optionally enhanced."""

    _width: int = field(compare=False, init=False, default=0)
    """Image width in pixels, populated from the source file."""

    _height: int = field(compare=False, init=False, default=0)
    """Image height in pixels, populated from the source file."""

    _enhanced: bool = field(compare=False, init=False, default=False)
    """Whether this image has enhanced metadata (for example TIFF enhancements)."""

    content: ImageContent = ImageContent()
    """Validated image file content for this item."""

    type: str = ItemType.IMAGE
    """Item type identifier for image items."""

    @property
    def width(self):
        """Image width in pixels."""
        return self._width

    @property
    def height(self):
        """Image height in pixels."""
        return self._height

    @property
    def enhanced(self):
        """Whether this image is an enhanced image (for example TIFF with metadata)."""
        return self._enhanced

    def save(self, **kwargs):
        """Save the image payload, converting to PNG when appropriate.

        Non-enhanced images are stored as PNG files, while enhanced
        images retain their original format. The file name is derived
        from the item GUID.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to the database ``save`` method of
            the underlying ORM instance. For eg: The ``using`` argument can be
            used to select the target database alias.

        Raises
        ------
        IntegrityError
            If the database reports an integrity violation while saving.
        InvalidFieldError
            If invalid field names or values are supplied (via decorator).
        ADRException
            If an error occurs during image conversion.
        Exception
            Any other unexpected exception is propagated unchanged.
        """
        if self._file is None:
            raise ADRException("Failed to save image because file content is missing.")
        with self._file.open(mode="rb") as f:
            img_bytes = f.read()
        image = PILImage.open(io.BytesIO(img_bytes))
        # Determine final file name and format
        target_ext = "png" if not self._enhanced else self._file_ext
        orm_instance = self._orm_instance
        if orm_instance is None:
            raise ADRException("Failed to save image because ORM instance is missing.")
        setattr(orm_instance, "payloadfile", f"{self.guid}_image.{target_ext}")
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
    """Item representing an animation/video payload."""

    content: AnimContent = AnimContent()
    """Validated animation/video file content for this item."""

    type: str = ItemType.ANIMATION
    """Item type identifier for animation items."""


class Scene(FilePayloadMixin, Item):
    """Item representing a 3D scene or geometry payload."""

    content: SceneContent = SceneContent()
    """Validated 3D scene or geometry file content for this item."""

    type: str = ItemType.SCENE
    """Item type identifier for scene items."""

    def save(self, **kwargs):
        """Save the 3D scene payload and ensure derived geometry is built.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to the database ``save`` method of
            the underlying ORM instance. For eg: The ``using`` argument can be
            used to select the target database alias.

        Raises
        ------
        IntegrityError
            If the database reports an integrity violation while saving.
        InvalidFieldError
            If invalid field names or values are supplied (via decorator).
        Exception
            Any other unexpected exception is propagated unchanged.
        """
        super().save(**kwargs)
        if not Path(get_avz_directory(self.file_path)).exists():
            rebuild_3d_geometry(self.file_path)


class File(FilePayloadMixin, Item):
    """Item representing a generic file payload."""

    content: FileContent = FileContent()
    """Validated generic file content for this item."""

    type: str = ItemType.FILE
    """Item type identifier for generic file items."""

    def save(self, **kwargs):
        """Save the generic file payload and rebuild geometry if needed.

        Parameters
        ----------
        **kwargs
            Keyword arguments forwarded to the database ``save`` method of
            the underlying ORM instance. For eg: The ``using`` argument can be
            used to select the target database alias.

        Raises
        ------
        IntegrityError
            If the database reports an integrity violation while saving.
        InvalidFieldError
            If invalid field names or values are supplied (via decorator).
        Exception
            Any other unexpected exception is propagated unchanged.
        """
        super().save(**kwargs)
        if (
            file_is_3d_geometry(self.file_path)
            and not Path(get_avz_directory(self.file_path)).exists()
        ):
            rebuild_3d_geometry(self.file_path)
