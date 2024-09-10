from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
import importlib
import inspect
from itertools import chain
import shlex
from typing import Any
import uuid
from uuid import UUID

from django.core.exceptions import (
    FieldDoesNotExist,
    FieldError,
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    ValidationError,
)
from django.db import DatabaseError
from django.db.models import Model, QuerySet
from django.db.models.base import subclass_exception

from ..exceptions import (
    ADRException,
    MultipleObjectsReturnedError,
    ObjectDoesNotExistError,
    ObjectNotSavedError,
)


def add_exception_to_cls(name, base, cls, parents, module):
    base_exceptions = tuple(getattr(p, name) for p in parents if hasattr(p, name))
    exception_cls = subclass_exception(
        name, base_exceptions or (base,), module, attached_to=cls  # bases
    )
    setattr(cls, name, exception_cls)


def handle_field_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (FieldError, FieldDoesNotExist, ValidationError, DatabaseError) as e:
            raise ADRException(extra_detail=f"One or more fields set or accessed are invalid: {e}")

    return wrapper


class BaseMeta(ABCMeta):
    _cls_registry: dict[str, type["BaseModel"]] = {}
    _model_cls_registry: dict[str, type[Model]] = {}

    def __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        super_new = super().__new__
        # ensure initialization is only performed for subclasses of BaseModel
        new_cls = super_new(mcs, cls_name, bases, namespace)
        parents = [b for b in bases if isinstance(b, BaseMeta)]
        if parents:
            # dynamically make the properties listed into class attrs
            if "_properties" in namespace:
                dynamic_props_field = namespace["_properties"]
                if hasattr(dynamic_props_field, "default"):
                    props = dynamic_props_field.default
                    new_namespace = {**namespace}
                    for prop in props:
                        new_namespace[prop] = None
                    new_cls = super_new(mcs, cls_name, bases, new_namespace, **kwargs)
            # save every class extending BaseModel
            mcs._cls_registry[cls_name] = new_cls
            # add exceptions
            add_exception_to_cls(
                "DoesNotExist",
                ObjectDoesNotExistError,
                new_cls,
                parents,
                namespace.get("__module__"),
            )
            add_exception_to_cls(
                "NotSaved", ObjectNotSavedError, new_cls, parents, namespace.get("__module__")
            )
            add_exception_to_cls(
                "MultipleObjectsReturned",
                MultipleObjectsReturnedError,
                new_cls,
                parents,
                namespace.get("__module__"),
            )
        # all classes must be dataclasses
        new_cls = dataclass(eq=False, order=False, repr=False)(new_cls)
        return new_cls

    def __getattribute__(cls, name):
        # applies only for class attrs
        # lazy load ORM model upon access
        attr = super().__getattribute__(name)
        if name == "_orm_model_cls":
            # for subclasses of BaseModel
            parents = [b for b in cls.__bases__ if isinstance(b, BaseMeta)]
            model_str = cls._orm_model
            if parents and attr is None and model_str:
                module_name, cls_name = model_str.rsplit(".", 1)
                if cls_name in cls._model_cls_registry:
                    return cls._model_cls_registry[cls_name]
                # import on demand
                module = importlib.import_module(module_name, package=__package__)
                attr = getattr(module, cls_name)
                cls._model_cls_registry[cls_name] = attr
        return attr


