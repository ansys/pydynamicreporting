from collections.abc import Iterable
import copy
from datetime import datetime
import os
from pathlib import Path
import platform
import shutil
import sys
from typing import Any, Optional, Type, Union
import uuid

import django
from django.core import management
from django.core.management.utils import get_random_secret_key
from django.http import HttpRequest

from .. import DEFAULT_ANSYS_VERSION
from ..adr_utils import get_logger
from ..exceptions import (
    ADRException,
    DatabaseMigrationError,
    GeometryMigrationError,
    ImproperlyConfiguredError,
    InvalidAnsysPath,
    InvalidPath,
    StaticFilesCollectionError,
)
from ..utils import report_utils
from ..utils.geofile_processing import file_is_3d_geometry, rebuild_3d_geometry
from .base import ObjectSet
from .item import Dataset, Item, Session
from .template import Template


class ADR:
    def __init__(
        self,
        ansys_installation: str,
        *,
        db_directory: Optional[str] = None,
        databases: Optional[dict] = None,
        media_directory: Optional[str] = None,
        static_directory: Optional[str] = None,
        media_url: Optional[str] = None,
        static_url: Optional[str] = None,
        debug: Optional[bool] = None,
        opts: Optional[dict] = None,
        request: Optional[HttpRequest] = None,
        logfile: Optional[str] = None,
    ) -> None:
        self._db_directory = None
        self._databases = databases or {}
        self._media_directory = None
        self._static_directory = None
        self._media_url = media_url
        self._static_url = static_url
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
                try:
                    self._db_directory = self._check_dir(db_directory)
                except InvalidPath:
                    # dir creation
                    self._db_directory = Path(db_directory)
                    self._db_directory.mkdir(parents=True, exist_ok=True)
                    # media dir
                    (self._db_directory / "media").mkdir(parents=True, exist_ok=True)
                    # secret key
                    if "CEI_NEXUS_SECRET_KEY" not in os.environ:
                        # Make a random string that could be used as a secret key for the database
                        secret_key = get_random_secret_key()
                        os.environ["CEI_NEXUS_SECRET_KEY"] = secret_key
                        # And make a target file (.nexdb) for auto launching of the report viewer...
                        with open(self._db_directory / "view_report.nexdb", "w") as f:
                            f.write(secret_key)
                else:
                    # check if there is a sqlite db in the directory
                    db_files = list(self._db_directory.glob("*.sqlite3"))
                    if not db_files:
                        raise InvalidPath(
                            extra_detail="No sqlite3 database found in the directory. Remove the existing directory if"
                            " you would like to create a new database."
                        )

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
            os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"] = str(self._media_directory.parent)
        # the env var here is actually the parent directory that contains the media directory
        elif "CEI_NEXUS_LOCAL_MEDIA_DIR" in os.environ:
            self._media_directory = (
                self._check_dir(os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"]) / "media"
            )
        elif self._db_directory is not None:  # fallback to the db dir
            self._media_directory = self._check_dir(self._db_directory / "media")
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

    def _is_sqlite(self, database: str) -> bool:
        return "sqlite" in self._databases.get(database, {}).get("ENGINE", "")

    def _get_db_dir(self, database: str) -> str:
        if self._is_sqlite(database):
            return self._databases.get(database, {}).get("NAME", "")
        return ""

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

        raise InvalidAnsysPath(
            f"Unable to detect an installation in: {[str(d) for d in dirs_to_check]}"
        )

    def _check_dir(self, dir_):
        dir_path = Path(dir_) if not isinstance(dir_, Path) else dir_
        if not dir_path.exists() or not dir_path.is_dir():
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    def _migrate_db(self, db):
        try:  # upgrade databases
            management.call_command("migrate", "--no-input", "--database", db, "--verbosity", 0)
        except Exception as e:
            raise DatabaseMigrationError(extra_detail=str(e))
        else:
            # create users/groups only for the default database
            if db != "default":
                return

            from django.contrib.auth.models import Group, Permission, User

            if not User.objects.filter(is_superuser=True).exists():
                user = User.objects.create_superuser("nexus", "", "cei")
                # include the nexus group (with all permissions)
                nexus_group, created = Group.objects.get_or_create(name="nexus")
                if created:
                    nexus_group.permissions.set(Permission.objects.all())
                nexus_group.user_set.add(user)

    def setup(self, collect_static: bool = False) -> None:
        from django.conf import settings

        if settings.configured:
            raise RuntimeError("ADR has already been configured. setup() can be called only once.")

        # import hack
        try:
            adr_path = (
                self._ansys_installation / f"nexus{self._ansys_version}" / "django"
            ).resolve(strict=True)
            sys.path.append(str(adr_path))
            from ceireports import settings_serverless
        except (ImportError, OSError) as e:
            raise ImportError(f"Failed to import from the Ansys installation: {e}")

        overrides = {}
        for setting in dir(settings_serverless):
            if setting.isupper():
                overrides[setting] = getattr(settings_serverless, setting)

        if self._debug is not None:
            overrides["DEBUG"] = self._debug

        if self._media_directory is not None:
            overrides["MEDIA_ROOT"] = str(self._media_directory)

        if self._static_directory is not None:
            overrides["STATIC_ROOT"] = str(self._static_directory)

        # relative URLs: By default, ADR serves static files from the URL /static/
        # and media files from the URL /media/. These can be changed using the
        # static_url and media_url options. URLs must be relative and start and end with
        # a forward slash.
        if self._media_url is not None:
            if not self._media_url.startswith("/") or not self._media_url.endswith("/"):
                raise ImproperlyConfiguredError(
                    "The 'media_url' option must be a relative URL and start and end with a forward slash."
                    " Example: '/media/'"
                )
            overrides["MEDIA_URL"] = self._media_url

        if self._static_url is not None:
            if not self._static_url.startswith("/") or not self._static_url.endswith("/"):
                raise ImproperlyConfiguredError(
                    "The 'static_url' option must be a relative URL and start and end with a forward slash."
                    " Example: '/static/'"
                )
            overrides["STATIC_URL"] = self._static_url

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

        # Check for Linux TZ issue
        report_utils.apply_timezone_workaround()

        try:
            settings.configure(**overrides)
            django.setup()
        except Exception as e:
            raise ImproperlyConfiguredError(extra_detail=str(e))

        # migrations
        if self._databases:
            for db in self._databases:
                self._migrate_db(db)
        elif self._db_directory is not None:
            self._migrate_db("default")

        # geometry migration
        try:
            from data.geofile_rendering import do_geometry_update_check

            do_geometry_update_check(self._logger)
        except Exception as e:
            raise GeometryMigrationError(extra_detail=str(e))

        # collect static files
        if collect_static:
            if self._static_directory is None:
                raise ImproperlyConfiguredError(
                    "The 'static_directory' option must be specified to collect static files."
                )
            try:
                management.call_command("collectstatic", "--no-input", "--verbosity", 0)
            except Exception as e:
                raise StaticFilesCollectionError(extra_detail=str(e))

        # create session and dataset w/ defaults if not provided.
        if self._session is None:
            self._session = Session.create()

        if self._dataset is None:
            self._dataset = Dataset.create()

    def backup_database(
        self, output_directory: str = ".", *, database: str = "default", compress=False
    ) -> None:
        if database != "default" and database not in self._databases:
            raise ADRException(f"{database} must be configured first using the 'databases' option.")
        target_dir = Path(output_directory).resolve(strict=True)
        if not target_dir.is_dir():
            raise InvalidPath(extra_detail=f"{output_directory} is not a valid directory.")
        # call django management command to dump the database
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_path = target_dir / f"backup_{timestamp}.json{'.gz' if compress else ''}"
        try:
            management.call_command(
                "dumpdata",
                "--all",
                "--database",
                database,
                "--output",
                str(file_path),
                "--verbosity",
                0,
            )
        except Exception as e:
            raise ADRException(f"Backup failed: {e}")

    def restore_database(self, input_file: str, *, database: str = "default") -> None:
        if database != "default" and database not in self._databases:
            raise ADRException(f"{database} must be configured first using the 'databases' option.")
        backup_file = Path(input_file).resolve(strict=True)
        if not backup_file.is_file():
            raise InvalidPath(extra_detail=f"{input_file} is not a valid file.")
        # call django management command to load the database
        try:
            management.call_command(
                "loaddata",
                str(backup_file),
                "--database",
                database,
                "--ignorenonexistent",
                "--verbosity",
                0,
            )
        except Exception as e:
            raise ADRException(f"Restore failed: {e}")

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
        if not kwargs:
            raise ADRException("At least one keyword argument must be provided to create the item.")
        return item_type.create(
            session=kwargs.pop("session", self._session),
            dataset=kwargs.pop("dataset", self._dataset),
            **kwargs,
        )

    def create_template(self, template_type: Type[Template], **kwargs: Any) -> Template:
        if not issubclass(template_type, Template):
            raise TypeError(f"{template_type} is not valid")
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to create the template."
            )
        template = template_type.create(**kwargs)
        parent = kwargs.get("parent")
        if parent is not None:
            parent.children.append(template)
            parent.save()
        return template

    def get_report(self, **kwargs) -> Template:
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        try:
            return Template.get(parent=None, **kwargs)
        except Exception as e:
            raise e

    def get_reports(
        self, *, fields: Optional[list] = None, flat: bool = False
    ) -> Union[ObjectSet, list]:
        # return list of reports by default.
        # if fields are mentioned, return value list
        try:
            out = Template.filter(parent=None)
            if fields:
                out = out.values_list(*fields, flat=flat)
        except Exception as e:
            raise e

        return out

    def get_list_reports(self, *, r_type: str = "name") -> Union[ObjectSet, list]:
        supported_types = ("name", "report")
        if r_type not in supported_types:
            raise ADRException(f"r_type must be one of {supported_types}")
        if r_type == "name":
            return self.get_reports(
                fields=[
                    r_type,
                ],
                flat=True,
            )
        else:
            return self.get_reports()

    def render_report(
        self, *, context: Optional[dict] = None, item_filter: str = "", **kwargs: Any
    ) -> str:
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        try:
            return Template.get(**kwargs).render(
                request=self._request, context=context, item_filter=item_filter
            )
        except Exception as e:
            raise e

    def query(
        self,
        query_type: Union[Session, Dataset, Type[Item], Type[Template]],
        *,
        query: str = "",
        **kwargs: Any,
    ) -> ObjectSet:
        if not issubclass(query_type, (Item, Template, Session, Dataset)):
            raise TypeError(f"{query_type} is not valid")
        return query_type.find(query=query, **kwargs)

    def create_objects(
        self,
        objects: Union[list, ObjectSet],
        **kwargs: Any,
    ) -> int:
        if not isinstance(objects, Iterable):
            raise ADRException("objects must be an iterable")
        count = 0
        for obj in objects:
            if kwargs.get("using", "default") != obj.db:
                # required if copying across databases
                obj.reinit()
            obj.save(**kwargs)
            count += 1
        return count

    def _copy_template(self, template: Template, **kwargs) -> Template:
        # depth-first walk down from the root, which is 'template',
        # and copy the children along the way.
        out_template = copy.deepcopy(template)
        if out_template.parent is not None:
            parent = out_template.parent
            # parents are always copied first, so they should exist
            out_template.parent = Template.get(
                guid=parent.guid, using=kwargs.get("using", "default")
            )
        out_template.reorder_children()  # preserves legacy code from Server.copy_items
        children = out_template.children
        out_template.children = []
        out_template.reinit()
        out_template.save(**kwargs)
        new_children = []
        for child in children:
            child.parent = out_template
            new_child = self._copy_template(child, **kwargs)
            new_children.append(new_child)
        out_template.children = new_children
        return out_template

    def copy_objects(
        self,
        object_type: Union[Session, Dataset, Type[Item], Type[Template]],
        target_database: str,
        *,
        query: str = "",
        target_media_dir: str = "",
        test: bool = False,
    ) -> int:
        """
        This copies a selected collection of objects from one database to another.

        GUIDs are preserved and any referenced session and dataset objects are copied as
        well.
        """
        source_database = "default"  # todo: allow for source database to be specified

        if not issubclass(object_type, (Item, Template, Session, Dataset)):
            raise TypeError(f"{object_type} is not valid")

        if target_database not in self._databases or source_database not in self._databases:
            raise ADRException(
                f"'{source_database}' and '{target_database}' must be configured first using the 'databases' option."
            )

        objects = self.query(object_type, query=query)
        copy_list = []
        media_dir = None

        if issubclass(object_type, Item):
            for item in objects:
                # check for media dir if item has a physical file
                if getattr(item, "has_file", False) and media_dir is None:
                    if target_media_dir:
                        media_dir = target_media_dir
                    elif self._is_sqlite(target_database):
                        media_dir = self._check_dir(
                            Path(self._get_db_dir(target_database)).parent / "media"
                        )
                    else:
                        raise ADRException(
                            "'target_media_dir' argument must be specified because one of the objects"
                            " contains media to copy.'"
                        )
                # save or load sessions, datasets - since it is possible they are shared
                # and were saved already.
                session, _ = Session.get_or_create(**item.session.as_dict(), using=target_database)
                dataset, _ = Dataset.get_or_create(**item.dataset.as_dict(), using=target_database)
                item.session = session
                item.dataset = dataset
                copy_list.append(item)
        elif issubclass(object_type, Template):
            for template in objects:
                # only copy top-level templates
                if template.parent is not None:
                    raise ADRException("Only top-level templates can be copied.")
                new_template = self._copy_template(template, using=target_database)
                copy_list.append(new_template)
        else:  # sessions, datasets
            copy_list = list(objects)

        if test:
            self._logger.info(f"Copying {len(copy_list)} objects...")
            return len(copy_list)

        try:
            count = self.create_objects(copy_list, using=target_database)
        except Exception as e:
            raise ADRException(f"Some objects could not be copied: {e}")

        # copy media
        if issubclass(object_type, Item) and media_dir is not None:
            for item in objects:
                if not getattr(item, "has_file", False):
                    continue
                shutil.copy(Path(item.content), media_dir)
                file_name = str((media_dir / Path(item.content).name).resolve(strict=True))
                if file_is_3d_geometry(file_name, file_item_only=(item.type == "file")):
                    rebuild_3d_geometry(file_name)

        return count
