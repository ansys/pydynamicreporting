import importlib
import inspect
import shlex
import uuid
from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass, field, fields
from typing import Any, Type
from uuid import UUID

from django.db.models import Model

from ..exceptions import ObjectNotSavedError


def require_model_import(func):
    def wrapper(*args, **kwargs):
        arg = args[0]
        if isinstance(arg, BaseModel):
            cls = arg.__class__
        else:
            cls = arg
        if cls._orm_model and cls._orm_model_cls is None:
            module_name, class_name = cls._orm_model.rsplit(".", 1)
            # relative import for ease (needs '.' and package=)
            module = importlib.import_module("." + module_name, package=__package__)
            cls._orm_model_cls = getattr(module, class_name)
        return func(*args, **kwargs)

    return wrapper


class BaseMeta(ABCMeta):
    cls_registry: dict[str, 'BaseModel'] = {}

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
            mcs.cls_registry[cls_name] = new_cls
        # all classes must be dataclasses
        new_cls = dataclass(repr=False)(new_cls)
        return new_cls


class BaseModel(metaclass=BaseMeta):
    guid: UUID = field(init=False, compare=False, kw_only=True, default_factory=uuid.uuid1)
    tags: str = field(compare=False, kw_only=True, default="")
    _saved: bool = field(init=False, compare=False, default=False)  # tracks if the object is saved in the db
    _orm_model: str = field(init=False, compare=False, default=None)
    _orm_model_cls: Type[Model] = field(init=False, compare=False, default=None)
    _orm_instance: Model = field(init=False, compare=False, default=None)  # tracks the corresponding ORM instance

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} object {self.guid}"

    def __post_init__(self):
        self._validate()

    def _validate(self):
        for field_ in self._get_fields():
            type_ = field_.type
            if isinstance(type_, str):
                type_ = BaseMeta.cls_registry[type_]
            if issubclass(type_, Validator):
                continue
            value = getattr(self, field_.name, None)
            if value is not None and not isinstance(value, type_):
                raise TypeError(f"Expected {field_.name} to be of type {field_.type}.")

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

    def _get_fields(self):
        return tuple(f for f in fields(self) if not f.name.startswith("_"))

    @staticmethod
    def _get_orm_field_names(orm_instance):
        return tuple(f.name for f in orm_instance._meta.fields)

    @classmethod
    def get_field_names(cls):
        return tuple(f.name for f in fields(cls) if not f.name.startswith("_"))

    @classmethod
    def _get_all_field_names(cls):
        """
        Returns a list of all field names from a dataclass, including properties.
        """
        fields_ = []
        for name, value in inspect.getmembers(cls):
            if isinstance(value, property):
                fields_.append(name)
        return tuple(fields_) + cls.get_field_names()

    @property
    def saved(self):
        return self._saved

    @require_model_import
    def save(self, **kwargs):
        if self._orm_instance is None:
            self._orm_instance = self._orm_model_cls()
        cls_fields = self._get_all_field_names()
        model_fields = self._get_orm_field_names(self._orm_instance)
        for field_ in cls_fields:
            if field_ in model_fields:
                value = getattr(self, field_, None)
                # skip setting value if None
                if value is not None:
                    if isinstance(value, BaseModel):
                        value = value._orm_instance.__class__.objects.get(guid=value.guid)
                    setattr(self._orm_instance, field_, value)
        self._orm_instance.save(**kwargs)
        self._saved = True

    def delete(self, **kwargs):
        if not self._saved:
            raise ObjectNotSavedError(extra_detail="Delete failed")
        self._saved = False
        count, _ = self._orm_instance.delete(**kwargs)
        return count

    @classmethod
    @require_model_import
    def get(cls, **kwargs):
        obj = cls()
        # todo: handle modelDoesNotExist here and raise own exception added to Metaclass.
        orm_instance = cls._orm_model_cls.objects.get(**kwargs)
        cls_fields = cls.get_field_names()
        model_fields = cls._get_orm_field_names(orm_instance)

        for field_ in model_fields:
            if field_ in cls_fields:
                value = getattr(orm_instance, field_, None)
                # don't check for None here, we need everything as-is
                if isinstance(value, Model):
                    #  todo: convert relation objects to BaseModel types
                    #  get the corresponding field type from the dataclass and create objects
                    value = ...
                setattr(obj, field_, value)

        obj._orm_instance = orm_instance
        obj._saved = True
        return obj

    @classmethod
    @require_model_import
    def create(cls, **kwargs):
        pass

    @classmethod
    @require_model_import
    def filter(cls, **kwargs):
        pass

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
            cleaned_value = self.validate(value)
        setattr(obj, self._name, cleaned_value)

    @abstractmethod
    def validate(self, value):
        pass