class BaseModel(metaclass=BaseMeta):
    guid: UUID = field(init=False, compare=False, kw_only=True, default_factory=uuid.uuid1)
    tags: str = field(compare=False, kw_only=True, default="")
    _saved: bool = field(
        init=False, compare=False, default=False
    )  # tracks if the object is saved in the db
    _orm_model: str = field(init=False, compare=False, default=None)
    _orm_model_cls: type[Model] = field(init=False, compare=False, default=None)
    _orm_instance: Model = field(
        init=False, compare=False, default=None
    )  # tracks the corresponding ORM instance

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} object {self.guid}"

    def __post_init__(self):
        self._validate_field_types()
        self._orm_instance = self.__class__._orm_model_cls()

    def _validate_field_types(self):
        for field_name, field_type in self._get_field_names(with_types=True):
            if isinstance(field_type, str):
                type_ = self.__class__._cls_registry[field_type]
            else:
                type_ = field_type
            if issubclass(type_, Validator):
                continue
            value = getattr(self, field_name, None)
            if value is not None and not isinstance(value, type_):
                raise TypeError(f"Expected {field_name} to be of type {type_}.")

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
                tags_list.append(
                    self._add_quotes(tag_and_value[0]) + "=" + self._add_quotes(tag_and_value[1])
                )
            else:
                tags_list.append(self._add_quotes(tag_and_value[0]))
        self.set_tags(" ".join(tags_list))

    @staticmethod
    def _get_orm_field_names(orm_instance):
        return tuple(f.name for f in orm_instance._meta.get_fields())

    @classmethod
    def _get_field_names(cls, with_types=False, include_private=False):
        fields_ = []
        for f in dataclass_fields(cls):
            if not include_private and f.name.startswith("_"):
                continue
            fields_.append((f.name, f.type) if with_types else f.name)
        return tuple(fields_)

    @classmethod
    def _get_all_field_names(cls):
        """Returns a list of all field names from a dataclass, including properties."""
        property_fields = []
        for name, value in inspect.getmembers(cls):
            if isinstance(value, property):
                property_fields.append(name)
        return tuple(property_fields) + cls._get_field_names()

    @classmethod
    def serialize_from_orm(cls, orm_instance):
        cls_fields = dict(cls._get_field_names(with_types=True, include_private=True))
        model_fields = cls._get_orm_field_names(orm_instance)
        obj = cls()
        for field_ in model_fields:
            if field_ in cls_fields:
                attr = field_
            elif f"_{field_}" in cls_fields:
                # serialize some private fields as well.
                attr = f"_{field_}"
            else:
                continue
            value = getattr(orm_instance, field_, None)
            # don't check for None here, we need everything as-is
            # We must also serialize 'related' fields
            if isinstance(value, Model):
                field_type = cls_fields[attr]
                if isinstance(field_type, str):
                    type_ = cls._cls_registry[field_type]
                else:
                    type_ = field_type
                value = type_.serialize_from_orm(value)
            setattr(obj, attr, value)

        obj._orm_instance = orm_instance
        obj._saved = True
        return obj

    @property
    def saved(self):
        return self._saved

    @handle_field_errors
    def save(self, **kwargs):
        cls_fields = self._get_all_field_names()
        model_fields = self._get_orm_field_names(self._orm_instance)
        for field_ in cls_fields:
            if field_ in model_fields:
                value = getattr(self, field_, None)
                if value is not None:
                    if isinstance(value, list):
                        obj_list = []
                        for obj in value:
                            obj_list.append(obj._orm_instance)
                        if obj_list:
                            getattr(self._orm_instance, field_).add(*obj_list)
                    else:
                        if isinstance(value, BaseModel):
                            value = value._orm_instance.__class__.objects.get(guid=value.guid)
                        setattr(self._orm_instance, field_, value)
        self._orm_instance.save(**kwargs)
        self._saved = True

    @classmethod
    @handle_field_errors
    def create(cls, **kwargs):
        obj = cls(**kwargs)
        obj.save(force_insert=True)
        return obj

    def delete(self, **kwargs):
        if not self._saved:
            raise self.__class__.NotSaved(extra_detail="Delete failed")
        count, _ = self._orm_instance.delete(**kwargs)
        self._saved = False
        return count

    @classmethod
    @handle_field_errors
    def get(cls, **kwargs):
        try:
            orm_instance = cls._orm_model_cls.objects.get(**kwargs)
        except ObjectDoesNotExist:
            raise cls.DoesNotExist
        except MultipleObjectsReturned:
            raise cls.MultipleObjectsReturned

        return cls.serialize_from_orm(orm_instance)

    @classmethod
    @handle_field_errors
    def filter(cls, **kwargs):
        qs = cls._orm_model_cls.objects.filter(**kwargs)
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)

    @classmethod
    @handle_field_errors
    def find(cls, query="", reverse=False, sort_tag="date"):
        qs = cls._orm_model_cls.find(query=query, reverse=reverse, sort_tag=sort_tag)
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)

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


@dataclass(eq=False, order=False, repr=False)
class ObjectSet:
    _model: type[BaseModel] = field(compare=False, default=None)
    _obj_set: list[BaseModel] = field(init=True, compare=False, default_factory=list)
    _saved: bool = field(init=False, compare=False, default=False)
    _orm_model: type[Model] = field(compare=False, default=None)
    _orm_queryset: QuerySet = field(compare=False, default=None)

    def __post_init__(self):
        if self._orm_queryset is not None:
            self._saved = True
            self._obj_set = [
                self._model.serialize_from_orm(instance) for instance in self._orm_queryset
            ]

    def __repr__(self):
        return f"<{self.__class__.__name__}  {self._obj_set}>"

    def __str__(self):
        return str(self._obj_set)

    def __len__(self):
        return len(self._obj_set)

    def __iter__(self):
        return iter(self._obj_set)

    def __bool__(self):
        return bool(self._obj_set)

    def __getitem__(self, k):
        return self._obj_set.__getitem__(k)

    @property
    def saved(self):
        return self._saved

    def delete(self):
        self._obj_set = []
        self._saved = False
        count, _ = self._orm_queryset.delete()
        return count

    def values_list(self, *fields, flat=False):
        if flat and len(fields) > 1:
            raise TypeError(
                "'flat' is not valid when values_list is called with more than one " "field."
            )
        ret = []
        for obj in self._obj_set:
            ret.append(tuple(getattr(obj, f, None) for f in fields))
        return chain.from_iterable(ret) if flat else ret


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
        cleaned_value = None
        if value is not None:
            cleaned_value = self.process(value, obj)
        setattr(obj, self._name, cleaned_value)

    @abstractmethod
    def process(self, value, obj):
        pass
