from abc import ABC, ABCMeta, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from enum import Enum
import importlib
import inspect
from itertools import chain
import shlex
from typing import Any, get_args, get_origin
import uuid

from django.core.exceptions import (
    FieldDoesNotExist,
    FieldError,
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    ValidationError,
)
from django.db import DataError
from django.db.models import Model, QuerySet
from django.db.models.base import subclass_exception
from django.db.models.manager import Manager
from django.db.utils import IntegrityError as DBIntegrityError

from ..exceptions import (
    IntegrityError,
    InvalidFieldError,
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
        except (FieldError, FieldDoesNotExist, ValidationError, DataError) as e:
            raise InvalidFieldError(
                extra_detail=f"One or more fields set or accessed are invalid: {e}"
            )

    return wrapper


def is_generic_class(cls):
    return not isinstance(cls, type) or get_origin(cls) is not None


def get_uuid():
    return str(uuid.uuid1())


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
                props = namespace["_properties"]
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
            add_exception_to_cls(
                "IntegrityError",
                IntegrityError,
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
    guid: str = field(compare=False, kw_only=True, default_factory=get_uuid)
    tags: str = field(compare=False, kw_only=True, default="")
    _saved: bool = field(
        init=False, compare=False, default=False
    )  # tracks if the object is saved in the db
    _orm_model: str = field(init=False, compare=False, default=None)
    _orm_model_cls: type[Model] = field(init=False, compare=False, default=None)
    _orm_instance: Model = field(
        init=False, compare=False, default=None
    )  # tracks the corresponding ORM instance

    # check if ADR is set up before creating instances
    def __new__(cls, *args, **kwargs):
        try:
            from .adr import ADR

            ADR.ensure_setup()
        except RuntimeError as e:
            raise RuntimeError(
                f"ADR must be set up before creating instances of '{cls.__name__}': {e}"
            )
        return super().__new__(cls)

    def __eq__(self, other: object) -> bool:
        """Models are equal iff they are the same concrete class and have the same GUID."""
        if self is other:
            return True
        if not isinstance(other, BaseModel):
            return NotImplemented
        return (self.__class__ is other.__class__) and (self.guid == other.guid)

    def __hash__(self) -> int:
        """Hash by concrete class + GUID so instances are usable in sets/dicts."""
        return hash((self.__class__, self.guid))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.guid}>"

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}: {self.guid}>"

    def __post_init__(self):
        self._validate_field_types()
        self._orm_instance = self.__class__._orm_model_cls()

    def _validate_field_types(self):
        for field_name, field_type in self._get_field_names(with_types=True):
            value = getattr(self, field_name, None)
            if value is None:
                continue
            # Type inference
            # convert strings to classes
            if isinstance(field_type, str):
                type_cls = self.__class__._cls_registry[field_type]
            else:
                type_cls = field_type
            # Validators will validate by themselves, so this can be ignored.
            # Will only work when the type is a proper class
            if not is_generic_class(type_cls) and issubclass(type_cls, Validator):
                continue
            # 'Generic' class types
            if get_origin(type_cls) is not None:
                # get any args
                args = get_args(type_cls)
                # update with the origin type
                type_cls = get_origin(type_cls)
                # validate with the 'arg' type:
                # eg: 'Template' in list['Template']
                if args:
                    content_type = args[0]
                    if isinstance(content_type, str):
                        content_type = self.__class__._cls_registry[content_type]
                    if isinstance(value, Iterable):
                        for elem in value:
                            if not isinstance(elem, content_type):
                                raise TypeError(
                                    f"Expected '{field_name}' to contain items of type '{content_type}'."
                                )
            if not isinstance(value, type_cls):
                raise TypeError(f"Expected '{field_name}' to be of type '{type_cls}'.")

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

    def _get_var_field_names(self, include_private=False):
        fields_ = []
        for f in vars(self).keys():
            if not include_private and f.startswith("_"):
                continue
            fields_.append(f)
        return tuple(fields_)

    @classmethod
    def _get_prop_field_names(cls):
        """Returns a list of all field names from a dataclass, including properties."""
        property_fields = []
        for name, value in inspect.getmembers(cls):
            if isinstance(value, property):
                property_fields.append(name)
        return tuple(property_fields)

    @property
    def saved(self) -> bool:
        return self._saved

    @property
    def _orm_saved(self) -> bool:
        return not self._orm_instance._state.adding

    @property
    def _orm_db(self) -> str:
        return self._orm_instance._state.db

    @property
    def db(self):
        return self._orm_db

    def as_dict(self, recursive=False) -> dict[str, Any]:
        out_dict = {}
        # use a combination of vars and fields
        cls_fields = set(self._get_field_names() + self._get_var_field_names())
        for field_ in cls_fields:
            if field_.startswith("_"):
                continue
            value = getattr(self, field_, None)
            if value is None:  # skip and use defaults
                continue
            if isinstance(value, list) and recursive:
                # convert to guids
                value = [obj.guid for obj in value]
            out_dict[field_] = value
        return out_dict

    def _prepare_for_save(self, **kwargs):
        self._saved = False

        target_db = kwargs.pop("using", "default")
        cls_fields = self._get_field_names() + self._get_prop_field_names()
        model_fields = self._get_orm_field_names(self._orm_instance)
        for field_ in cls_fields:
            if field_ not in model_fields:
                continue
            value = getattr(self, field_, None)
            if value is None:  # skip and use defaults
                continue
            if isinstance(value, list):
                objs = [obj._orm_instance for obj in value]
                try:
                    getattr(self._orm_instance, field_).add(*objs)
                except (ObjectDoesNotExist, ValueError) as e:
                    if value:
                        obj_cls = value[0].__class__
                        raise obj_cls.NotSaved(extra_detail=str(e))
                    else:
                        raise ValueError(str(e))
            else:
                if isinstance(value, BaseModel):  # relations
                    try:
                        value = value._orm_instance.__class__.objects.using(target_db).get(
                            guid=value.guid
                        )
                    except ObjectDoesNotExist as e:
                        raise value.__class__.DoesNotExist(
                            extra_detail=f"Object with guid '{value.guid}'" f" does not exist: {e}"
                        )
                # for all others
                setattr(self._orm_instance, field_, value)

        return self

    def reinit(self):
        self._saved = False
        self._orm_instance = self.__class__._orm_model_cls()

    @handle_field_errors
    def save(self, **kwargs):
        try:
            obj = self._prepare_for_save(**kwargs)
            obj._orm_instance.save(**kwargs)
        except DBIntegrityError as e:
            raise self.__class__.IntegrityError(
                extra_detail=f"Save failed for object with guid '{self.guid}': {e}"
            )
        except Exception as e:
            raise e
        else:
            obj._saved = True

    def delete(self, **kwargs):
        if not self._saved:
            raise self.__class__.NotSaved(
                extra_detail=f"Delete failed for object with guid '{self.guid}'."
            )
        count, _ = self._orm_instance.delete(**kwargs)
        self._saved = False
        return count

    @classmethod
    def from_db(cls, orm_instance, parent=None):
        cls_fields = dict(cls._get_field_names(with_types=True, include_private=True))
        model_fields = cls._get_orm_field_names(orm_instance)
        obj = cls.__new__(cls)  # Bypass __init__ to skip validation
        for field_ in model_fields:
            if field_ in cls_fields:
                attr = field_
            elif f"_{field_}" in cls_fields:
                # serialize some private fields as well.
                attr = f"_{field_}"
            else:
                continue
            # don't check for None here, we need everything as-is
            value = getattr(orm_instance, field_, None)
            field_type = cls_fields[attr]
            # We must also serialize 'related' fields
            if isinstance(value, Model):
                # convert the value to a type supported by the proxy
                # for string definitions of the dataclass type, example - parent: 'Template'
                if isinstance(field_type, str):
                    type_ = cls._cls_registry[field_type]
                else:
                    type_ = field_type
                if issubclass(cls, type_) and parent is not None:
                    # Same hierarchy means there is a parent-child relation.
                    # We avoid loading the parent object again and use the one passed
                    # from the previous 'from_db' load to prevent infinite recursion.
                    value = parent
                else:
                    value = type_.from_db(value)
            elif isinstance(value, Manager):
                type_ = get_origin(field_type)
                args = get_args(field_type)
                # todo: move this check to the metaclass
                if type_ is None or not issubclass(type_, Iterable) or len(args) != 1:
                    raise TypeError(
                        f"The field '{attr}' in the dataclass must be a generic iterable"
                        f" class containing exactly one type argument. For example: "
                        f"list['Template'] or tuple['Template']."
                    )
                content_type = args[0]
                if isinstance(content_type, str):
                    content_type = cls._cls_registry[content_type]
                qs = value.all()
                # content_type must match orm model class
                if content_type._orm_model_cls != qs.model:
                    raise TypeError(
                        f"The field '{attr}' is of '{field_type}' but the "
                        f"actual content is of type '{qs.model}'"
                    )
                if qs:
                    obj_set = ObjectSet(
                        _model=content_type, _orm_model=qs.model, _orm_queryset=qs, _parent=obj
                    )
                    value = type_(obj_set)
                else:
                    value = type_()
            else:
                if value is not None and not isinstance(value, field_type):
                    value = field_type(value)

            # set the orm value on the proxy object
            setattr(obj, attr, value)

        obj._orm_instance = orm_instance
        obj._saved = True
        return obj

    @classmethod
    @handle_field_errors
    def create(cls, **kwargs):
        target_db = kwargs.pop("using", "default")
        obj = cls(**kwargs)
        obj.save(force_insert=True, using=target_db)
        return obj

    @classmethod
    @handle_field_errors
    def get(cls, **kwargs):
        """Get an object from the database using the ORM model."""
        # convert basemodel instances to orm instances
        for key, value in kwargs.items():
            if isinstance(value, BaseModel):
                kwargs[key] = value._orm_instance
        try:
            orm_instance = cls._orm_model_cls.objects.using(kwargs.pop("using", "default")).get(
                **kwargs
            )
        except ObjectDoesNotExist:
            raise cls.DoesNotExist
        except MultipleObjectsReturned:
            raise cls.MultipleObjectsReturned

        return cls.from_db(orm_instance)

    @classmethod
    @handle_field_errors
    def filter(cls, **kwargs) -> "ObjectSet":
        for key, value in kwargs.items():
            if isinstance(value, BaseModel):
                kwargs[key] = value._orm_instance
        qs = cls._orm_model_cls.objects.using(kwargs.pop("using", "default")).filter(**kwargs)
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)

    @classmethod
    @handle_field_errors
    def find(cls, query="", **kwargs) -> "ObjectSet":
        qs = cls._orm_model_cls.find(query=query, **kwargs)
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)

    def get_tags(self) -> str:
        return self.tags

    def set_tags(self, tag_str: str) -> None:
        self.tags = tag_str

    def add_tag(self, tag: str, value: str | None = None) -> None:
        self.rem_tag(tag)
        tags = shlex.split(self.get_tags())
        if value:
            tags.append(tag + "=" + str(value))
        else:
            tags.append(tag)
        self._rebuild_tags(tags)

    def rem_tag(self, tag: str) -> None:
        tags = shlex.split(self.get_tags())
        for t in tags:
            if t == tag or t.split("=")[0] == tag:
                tags.remove(t)
        self._rebuild_tags(tags)

    def remove_tag(self, tag: str) -> None:
        self.rem_tag(tag)


