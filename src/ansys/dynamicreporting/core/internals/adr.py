import datetime
import os
import re
import shlex
import uuid
from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytz
from django.core import management
from django.db.models import Model
from django.http import HttpRequest
from django.utils import timezone

from ..adr_utils import get_logger, table_attr
from ..exceptions import (
    InvalidAnsysPath,
    AnsysVersionAbsentError,
    ImproperlyConfiguredError,
    DatabaseMigrationError,
    StaticFilesCollectionError,
    InvalidPath
)


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
    _saved: bool = field(init=False, default=False)  # tracks if the object is saved in the db
    _orm_instance: Model = field(init=False, default=None)  # tracks the corresponding ORM instance
    guid: str = field(compare=False, kw_only=True, default_factory=uuid.uuid1)
    tags: str = field(compare=False, kw_only=True, default="")
    date: datetime = field(compare=False, kw_only=True, default_factory=timezone.now)

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

    @abstractmethod
    def create(self):
        pass

    @abstractmethod
    def save(self, *args):
        pass

    @abstractmethod
    def delete(self):
        pass


class Validator(ABC):
    ...


class StringContent(Validator):
    ...


@dataclass(repr=False)
class Item(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    source: str = field(compare=False, kw_only=True, default="")
    type: str = field(compare=False, kw_only=True, default="")

    @abstractmethod
    def set_content(self):
        pass

    @abstractmethod
    def render(self):
        pass

    def create(self):
        ...

    def save(
            self,
            *args,
    ):
        ...

    def delete(self):
        ...


@dataclass(repr=False)
class String(Item):
    content = StringContent()

    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class Text(String):
    ...


@dataclass(repr=False)
class Table(Item):
    _properties: list = field(init=False, default=table_attr)

    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class Plot(Table):
    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class Tree(Item):
    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class Scene(Item):
    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class Image(Item):
    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class HTML(Item):
    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class Animation(Item):
    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class File(Item):
    def render(self):
        pass

    def set_content(self):
        pass


@dataclass(repr=False)
class Session(BaseModel):
    def create(self):
        pass

    def save(self, *args):
        pass

    def delete(self):
        pass

    ...


@dataclass(repr=False)
class Dataset(BaseModel):
    def create(self):
        pass

    def save(self, *args):
        pass

    def delete(self):
        pass

    ...


@dataclass(repr=False)
class Template(BaseModel):
    def create(self):
        pass

    def save(self, *args):
        pass

    def delete(self):
        pass

    def render(self):
        ...

    def export(self):
        ...

    def set_filter(self):
        ...

    def set_params(self):
        ...


class ADR:
    """
        >>> from ansys.dynamicreporting.core import ADR
        >>> opts = { "CEI_NEXUS_DEBUG" : "0",
                     "CEI_NEXUS_SECRET_KEY":"h1kuvl)j#e6_7rbhr&f@_3%)$nle*b8t$82wta*e3wu-(5v$$o",
                     "CEI_NEXUS_LOCAL_DB_DIR":r"C:\cygwin64\home\vrajendr\ogdocex" }
        >>> adr = ADR(r"C:\Program Files (x86)\ANSYSv231", opts = opts)
        >>> first_text = adr.create_item(content="<h1>My Title</h1>This is the first example")
        >>> content = adr.get_report_content()
    """

    def __init__(
            self,
            ansys_installation: str,
            *,
            db_directory: str = None,
            media_directory: str = None,
            static_directory: str = None,
            opts: dict = None,
            request: HttpRequest = None,
            logfile: str = None
    ) -> None:
        self._db_directory = None
        self._media_directory = None
        self._static_directory = None
        self._logger = get_logger(logfile)
        self._request = request  # must be passed when used in the context of a webserver.

        if ansys_installation is None:
            raise InvalidAnsysPath(extra_detail="Please pass a Ansys Installation path")
        # CAVEAT: note that "" will take the current directory
        install_dir = Path(ansys_installation)
        if not os.path.isdir(install_dir):
            raise InvalidAnsysPath(extra_detail=str(install_dir))
        if install_dir.stem != "CEI":
            install_dir = install_dir / "CEI"
        self._ansys_installation = install_dir
        os.environ['CEI_NEXUS_INSTALLATION_DIR'] = str(install_dir)

        # try to get version from install path
        matches = re.search(r".*v([0-9]{3}).*", ansys_installation)
        if matches is None:
            raise AnsysVersionAbsentError
        try:
            self._ansys_version = matches.group(1)
            os.environ["CEI_APEX_SUFFIX"] = self._ansys_version
        except IndexError:
            raise AnsysVersionAbsentError

        if opts is None:
            opts = {}
        os.environ.update(opts)

        if db_directory is not None:
            self._db_directory = self._check_dir(db_directory)
            os.environ["CEI_NEXUS_LOCAL_DB_DIR"] = db_directory
        else:
            if "CEI_NEXUS_LOCAL_DB_DIR" in os.environ:
                self._db_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_DB_DIR"])

        if media_directory is not None:
            self._media_directory = self._check_dir(media_directory)
            os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"] = media_directory
        else:
            if "CEI_NEXUS_LOCAL_MEDIA_DIR" in os.environ:
                self._media_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"])

        if static_directory is not None:
            self._static_directory = self._check_dir(static_directory)
            os.environ["CEI_NEXUS_LOCAL_STATIC_DIR"] = static_directory
        else:
            if "CEI_NEXUS_LOCAL_STATIC_DIR" in os.environ:
                self._static_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_STATIC_DIR"])

        self._configure()

    def _check_dir(self, dir_):
        dir_path = Path(dir_)
        if not dir_path.is_dir():
            self._logger.error(f"Invalid directory path: {dir_}")
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    def _configure(self) -> None:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                              "ansys.dynamicreporting.core.internals.report_framework.settings")
        # django.setup() may only be called once.
        try:
            import django
            django.setup()
        except Exception as e:
            self._logger.error(f"{e}")
            raise ImproperlyConfiguredError(extra_detail=str(e))

        # migrations
        if self._db_directory is not None:
            try:
                management.call_command('migrate', verbosity=0)
            except Exception as e:
                self._logger.error(f"{e}")
                raise DatabaseMigrationError(extra_detail=str(e))
            else:
                from django.contrib.auth.models import User
                from django.contrib.auth.models import Group
                from django.contrib.auth.models import Permission

                if not User.objects.filter(is_superuser=True).exists():
                    user = User.objects.create_superuser("nexus", "", "cei")
                    # include the nexus group (with all permissions)
                    nexus_group, created = Group.objects.get_or_create(name='nexus')
                    if created:
                        nexus_group.permissions.set(Permission.objects.all())
                    nexus_group.user_set.add(user)

        # collectstatic
        if self._static_directory is not None:
            try:
                management.call_command('collectstatic', '--no-input', verbosity=0)
            except Exception as e:
                self._logger.error(f"{e}")
                raise StaticFilesCollectionError(extra_detail=str(e))

    def create_item(self, type, content):
        # pass in name, item type (Enum?), payload and tags
        ...

    def create_template(self):
        # pass in name, parent, template type (Enum), params, filters, properties, HTML header
        ...

    def put_objects(self):
        ...

    def create_session(self):
        ...

    def create_dataset(self):
        ...

    def get_report(self):
        #     take name or guid, return Template obj
        return

    def render_report(self):  # replacement for visualize_report
        ...

    def query(self, query_filter=""):
        ...

    def get_list_reports(self):
        ...
