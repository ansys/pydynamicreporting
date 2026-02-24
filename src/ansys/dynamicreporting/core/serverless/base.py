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

"""Core serverless base models and utilities.

This module provides the foundational abstractions used by the serverless ADR
API:

* :class:`BaseModel` – a lightweight dataclass wrapper around an ADR ORM
  model, with validation, tagging, and CRUD helpers.
* :class:`ObjectSet` – a simple collection wrapper around query results that
  materializes :class:`BaseModel` instances.
* :class:`Validator` – a descriptor base class for value validation and
  normalization on assignment.
* :class:`StrEnum` – a convenience enum that behaves like :class:`str` for
  serialization.

The :class:`BaseMeta` metaclass wires dataclasses to their corresponding ORM
models, lazily loads ORM classes, and injects model-specific exception types.
"""

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
from django.db.models.manager import Manager
from django.db.utils import IntegrityError as DBIntegrityError

from ..exceptions import (
    IntegrityError,
    InvalidFieldError,
    MultipleObjectsReturnedError,
    ObjectDoesNotExistError,
    ObjectNotSavedError,
)


def _add_exception_to_cls(name, base, cls, parents, module):
    """Attach a Django-style exception subclass to a model class.

    This mirrors Django's pattern of adding exceptions such as
    ``DoesNotExist`` and ``MultipleObjectsReturned`` on the model itself,
    but uses the serverless ADR exception hierarchy as a base.
    """
    base_exceptions = tuple(getattr(p, name) for p in parents if hasattr(p, name))
    exception_cls = type(name, base_exceptions or (base,), {"__module__": module})
    setattr(cls, name, exception_cls)


def _handle_field_errors(func):
    """Decorator that normalizes common Django field-related errors.

    Any :class:`FieldError`, :class:`FieldDoesNotExist`,
    :class:`ValidationError`, or :class:`DataError` raised by the wrapped
    function is converted into :class:`InvalidFieldError` with additional
    context. This keeps higher-level APIs free from ORM-specific exceptions.
    """

    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (FieldError, FieldDoesNotExist, ValidationError, DataError) as e:
            raise InvalidFieldError(
                extra_detail=f"One or more fields set or accessed are invalid: {e}"
            )

    return _wrapper


def _is_generic_class(cls):
    """Return ``True`` if ``cls`` is a typing generic or not a real class.

    This is used to distinguish types like ``list['Template']`` from
    concrete classes when validating dataclass field values.

    """
    return not isinstance(cls, type) or get_origin(cls) is not None


def _get_uuid():
    """Return a new UUIDv1 value as a string.

    This is used as the default GUID for :class:`BaseModel` instances.

    """
    return str(uuid.uuid1())