@dataclass(eq=False, order=False, repr=False)
class ObjectSet:
    _model: type[BaseModel] = field(compare=False, default=None)
    _obj_set: list[BaseModel] = field(init=True, compare=False, default_factory=list)
    _saved: bool = field(init=False, compare=False, default=False)
    _orm_model: type[Model] = field(compare=False, default=None)
    _orm_queryset: QuerySet = field(compare=False, default=None)
    _parent: BaseModel = field(compare=False, default=None)

    def __post_init__(self):
        if self._orm_queryset is None:
            return
        self._saved = True
        self._obj_set = [
            self._model.from_db(instance, parent=self._parent) for instance in self._orm_queryset
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
        count = 0
        for obj in self._obj_set:
            obj.delete()
            count += 1
        self._orm_queryset.delete()
        self._obj_set = []
        self._saved = False
        return count

    def values_list(self, *fields, flat=False):
        if flat and len(fields) > 1:
            raise ValueError(
                "'flat' is not valid when values_list is called with more than one field."
            )
        ret = []
        for obj in self._obj_set:
            ret.append(tuple(getattr(obj, f, None) for f in fields))
        return list(chain.from_iterable(ret)) if flat else ret


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
        cleaned_value = self.process(value, obj)
        setattr(obj, self._name, cleaned_value)

    @abstractmethod
    def process(self, value, obj):
        pass  # pragma: no cover


class StrEnum(str, Enum):
    """Enum with a str mixin."""

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value
