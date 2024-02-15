import os
import re
import shlex
import uuid
from abc import ABC, abstractmethod, ABCMeta
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Type

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
    guid: str = field(compare=False, kw_only=True, default_factory=uuid.uuid1)
    tags: str = field(compare=False, kw_only=True, default="")
    _saved: bool = field(init=False, compare=False, default=False)  # tracks if the object is saved in the db
    _orm_instance: Model = field(init=False, compare=False, default=None)  # tracks the corresponding ORM instance

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

    @abstractmethod
    def create(self, **kwargs):
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


class StringContent(Validator):
    def validate(self, value):
        pass


class ImageContent(Validator):
    def validate(self, value):
        pass


class AnimContent(Validator):
    def validate(self, value):
        pass


class TableContent(Validator):
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

    def create(self, **kwargs):
        pass

    def save(self):
        self._orm_instance.save()

    def delete(self):
        # todo: delete sessions, datasets
        pass

    @abstractmethod
    def render(self):
        pass


@dataclass(repr=False)
class String(Item):
    _type: str = field(init=False, compare=False, default="string")
    content: StringContent = StringContent()

    def render(self):
        pass


@dataclass(repr=False)
class Text(String):
    pass


@dataclass(repr=False)
class Table(Item):
    content: TableContent = TableContent()
    _type: str = field(init=False, compare=False, default="table")
    _properties: list = field(init=False, default=table_attr)

    def render(self):
        pass


@dataclass(repr=False)
class Plot(Table):
    def render(self):
        pass


@dataclass(repr=False)
class Tree(Item):
    _type: str = field(init=False, compare=False, default="tree")
    content: TreeContent = TreeContent()

    def render(self):
        pass


@dataclass(repr=False)
class Scene(Item):
    _type: str = "scene"
    content: SceneContent = SceneContent()

    def render(self):
        pass


@dataclass(repr=False)
class Image(Item):
    _type: str = field(init=False, compare=False, default="image")
    width: int = field(compare=False, kw_only=True, default=0)
    height: int = field(compare=False, kw_only=True, default=0)
    content: ImageContent = ImageContent()

    def render(self):
        pass


@dataclass(repr=False)
class HTML(Item):
    _type: str = field(init=False, compare=False, default="html")
    content: HTMLContent = HTMLContent()

    def render(self):
        pass


@dataclass(repr=False)
class Animation(Item):
    _type: str = field(init=False, compare=False, default="anim")
    content: AnimContent = AnimContent()

    def render(self):
        pass


@dataclass(repr=False)
class File(Item):
    _type: str = field(init=False, compare=False, default="file")
    content: FileContent = FileContent()

    def render(self):
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

    def create(self, **kwargs):
        pass


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

    def create(self, **kwargs):
        pass


@dataclass(repr=False)
class Template(BaseModel):
    name: str = field(compare=False, kw_only=True, default="")
    params: str = field(compare=False, kw_only=True, default="")
    item_filter: str = field(compare=False, kw_only=True, default="")
    parent: Type['Template'] = field(compare=False, kw_only=True, default=None)
    children: list = field(compare=False, kw_only=True, default_factory=list)
    children_order: str = field(compare=False, kw_only=True, default="")
    master: bool = field(compare=False, kw_only=True, default=True)
    _type: str = field(init=False, compare=False, default="")

    @property
    def type(self):
        return self._type

    def post_init(self):
        from .reports.models import Template as TemplateModel
        self._orm_instance = TemplateModel()

    def create(self, **kwargs):
        pass

    def save(self):
        # todo
        self._orm_instance.save()

    def delete(self):
        # todo: delete children, parents
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
        from ansys.dynamicreporting.core import ADR, Table
        opts = { "CEI_NEXUS_DEBUG" : "0", "CEI_NEXUS_SECRET_KEY":"", "CEI_NEXUS_LOCAL_DB_DIR":r"C:\cygwin64\home\vrajendr\ogdocex" }
        adr = ADR(r"C:\Program Files (x86)\ANSYSv231", opts = opts)
        adr.configure()
        table = adr.create_item(Table, name="table1", content={}, tags="dp=1 part=bumper")
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

    def _check_dir(self, dir_):
        dir_path = Path(dir_)
        if not dir_path.is_dir():
            self._logger.error(f"Invalid directory path: {dir_}")
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    def configure(self, collect_static=False) -> None:
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
        if collect_static and self._static_directory is not None:
            try:
                management.call_command('collectstatic', '--no-input', verbosity=0)
            except Exception as e:
                self._logger.error(f"{e}")
                raise StaticFilesCollectionError(extra_detail=str(e))

    def create_item(self, item_type: Type[Item], **kwargs: Any):
        if not isinstance(item_type, Item):
            raise TypeError(f"{item_type} is not valid")
        item = item_type()
        valid_fields = (f.name for f in fields(item_type) if not f.name.startswith("_"))
        for kwarg, value in kwargs.items():
            if kwarg not in valid_fields:
                detail = f"{item_type.__name__} has no attribute {kwarg}"
                self._logger.error(detail)
                raise AttributeError(detail)
            setattr(item, kwarg, value)
        item.save()
        return item

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

    def query(self, query_type, query_filter=""):
        """
                Query the database.

                .. _Query Expressions: https://nexusdemo.ensight.com/docs/html/Nexus.html?DataItems.html

                Parameters
                ----------
                query_type : str, optional
                    Type of objects to query. The default is ``"Item"``. Options are ``"Item"``,
                    ``"Session"``, and ``"Dataset"``.
                query_filter : str, optional
                    Query string for filtering. The default is ``""``. The syntax corresponds
                    to the syntax for Ansys Dynamic Reporting. For more information, see
                    _Query Expressions in the documentation for Ansys Dynamic Reporting.

                Returns
                -------
                list
                    List of queried objects.

                Examples
                --------
                ::

                    import ansys.dynamicreporting.core as adr
                    adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
                    ret = adr_service.connect()
                    imgs = adr_service.query(query_type='Item', filter='A|i_type|cont|image;')
        """
        ...

    def get_list_reports(self):
        ...
