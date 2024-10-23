import os
import platform
import sys
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional, Type, Union

import django
from django.core import management
from django.http import HttpRequest

from .base import ObjectSet
from .item import Dataset, Item, Session
from .template import Template
from .. import DEFAULT_ANSYS_VERSION
from ..adr_utils import get_logger
from ..exceptions import (
    ADRException,
    DatabaseMigrationError,
    ImproperlyConfiguredError,
    InvalidAnsysPath,
    InvalidPath,
    StaticFilesCollectionError,
)


class ADR:
    def __init__(
        self,
        ansys_installation: str,
        *,
        db_directory: Optional[str] = None,
        databases: Optional[dict] = None,
        media_directory: Optional[str] = None,
        static_directory: Optional[str] = None,
        debug: Optional[bool] = None,
        opts: Optional[dict] = None,
        request: Optional[HttpRequest] = None,
        logfile: Optional[str] = None,
    ) -> None:
        self._db_directory = None
        self._databases = databases or {}
        self._media_directory = None
        self._static_directory = None
        self._debug = debug
        self._request = request  # passed when used in the context of a webserver.
        self._session = None
        self._dataset = None
        self._logger = get_logger(logfile)
        self._ansys_version = DEFAULT_ANSYS_VERSION
        self._ansys_installation = self._get_install_directory(ansys_installation)

        if opts is None:
            opts = {}
        os.environ.update(opts)

        if not self._databases:
            if db_directory is not None:
                self._db_directory = self._check_dir(db_directory)
                os.environ["CEI_NEXUS_LOCAL_DB_DIR"] = db_directory
            elif "CEI_NEXUS_LOCAL_DB_DIR" in os.environ:
                self._db_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_DB_DIR"])
            else:
                raise ImproperlyConfiguredError(
                    "A database must be specified using either the 'db_directory'"
                    " or the 'databases' option."
                )

        if media_directory is not None:
            self._media_directory = self._check_dir(media_directory)
            os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"] = media_directory
        elif "CEI_NEXUS_LOCAL_MEDIA_DIR" in os.environ:
            self._media_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"])
        elif self._db_directory is not None:  # fallback to the db dir
            self._media_directory = self._db_directory
        else:
            raise ImproperlyConfiguredError(
                "A media directory must be specified using either the 'media_directory'"
                " or the 'db_directory' option."
            )

        if static_directory is not None:
            self._static_directory = self._check_dir(static_directory)
            os.environ["CEI_NEXUS_LOCAL_STATIC_DIR"] = static_directory
        elif "CEI_NEXUS_LOCAL_STATIC_DIR" in os.environ:
            self._static_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_STATIC_DIR"])

    def _get_install_directory(self, ansys_installation: str) -> Path:
        dirs_to_check = []
        if ansys_installation:
            # User passed directory
            dirs_to_check.extend([Path(ansys_installation) / "CEI", Path(ansys_installation)])
        else:
            # Environmental variable
            if "PYADR_ANSYS_INSTALLATION" in os.environ:
                env_inst = Path(os.environ["PYADR_ANSYS_INSTALLATION"])
                # Note: PYADR_ANSYS_INSTALLATION is designed for devel builds
                # where there is no CEI directory, but for folks using it in other
                # ways, we'll add that one too, just in case.
                dirs_to_check.extend([env_inst, env_inst / "CEI"])
            # Look for Ansys install using target version number
            if f"AWP_ROOT{self._ansys_version}" in os.environ:
                dirs_to_check.append(Path(os.environ[f"AWP_ROOT{self._ansys_version}"]) / "CEI")
            # Common, default install locations
            if platform.system().startswith("Wind"):
                install_loc = Path(rf"C:\Program Files\ANSYS Inc\v{self._ansys_version}\CEI")
            else:
                install_loc = Path(f"/ansys_inc/v{self._ansys_version}/CEI")

            dirs_to_check.append(install_loc)

        for install_dir in dirs_to_check:
            launch_file = install_dir / "bin" / "adr_template_editor"
            if launch_file.exists():
                return install_dir

        raise InvalidAnsysPath(f"Unable to detect an installation in: {','.join(dirs_to_check)}")

    def _check_dir(self, dir_):
        dir_path = Path(dir_) if not isinstance(dir_, Path) else dir_
        if not dir_path.is_dir():
            self._logger.error(f"Invalid directory path: {dir_}")
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    def _migrate_db(self, db):
        try:  # upgrade databases
            management.call_command("migrate", "--no-input", "--database", db, verbosity=0)
        except Exception as e:
            self._logger.error(f"{e}")
            raise DatabaseMigrationError(extra_detail=str(e))
        else:
            from django.contrib.auth.models import Group, Permission, User

            if not User.objects.using(db).filter(is_superuser=True).exists():
                user = User.objects.using(db).create_superuser("nexus", "", "cei")
                # include the nexus group (with all permissions)
                nexus_group, created = Group.objects.using(db).get_or_create(name="nexus")
                if created:
                    nexus_group.permissions.set(Permission.objects.using(db).all())
                nexus_group.user_set.add(user)

    def setup(self, collect_static: bool = False) -> None:
        from django.conf import settings

        if settings.configured:
            raise RuntimeError("ADR has already been configured. setup() can be called only once.")

        try:
            # import hack
            sys.path.append(
                str(self._ansys_installation / f"nexus{self._ansys_version}" / "django")
            )
            from ceireports import settings_serverless
        except ImportError as e:
            raise ImportError(f"Failed to import from the Ansys installation: {e}")

        overrides = {}
        for setting in dir(settings_serverless):
            if setting.isupper():
                overrides[setting] = getattr(settings_serverless, setting)

        if self._debug is not None:
            overrides["DEBUG"] = self._debug

        if self._databases:
            if "default" not in self._databases:
                raise ImproperlyConfiguredError(
                    """ The 'databases' option must be a dictionary of the following format with
                    a "default" database specified.
                {
                    "default": {
                        "ENGINE": "sqlite3",
                        "NAME": os.path.join(local_db_dir, "db.sqlite3"),
                        "USER": "user",
                        "PASSWORD": "adr",
                        "HOST": "",
                        "PORT": "",
                    }
                    "remote": {
                        "ENGINE": "postgresql",
                        "NAME": "my_database",
                        "USER": "user",
                        "PASSWORD": "adr",
                        "HOST": "127.0.0.1",
                        "PORT": "5432",
                    }
                }
            """
                )
            for db in self._databases:
                engine = self._databases[db]["ENGINE"]
                self._databases[db]["ENGINE"] = f"django.db.backends.{engine}"
            # replace the database config
            overrides["DATABASES"] = self._databases

        try:
            settings.configure(**overrides)
            django.setup()
        except Exception as e:
            self._logger.error(f"{e}")
            raise ImproperlyConfiguredError(extra_detail=str(e))

        # create session and dataset w/ defaults if not provided.
        if self._session is None:
            self._session = Session.create()

        if self._dataset is None:
            self._dataset = Dataset.create()

        # migrations
        if self._databases:
            for db in self._databases:
                self._migrate_db(db)
        elif self._db_directory is not None:
            self._migrate_db("default")

        # collectstatic
        if collect_static and self._static_directory is not None:
            try:
                management.call_command("collectstatic", "--no-input", verbosity=0)
            except Exception as e:
                self._logger.error(f"{e}")
                raise StaticFilesCollectionError(extra_detail=str(e))

    @property
    def session(self) -> Session:
        return self._session

    @property
    def dataset(self) -> Dataset:
        return self._dataset

    @session.setter
    def session(self, session: Session) -> None:
        if not isinstance(session, Session):
            raise TypeError("Must be an instance of type 'Session'")
        self._session = session

    @dataset.setter
    def dataset(self, dataset: Dataset) -> None:
        if not isinstance(dataset, Dataset):
            raise TypeError("Must be an instance of type 'Dataset'")
        self._dataset = dataset

    def set_default_session(self, session: Session) -> None:
        self.session = session

    def set_default_dataset(self, dataset: Dataset) -> None:
        self.dataset = dataset

    @property
    def session_guid(self) -> uuid.UUID:
        """GUID of the session associated with the service."""
        return self._session.guid

    def create_item(self, item_type: Type[Item], **kwargs: Any) -> Item:
        if not issubclass(item_type, Item):
            raise TypeError(f"{item_type} is not valid")
        return item_type.create(session=self._session, dataset=self._dataset, **kwargs)

    def create_template(self, template_type: Type[Template], **kwargs: Any) -> Template:
        if not issubclass(template_type, Template):
            self._logger.error(f"{template_type} is not valid")
            raise TypeError(f"{template_type} is not valid")
        template = template_type.create(**kwargs)
        parent = kwargs.get("parent")
        if parent is not None:
            parent.children.append(template)
            parent.save()
        return template

    def get_report(self, **kwargs) -> Template:
        try:
            return Template.get(master=True, **kwargs)
        except Exception as e:
            self._logger.error(f"{e}")
            raise e

    def get_reports(
        self, fields: Optional[list] = None, flat: bool = False
    ) -> Union[ObjectSet, list]:
        # return list of reports by default.
        # if fields are mentioned, return value list
        try:
            out = Template.filter(master=True)
            if fields:
                out = out.values_list(*fields, flat=flat)
        except Exception as e:
            self._logger.error(f"{e}")
            raise e

        return out

    def get_list_reports(self, r_type: str = "name") -> Union[ObjectSet, list]:
        supported_types = ["name", "report"]
        if r_type not in supported_types:
            raise ADRException(f"r_type must be one of {supported_types}")
        if r_type == "name":
            return self.get_reports([r_type], flat=True)
        else:
            return self.get_reports()

    def render_report(self, context: Optional[dict] = None, query: str = "", **kwargs: Any) -> str:
        try:
            return Template.get(**kwargs).render(
                request=self._request, context=context, query=query
            )
        except Exception as e:
            self._logger.error(f"{e}")
            raise e

    def query(
        self,
        query_type: Union[Session, Dataset, Type[Item], Type[Template]],
        query: str = "",
        **kwargs: Any,
    ) -> ObjectSet:
        if not issubclass(query_type, (Item, Template, Session, Dataset)):
            self._logger.error(f"{query_type} is not valid")
            raise TypeError(f"{query_type} is not valid")
        return query_type.find(query=query, **kwargs)

    @staticmethod
    def create_objects(
        objects: Union[list, ObjectSet],
        **kwargs: Any,
    ) -> int:
        if not isinstance(objects, Iterable):
            raise ADRException("objects must be an iterable")
        count = 0
        for obj in objects:
            obj.save(**kwargs)
            count += 1
        return count

    def _is_sqlite(self, database: str) -> bool:
        return "sqlite" in self._databases[database]["ENGINE"]

    def _get_db_dir(self, database: str) -> str:
        return self._databases[database]["NAME"]