class BaseMeta(ABCMeta):
    """Metaclass that wires dataclass models to their Django ORM counterparts.

    Responsibilities
    ----------------
    * Registers all subclasses of :class:`BaseModel` in a class registry.
    * Optionally materializes extra dataclass fields defined via
      ``_properties`` on the class body.
    * Lazily imports and caches the underlying Django ORM model declared
      via the ``_orm_model`` string.
    * Attaches model-specific exception classes such as ``DoesNotExist``
      and ``IntegrityError`` using the serverless ADR exception hierarchy.
    """

    _cls_registry: dict[str, type["BaseModel"]] = {}
    _model_cls_registry: dict[str, type[Model]] = {}

    def __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ) -> type:
        """Create a new :class:`BaseModel` subclass and register it.

        Parameters
        ----------
        cls_name : str
            Name of the class being created.
        bases : tuple of type
            Base classes for the new class.
        namespace : dict
            Namespace (attributes and methods) of the new class.
        **kwargs : Any
            Additional keyword arguments passed by the metaclass
            machinery.

        Returns
        -------
        type
            Newly created class, wrapped as a dataclass and registered
            in the class registry if it extends :class:`BaseModel`.
        """
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
            _add_exception_to_cls(
                "DoesNotExist",
                ObjectDoesNotExistError,
                new_cls,
                parents,
                namespace.get("__module__"),
            )
            _add_exception_to_cls(
                "NotSaved", ObjectNotSavedError, new_cls, parents, namespace.get("__module__")
            )
            _add_exception_to_cls(
                "MultipleObjectsReturned",
                MultipleObjectsReturnedError,
                new_cls,
                parents,
                namespace.get("__module__"),
            )
            _add_exception_to_cls(
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
        """Resolve attributes, lazily loading the ORM model when needed.

        The ``_orm_model_cls`` attribute is populated on first access by
        importing the dotted ``_orm_model`` path. The resolved Django model
        class is cached in :attr:`_model_cls_registry`.
        """
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
    """Base dataclass model that proxies a Django ORM model.

    Each subclass should define:

    * ``_orm_model`` – dotted path to the underlying Django model class.
    * Matching dataclass fields for the Django model fields.

    Instances of :class:`BaseModel` are validated on construction, can be
    saved and deleted via the underlying ORM instance, and expose helper
    methods for querying and tag management.

    The ADR setup is enforced at construction time via
    :meth:`ansys.dynamicreporting.core.serverless.adr.ADR.ensure_setup`.
    """

    guid: str = field(compare=False, kw_only=True, default_factory=_get_uuid)
    """Globally unique identifier for this object."""

    tags: str = field(compare=False, kw_only=True, default="")
    """Tag string used to group and filter objects."""

    _saved: bool = field(
        init=False,
        compare=False,
        default=False,
    )  # tracks if the object is saved in the db
    _orm_model: str | None = field(init=False, compare=False, default=None)
    _orm_model_cls: type[Model] | None = field(init=False, compare=False, default=None)
    _orm_instance: Model | None = field(
        init=False,
        compare=False,
        default=None,
    )  # tracks the corresponding ORM instance

    # check if ADR is set up before creating instances
    def __new__(cls, *args, **kwargs):
        """Enforce ADR setup before creating a :class:`BaseModel` instance."""
        try:
            from .adr import ADR

            ADR.ensure_setup()
        except RuntimeError as e:
            raise RuntimeError(
                f"ADR must be set up before creating instances of '{cls.__name__}': {e}"
            )
        return super().__new__(cls)

    def __eq__(self, other: object) -> bool:
        """Compare models by concrete class and GUID."""
        if self is other:
            return True
        if not isinstance(other, BaseModel):
            return NotImplemented
        return (self.__class__ is other.__class__) and (self.guid == other.guid)

    def __hash__(self) -> int:
        """Hash by concrete class and GUID for use in sets and dicts."""
        return hash((self.__class__, self.guid))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.guid}>"

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}: {self.guid}>"

    def __post_init__(self):
        """Run post-init validation and instantiate the ORM instance."""
        self._validate_field_types()
        orm_model_cls = self.__class__._orm_model_cls
        if orm_model_cls is None:
            raise RuntimeError(f"ORM model is not configured for '{self.__class__.__name__}'.")
        self._orm_instance = orm_model_cls()

    def _validate_field_types(self):
        """Validate dataclass field values against their declared types.

        This performs:

        * Resolution of string-based type annotations via the class
          registry (for example ``'Template'``).
        * Special handling for :class:`Validator` subclasses, which are
          responsible for their own validation.
        * Validation of generic collection types, ensuring that all
          elements match the declared content type.

        """
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
            if not _is_generic_class(type_cls) and issubclass(type_cls, Validator):
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
        """Return a tag token with quotes if it contains whitespace."""
        if " " in input_str and input_str[0] != "'":
            return "'" + input_str + "'"
        return input_str

    def _rebuild_tags(self, tags):
        """Rebuild the internal tag string from a list of tokens."""
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
        """Return the list of ORM field names for the given instance."""
        return tuple(f.name for f in orm_instance._meta.get_fields())

    @classmethod
    def _get_field_names(cls, with_types=False, include_private=False):
        """Return the dataclass field names (and optionally types)."""
        fields_ = []
        for f in dataclass_fields(cls):
            if not include_private and f.name.startswith("_"):
                continue
            fields_.append((f.name, f.type) if with_types else f.name)
        return tuple(fields_)

    def _get_var_field_names(self, include_private=False):
        """Return attribute names from ``vars(self)`` (optionally including private)."""
        fields_ = []
        for f in vars(self).keys():
            if not include_private and f.startswith("_"):
                continue
            fields_.append(f)
        return tuple(fields_)

    @classmethod
    def _get_prop_field_names(cls):
        """Return all property names defined on the class."""
        property_fields = []
        for name, value in inspect.getmembers(cls):
            if isinstance(value, property):
                property_fields.append(name)
        return tuple(property_fields)

    @property
    def saved(self) -> bool:
        """Whether this object has been successfully saved to the database."""
        return self._saved

    @property
    def _orm_saved(self) -> bool:
        """Whether the underlying ORM instance has been saved."""
        if self._orm_instance is None:
            return False
        return not self._orm_instance._state.adding

    @property
    def _orm_db(self) -> str | None:
        """Database alias used by the underlying ORM instance."""
        if self._orm_instance is None:
            return None
        return self._orm_instance._state.db

    @property
    def db(self):
        """Database alias in which this object is stored."""
        return self._orm_db

    def as_dict(self, recursive=False) -> dict[str, Any]:
        """Serialize the model into a plain dictionary.

        The resulting mapping contains dataclass fields plus any
        additional instance attributes (excluding private attributes and
        attributes with value ``None``).

        If ``recursive`` is ``True``, list-valued attributes are
        converted into lists of GUIDs instead of lists of objects.

        Parameters
        ----------
        recursive : bool, default: False
            If ``True``, recursively serialize lists of related objects
            as lists of GUIDs.

        Returns
        -------
        dict of str to Any
            Mapping of attribute name to value.
        """
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
        """Populate the ORM instance from the dataclass fields.

        This method copies all matching dataclass fields and properties
        onto the underlying ORM instance, resolving relations and many-
        to-many fields where appropriate.
        """
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
                            extra_detail=f"Object with guid '{value.guid}' does not exist: {e}"
                        )
                # for all others
                setattr(self._orm_instance, field_, value)

        return self

    def reinit(self):
        """Reset the in-memory ORM state for this object.

        This marks the object as unsaved and replaces the underlying ORM
        instance with a fresh one of the same model class. Dataclass
        fields remain unchanged.
        """
        self._saved = False
        orm_model_cls = self.__class__._orm_model_cls
        if orm_model_cls is None:
            raise RuntimeError(f"ORM model is not configured for '{self.__class__.__name__}'.")
        self._orm_instance = orm_model_cls()

    @_handle_field_errors
    def save(self, **kwargs):
        """Save this object to the database.

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

    def delete(self):
        """Delete this object from the database.

        Returns
        -------
        int
            Number of ORM rows deleted.

        Raises
        ------
        NotSaved
            If the object has not been previously saved.
        """
        if not self._saved:
            raise self.__class__.NotSaved(
                extra_detail=f"Delete failed for object with guid '{self.guid}'."
            )
        if self._orm_instance is None:
            raise self.__class__.NotSaved(
                extra_detail=f"Delete failed for object with guid '{self.guid}'."
            )
        count, _ = self._orm_instance.delete()
        self._saved = False
        return count

    @classmethod
    def _from_db(cls, orm_instance, parent=None, **kwargs):
        """Create a :class:`BaseModel` instance from a Django ORM instance.

        This method bypasses ``__init__`` to avoid re-validation and
        instead copies fields directly from the ORM object, converting
        relations into :class:`BaseModel` instances or :class:`ObjectSet`
        collections as needed.
        """
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
                    value = type_._from_db(value)
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
                        _model=content_type,
                        _orm_model=qs.model,
                        _orm_queryset=qs,
                        _parent=obj,
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
    @_handle_field_errors
    def create(cls, **kwargs):
        """Create and save a new object in a single step.

        Parameters
        ----------
        **kwargs
            Field values for the new instance. The ``using`` argument,
            if present, is consumed to determine the target database and
            is not passed to the constructor.

        Returns
        -------
        BaseModel
            Newly created and saved instance.

        Raises
        ------
        InvalidFieldError
            If invalid field names or values are supplied.
        IntegrityError
            If a database integrity error occurs during save.
        """
        target_db = kwargs.pop("using", "default")
        obj = cls(**kwargs)
        obj.save(force_insert=True, using=target_db)
        return obj

    @classmethod
    @_handle_field_errors
    def get(cls, **kwargs):
        """Retrieve a single object from the database.

        Parameters
        ----------
        **kwargs
            Keyword arguments to configure the database operation.
            Eg: The special ``using`` argument can be supplied to select a database alias.

        Returns
        -------
        BaseModel
            Single matching instance.

        Raises
        ------
        DoesNotExist
            If no matching row is found.
        MultipleObjectsReturned
            If more than one row matches the query.
        InvalidFieldError
            If the filter arguments reference invalid fields.
        """
        if cls._orm_model_cls is None:
            raise RuntimeError(f"ORM model is not configured for '{cls.__name__}'.")
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

        return cls._from_db(orm_instance)

    @classmethod
    @_handle_field_errors
    def filter(cls, **kwargs) -> "ObjectSet":
        """Return a collection of objects matching the given filters.

        Parameters
        ----------
        **kwargs
            Keyword arguments to filter the queryset. Eg: `tags="key=value"`.
            The special ``using`` argument can be supplied to select a database alias.

        Returns
        -------
        ObjectSet
            Collection wrapper around the resulting queryset.
        """
        if cls._orm_model_cls is None:
            raise RuntimeError(f"ORM model is not configured for '{cls.__name__}'.")
        filter_kwargs = {}
        db_alias = kwargs.pop("using", "default")
        for key, value in kwargs.items():
            if isinstance(value, BaseModel):
                filter_kwargs[key] = value._orm_instance
            else:
                filter_kwargs[key] = value
        qs = cls._orm_model_cls.objects.using(db_alias).filter(**filter_kwargs)
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)

    @classmethod
    @_handle_field_errors
    def find(cls, query="") -> "ObjectSet":
        """Search for objects using an ADR query string.

        Parameters
        ----------
        query : str, default: ""
            ADR Query string.

        Returns
        -------
        ObjectSet
            Collection of results wrapped as :class:`BaseModel`
            instances.
        """
        if cls._orm_model_cls is None:
            raise RuntimeError(f"ORM model is not configured for '{cls.__name__}'.")
        find_method = getattr(cls._orm_model_cls, "find", None)
        if find_method is None:
            raise AttributeError(f"ORM model '{cls._orm_model_cls}' does not implement 'find'.")
        qs = find_method(query=query)
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)

    def get_tags(self) -> str:
        """Return the raw tag string stored on this object.

        Returns
        -------
        str
            Space-separated tag string, where individual tokens are
            ``key`` or ``key=value`` (with quoting for values that
            contain whitespace).
        """
        return self.tags

    def set_tags(self, tag_str: str) -> None:
        """Replace all tags with the given tag string.

        Parameters
        ----------
        tag_str : str
            New space-separated tag string to store.
        """
        self.tags = tag_str

    def add_tag(self, tag: str, value: str | None = None) -> None:
        """Add or update a single tag.

        If a tag with the same key already exists, it is removed before
        adding the new one.

        Parameters
        ----------
        tag : str
            Tag key.
        value : str or None, optional
            Tag value. If omitted, the tag is stored as a bare key
            without ``=value``.
        """
        self.rem_tag(tag)
        tags = shlex.split(self.get_tags())
        if value:
            tags.append(tag + "=" + str(value))
        else:
            tags.append(tag)
        self._rebuild_tags(tags)

    def rem_tag(self, tag: str) -> None:
        """Remove a tag by key, if it exists.

        Both ``tag`` and ``tag=value`` forms are removed if present.

        Parameters
        ----------
        tag : str
            Tag key to remove.
        """
        tags = shlex.split(self.get_tags())
        for t in tags:
            if t == tag or t.split("=")[0] == tag:
                tags.remove(t)
        self._rebuild_tags(tags)

    def remove_tag(self, tag: str) -> None:
        """Alias for :meth:`rem_tag` for backwards compatibility.

        Parameters
        ----------
        tag : str
            Tag key to remove.
        """
        self.rem_tag(tag)


@dataclass(eq=False, order=False, repr=False)
class ObjectSet:
    """Collection wrapper around a queryset of :class:`BaseModel` objects.

    An :class:`ObjectSet` encapsulates a Django queryset and eagerly
    materializes it into a list of :class:`BaseModel` instances. It
    behaves like a simple list for iteration, indexing, and truth
    testing, while providing extra helpers such as bulk deletion and
    value extraction.
    """

    _model: type[BaseModel] | None = field(compare=False, default=None)
    _obj_set: list[BaseModel] = field(init=True, compare=False, default_factory=list)
    _saved: bool = field(init=False, compare=False, default=False)
    _orm_model: type[Model] | None = field(compare=False, default=None)
    _orm_queryset: QuerySet | None = field(compare=False, default=None)
    _parent: BaseModel | None = field(compare=False, default=None)

    def __post_init__(self):
        """Materialize ORM instances into :class:`BaseModel` objects."""
        if self._orm_queryset is None or self._model is None:
            return
        self._saved = True
        self._obj_set = [
            self._model._from_db(instance, parent=self._parent) for instance in self._orm_queryset
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
        """Whether this object set currently reflects saved ORM rows."""
        return self._saved

    def delete(self):
        """Delete all objects in this set from the database.

        The individual objects' :meth:`BaseModel.delete` methods are
        called, followed by deletion of any remaining rows via the
        underlying queryset.

        Returns
        -------
        int
            Number of objects deleted.
        """
        count = 0
        for obj in self._obj_set:
            obj.delete()
            count += 1
        if self._orm_queryset is not None:
            self._orm_queryset.delete()
        self._obj_set = []
        self._saved = False
        return count

    def values_list(self, *fields, flat=False):
        """Return a list of tuples of field values for objects in the set.

        Parameters
        ----------
        *fields : str
            Attribute names to extract from each object.
        flat : bool, default: False
            If ``True``, and exactly one field is requested, return a
            simple list of values instead of a list of 1-tuples.

        Returns
        -------
        list
            List of tuples of field values, or a flat list of values if
            ``flat=True`` and a single field is requested.

        Raises
        ------
        ValueError
            If ``flat`` is ``True`` but more than one field name is
            provided.
        """
        if flat and len(fields) > 1:
            raise ValueError(
                "'flat' is not valid when values_list is called with more than one field."
            )
        ret = []
        for obj in self._obj_set:
            ret.append(tuple(getattr(obj, f, None) for f in fields))
        return list(chain.from_iterable(ret)) if flat else ret


class Validator(ABC):
    """Descriptor base class for value validation and normalization.

    Subclasses implement :meth:`process` to validate and transform values
    before they are stored on the owning object. A ``default`` value can
    be provided for cases where no explicit value has been set.
    """

    def __init__(self, *, default=None):
        """Initialize the validator."""
        self._default = default

    def __set_name__(self, owner, name):
        """Record the private attribute name used for storage."""
        self._name = "_" + name

    def __get__(self, obj, obj_type=None):
        """Return the validated value from the owning object."""
        if obj is None:
            return self._default

        return getattr(obj, self._name, self._default)

    def __set__(self, obj, value):
        """Validate and store a new value on the owning object."""
        cleaned_value = self.process(value, obj)
        setattr(obj, self._name, cleaned_value)

    @abstractmethod
    def process(self, value, obj):
        """Validate and normalize a raw value.

        Subclasses must implement this method to perform type coercion,
        range checks, or any other validation required before storing
        the value.
        """
        pass  # pragma: no cover


class StrEnum(str, Enum):
    """Enum with a :class:`str` mixin for easy serialization.

    The value of each enum member is its string representation, which
    makes it convenient for use in JSON, HTML attributes, and other
    text-based contexts.
    """

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value
