import pickle
import platform
from dataclasses import dataclass, field
from datetime import datetime

import numpy
from django.template.loader import render_to_string
from django.utils import timezone

from .base import BaseModel, Validator, require_model_import
from .data.extremely_ugly_hacks import safe_unpickle
from .data.utils import delete_item_media
from .report_framework.utils import get_render_error_html
from ..adr_utils import table_attr
from ..utils import report_utils


class StringContent(Validator):
    def validate(self, string):
        if not isinstance(string, str):
            raise TypeError(f'Expected content to be a string')
        return string


class TableContent(Validator):
    def validate(self, array):
        if not isinstance(array, numpy.ndarray):
            raise TypeError("Expected content to be a numpy array")
        if array.dtype.kind not in ["S", "f"]:
            raise TypeError("Expected content to be a numpy array of bytes or float type.")
        if len(array.shape) != 2:
            raise ValueError("Expected content to be a 2 dimensional numpy array.")
        return array


class ImageContent(Validator):
    def validate(self, value):
        pass


class AnimContent(Validator):
    def validate(self, value):
        pass


class TreeContent(Validator):
    def validate(self, value):
        pass


class SceneContent(Validator):
    def validate(self, value):
        pass


class FileContent(Validator):
    def validate(self, value):
        pass


class HTMLContent(Validator):
    def validate(self, value):
        pass


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


class Item(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    source: str = field(compare=False, kw_only=True, default="")
    sequence: int = field(compare=False, kw_only=True, default=0)
    session: Session = field(compare=False, kw_only=True, default_factory=Session)
    dataset: Dataset = field(compare=False, kw_only=True, default_factory=Dataset)
    _type: str = "none"
    _orm_model: str = "data.models.Item"

    @property
    def type(self):
        return self._type

    def delete(self, **kwargs):
        super().delete(**kwargs)
        delete_item_media(self._orm_instance.guid)

    def render(self, context=None):
        if context is None:
            context = {}
        template_context = {**context}
        if "request" not in template_context:
            template_context["request"] = None
        try:
            template_context["HTML"] = self._orm_instance.render(template_context)
            return render_to_string('data/item_detail_simple.html', template_context)
        except Exception as e:
            return get_render_error_html(e, target='report item', guid=self.guid)


class String(Item):
    content: StringContent = StringContent()
    _type: str = "string"

    @property
    def type(self):
        return self._type


class Text(String):
    pass


class Table(Item):
    content: TableContent = TableContent()
    _type: str = "table"
    _properties: tuple = table_attr

    @property
    def type(self):
        return self._type

    @classmethod
    @require_model_import
    def get(cls, **kwargs):
        obj = super().get(**kwargs)
        # type specific deserialization of payload
        payload = safe_unpickle(obj._orm_instance.payloaddata)
        obj.content = payload.pop("array", None)
        for prop in cls._properties:
            if prop in payload:
                setattr(obj, prop, payload[prop])
        return obj

    @require_model_import
    def save(self, **kwargs):
        payload = {
            "array": self.content,
        }
        for prop in self._properties:
            value = getattr(self, prop, None)
            if value is not None:
                payload[prop] = value
        if self._orm_instance is None:
            self._orm_instance = self._orm_model_cls()
        self._orm_instance.payloaddata = pickle.dumps(payload, protocol=0)
        super().save(**kwargs)


class Plot(Table):
    pass


class Tree(Item):
    content: TreeContent = TreeContent()
    _type: str = "tree"


class Scene(Item):
    content: SceneContent = SceneContent()
    _type: str = "scene"


class Image(Item):
    width: int = field(compare=False, kw_only=True, default=0)
    height: int = field(compare=False, kw_only=True, default=0)
    content: ImageContent = ImageContent()
    _type: str = "image"


class HTML(Item):
    content: HTMLContent = HTMLContent()
    _type: str = "html"


class Animation(Item):
    content: AnimContent = AnimContent()
    _type: str = "anim"


class File(Item):
    content: FileContent = FileContent()
    _type: str = "file"
