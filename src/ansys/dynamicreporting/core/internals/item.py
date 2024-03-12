import pickle
import platform
from dataclasses import dataclass, field
from datetime import datetime

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


class Item(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    source: str = field(compare=False, kw_only=True, default="")
    sequence: int = field(compare=False, kw_only=True, default=0)
    session: Session = field(compare=False, kw_only=True, default=None)
    dataset: Dataset = field(compare=False, kw_only=True, default=None)
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
        super().save(**kwargs)

    def delete(self, **kwargs):
        super().delete(**kwargs)
        delete_item_media(self._orm_instance.guid)

    def render(self, context=None, request=None):
        if context is None:
            context = {}
        ctx = {**context, **global_settings(request), "request": request}
        try:
            ctx["HTML"] = self._orm_instance.render(ctx)
        except Exception as e:
            ctx["HTML"] = get_render_error_html(e, target='report item', guid=self.guid)

        return render_to_string('data/item_detail_simple.html', context=ctx, request=request)


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
    def get(cls, **kwargs):
        obj = super().get(**kwargs)
        # type specific deserialization of payload
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
