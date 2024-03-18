import pickle
import platform
import uuid
from dataclasses import field
from datetime import datetime
from html.parser import HTMLParser as BaseHTMLParser

import numpy
from django.template.loader import render_to_string
from django.utils import timezone

from .base import BaseModel, Validator
from .data.extremely_ugly_hacks import safe_unpickle
from .data.utils import delete_item_media
from .report_framework.context_processors import global_settings
from .report_framework.utils import get_render_error_html
from ..adr_utils import table_attr
from ..exceptions import PyadrException
from ..utils import report_utils


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


class SimplePayloadMixin:
    @classmethod
    def serialize_from_orm(cls, orm_instance):
        obj = super().serialize_from_orm(orm_instance)
        obj.content = safe_unpickle(obj._orm_instance.payloaddata)
        return obj

    def save(self, **kwargs):
        self._orm_instance.payloaddata = pickle.dumps(self.content, protocol=0)
        super().save(**kwargs)


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


class StringContent(Validator):
    def validate(self, string):
        if not isinstance(string, str):
            raise TypeError("Expected content to be a string")
        return string


class HTMLContent(StringContent):
    def validate(self, string):
        html_str = super().validate(string)
        if not HTMLParser().validate(html_str):
            raise ValueError(f'Expected content to contain valid HTML')
        return html_str


class TableContent(Validator):
    def validate(self, array):
        if not isinstance(array, numpy.ndarray):
            raise TypeError("Expected content to be a numpy array")
        if array.dtype.kind not in ["S", "f"]:
            raise TypeError("Expected content to be a numpy array of bytes or float type.")
        if len(array.shape) != 2:
            raise ValueError("Expected content to be a 2 dimensional numpy array.")
        return array


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

    def validate(self, tree):
        self._validate_tree(tree)
        return tree


class ImageContent(Validator):
    def validate(self, value):
        pass


class AnimContent(Validator):
    def validate(self, value):
        pass


class SceneContent(Validator):
    def validate(self, value):
        pass


class FileContent(Validator):
    def validate(self, value):
        pass


class Item(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    source: str = field(compare=False, kw_only=True, default="")
    sequence: int = field(compare=False, kw_only=True, default=0)
    session: Session = field(compare=False, kw_only=True, default=None)
    dataset: Dataset = field(compare=False, kw_only=True, default=None)
    content: type[Validator] = field(compare=False, kw_only=True, default=None)
    _type: str = "none"
    _orm_model: str = "data.models.Item"

    @property
    def type(self):
        return self._type

    def save(self, **kwargs):
        if self.session is None or self.dataset is None:
            raise PyadrException(extra_detail="A session and a dataset are required to save an item")
        if not self.session.saved:
            raise Session.NotSaved(extra_detail="Failed to save item because the session is not saved")
        if not self.dataset.saved:
            raise Dataset.NotSaved(extra_detail="Failed to save item because the dataset is not saved")
        if self.content is None:
            raise PyadrException(extra_detail=f"The item {self.guid} must have some content to save")
        super().save(**kwargs)

    def delete(self, **kwargs):
        super().delete(**kwargs)
        delete_item_media(self._orm_instance.guid)

    @classmethod
    def filter(cls, **kwargs):
        new_kwargs = {"type": cls._type, **kwargs} if cls._type != "none" else kwargs
        return super().filter(**new_kwargs)

    @classmethod
    def get(cls, **kwargs):
        new_kwargs = {"type": cls._type, **kwargs} if cls._type != "none" else kwargs
        return super().get(**new_kwargs)

    def render(self, context=None, request=None):
        if context is None:
            context = {}
        ctx = {**context, **global_settings(request), "request": request}
        try:
            ctx["HTML"] = self._orm_instance.render(ctx)
        except Exception as e:
            ctx["HTML"] = get_render_error_html(e, target='report item', guid=self.guid)

        return render_to_string('data/item_detail_simple.html', context=ctx, request=request)


class String(SimplePayloadMixin, Item):
    content: StringContent = StringContent()
    _type: str = "string"


class Text(String):
    pass


class HTML(String):
    content: HTMLContent = HTMLContent()
    _type: str = "html"


class Table(Item):
    content: TableContent = TableContent()
    _type: str = "table"
    _properties: tuple = table_attr

    @property
    def type(self):
        return self._type

    @classmethod
    def serialize_from_orm(cls, orm_instance):
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
    _type: str = "tree"


class Image(Item):
    width: int = field(compare=False, kw_only=True, default=0)
    height: int = field(compare=False, kw_only=True, default=0)
    content: ImageContent = ImageContent()
    _type: str = "image"


class Animation(Item):
    content: AnimContent = AnimContent()
    _type: str = "anim"


class Scene(Item):
    content: SceneContent = SceneContent()
    _type: str = "scene"


class File(Item):
    content: FileContent = FileContent()
    _type: str = "file"
