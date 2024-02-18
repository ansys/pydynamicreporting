import shlex
import uuid
from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass, field
from typing import Any, Type

from django.db.models import Model


class BaseMetaclass(ABCMeta):

    def __new__(
            mcs,
            cls_name: str,
            bases: tuple[type[Any], ...],
            namespace: dict[str, Any],
            **kwargs: Any,
    ) -> type:
        super_new = super().__new__
        # ensure initialization is only performed for subclasses of BaseModel
        # (excluding BaseModel class itself).
        parents = [b for b in bases if isinstance(b, BaseMetaclass)]
        if parents and "_properties" in namespace:
            dynamic_props_field = namespace["_properties"]
            if hasattr(dynamic_props_field, "default"):
                props = dynamic_props_field.default
                new_namespace = {**namespace}
                for prop in props:
                    new_namespace[prop] = None
                return super_new(mcs, cls_name, bases, new_namespace, **kwargs)
        return super_new(mcs, cls_name, bases, namespace)


@dataclass(repr=False)
class BaseModel(metaclass=BaseMetaclass):
    guid: str = field(compare=False, kw_only=True, default_factory=uuid.uuid1)
    tags: str = field(compare=False, kw_only=True, default="")
    _orm_instance: Any = field(init=False, compare=False)  # tracks the corresponding ORM instance
    _saved: bool = field(init=False, compare=False, default=False)  # tracks if the object is saved in the db

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} object {self.guid}"

    @staticmethod
    def _add_quotes(input_str):
        if " " in input_str and input_str[0] != "'":
            return "'" + input_str + "'"
        return input_str

    def _rebuild_tags(self, tags):
        tags_list = []
        for tag in tags:
            tag_and_value = tag.split("=")
            if len(tag_and_value) > 1:
                tags_list.append(self._add_quotes(tag_and_value[0]) + "=" + self._add_quotes(tag_and_value[1]))
            else:
                tags_list.append(self._add_quotes(tag_and_value[0]))
        self.set_tags(" ".join(tags_list))

    def get_tags(self):
        return self.tags

    def set_tags(self, tag_str):
        self.tags = tag_str

    def add_tag(self, tag, value=None):
        self.rem_tag(tag)
        tags = shlex.split(self.get_tags())
        if value:
            tags.append(tag + "=" + str(value))
        else:
            tags.append(tag)
        self._rebuild_tags(tags)

    def rem_tag(self, tag):
        tags = shlex.split(self.get_tags())
        for tag in list(tags):
            if "=" in tag:
                if tag.split("=")[0] == tag:
                    tags.remove(tag)
            elif tag == tag:
                tags.remove(tag)
        self._rebuild_tags(tags)

    def save(self):
        self._orm_instance.save()

    def delete(self):
        self._orm_instance.delete()

    @staticmethod
    @abstractmethod
    def create(**kwargs):
        pass

    @staticmethod
    @abstractmethod
    def get(**kwargs):
        pass

    @abstractmethod
    def post_init(self):
        pass

    def __post_init__(self):
        self.post_init()


class Validator(ABC):
    def __init__(self, *, default=None):
        self._default = default

    def __set_name__(self, owner, name):
        self._name = "_" + name

    def __get__(self, obj, obj_type=None):
        if obj is None:
            return self._default

        return getattr(obj, self._name, self._default)

    def __set__(self, obj, value):
        self.validate(value)
        setattr(obj, self._name, value)

    @abstractmethod
    def validate(self, value):
        pass
