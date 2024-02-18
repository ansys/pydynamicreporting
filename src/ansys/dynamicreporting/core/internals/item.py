from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy
from django.utils import timezone

from .base import BaseModel, Validator
from ..adr_utils import table_attr
from .report_framework.utils import get_render_error_html


class StringContent(Validator):
    def validate(self, string):
        if not isinstance(string, str):
            raise TypeError(f'Expected content to be a str')


class TableContent(Validator):
    def validate(self, array):
        if not isinstance(array, numpy.ndarray) or array.dtype.kind not in ["S", "f"]:
            raise TypeError("Expected content to be a numpy array of bytes or float type.")
        if len(array.shape) != 2:
            raise ValueError("Expected content to be a 2 dimensional numpy array.")


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


@dataclass(repr=False)
class Session(BaseModel):
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    hostname: str = field(compare=False, kw_only=True, default="")
    platform: str = field(compare=False, kw_only=True, default="")
    application: str = field(compare=False, kw_only=True, default="")
    version: str = field(compare=False, kw_only=True, default="")

    def post_init(self):
        from .data.models import Session as SessionModel
        self._orm_instance = SessionModel()

    @staticmethod
    def get(**kwargs):
        from .data.models import Session as SessionModel
        return SessionModel.objects.get(**kwargs)

    @staticmethod
    def create(**kwargs):
        from .data.models import Session as SessionModel
        return SessionModel.objects.create(**kwargs)


@dataclass(repr=False)
class Dataset(BaseModel):
    filename: str = field(compare=False, kw_only=True, default="")
    dirname: str = field(compare=False, kw_only=True, default="")
    format: str = field(compare=False, kw_only=True, default="")
    numparts: int = field(compare=False, kw_only=True, default=0)
    numelements: int = field(compare=False, kw_only=True, default=0)

    def post_init(self):
        from .data.models import Dataset as DatasetModel
        self._orm_instance = DatasetModel()

    @staticmethod
    def get(**kwargs):
        from .data.models import Dataset as DatasetModel
        return DatasetModel.objects.get(**kwargs)

    @staticmethod
    def create(**kwargs):
        from .data.models import Dataset as DatasetModel
        return DatasetModel.objects.create(**kwargs)


@dataclass(repr=False)
class Item(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)
    source: str = field(compare=False, kw_only=True, default="")
    sequence: int = field(compare=False, kw_only=True, default=0)
    session: str = field(compare=False, kw_only=True, default="")
    dataset: str = field(compare=False, kw_only=True, default="")
    _type: str = field(init=False, compare=False, default="none")

    @property
    def type(self):
        return self._type

    def post_init(self):
        from .data.models import Item as ItemModel
        self._orm_instance = ItemModel()

    @staticmethod
    def get(**kwargs):
        from .data.models import Item as ItemModel
        return ItemModel.objects.get(**kwargs)

    @staticmethod
    def create(**kwargs):
        from .data.models import Item as ItemModel
        return ItemModel.objects.create(**kwargs)

    def delete(self):
        # todo: delete sessions, datasets
        pass

    def render(self, ctx):
        if "request" not in ctx:
            ctx["request"] = None
        try:
            return self._orm_instance.render(ctx)
        except Exception as e:
            return get_render_error_html(e, target='report item', guid=self.guid)


@dataclass(repr=False)
class String(Item):
    _type: str = field(init=False, compare=False, default="string")
    content: StringContent = StringContent()


@dataclass(repr=False)
class Text(String):
    pass


@dataclass(repr=False)
class Table(Item):
    content: TableContent = TableContent()
    _type: str = field(init=False, compare=False, default="table")
    _properties: list = field(init=False, default=table_attr)


@dataclass(repr=False)
class Plot(Table):
    pass


@dataclass(repr=False)
class Tree(Item):
    _type: str = field(init=False, compare=False, default="tree")
    content: TreeContent = TreeContent()


@dataclass(repr=False)
class Scene(Item):
    _type: str = "scene"
    content: SceneContent = SceneContent()


@dataclass(repr=False)
class Image(Item):
    _type: str = field(init=False, compare=False, default="image")
    width: int = field(compare=False, kw_only=True, default=0)
    height: int = field(compare=False, kw_only=True, default=0)
    content: ImageContent = ImageContent()


@dataclass(repr=False)
class HTML(Item):
    _type: str = field(init=False, compare=False, default="html")
    content: HTMLContent = HTMLContent()


@dataclass(repr=False)
class Animation(Item):
    _type: str = field(init=False, compare=False, default="anim")
    content: AnimContent = AnimContent()


@dataclass(repr=False)
class File(Item):
    _type: str = field(init=False, compare=False, default="file")
    content: FileContent = FileContent()
