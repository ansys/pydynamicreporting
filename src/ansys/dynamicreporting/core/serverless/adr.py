from collections.abc import Iterable
import copy
from datetime import datetime
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from typing import Any
import uuid
import warnings

from django.core.management import call_command
from django.core.management.utils import get_random_secret_key
from django.db import DatabaseError, connections
from django.http import HttpRequest

from ..adr_utils import get_logger
from ..common_utils import get_install_info
from ..constants import DOCKER_REPO_URL
from ..docker_support import DockerLauncher
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
    """
    Ansys Dynamic Reporting (ADR) class.

    This class is used to interact with the Ansys Dynamic Reporting (ADR) system.
    It provides methods to create, query, and manipulate items and templates without the need
    for a web server.

    Parameters
    ----------
        ansys_installation: str, optional
            The path to the Ansys installation. If not provided, the class will attempt to
            detect the installation path.
        ansys_version: int, optional
            The version of Ansys to use. If not provided, the class will attempt to detect the
            version.
        db_directory: str, optional
            The directory to store the database. If not provided, the class will attempt to
            detect the database directory.
        databases: dict, optional
            A dictionary of database configurations. This is required if the 'db_directory' option
            is not provided.
        media_directory: str, optional
            The directory to store the media files. If not provided, the class will attempt to
            detect the media directory.
        static_directory: str, optional
            The directory to store the static files. If not provided, the class will attempt to
            detect the static directory.
        media_url: str, optional
            The URL to use for the media files. If not provided, the class will use the default
            URL.
        static_url: str, optional
            The URL to use for the static files. If not provided, the class will use the default
            URL.
        debug: bool, optional
            If True, the class will run in debug mode. If not provided, the class will run in
            production mode.
        opts: dict, optional
            A dictionary of environment variables to set.
        request: HttpRequest, optional
            The request object. This is required if the class is used in the context of a web server.
        logfile: str, optional
            The path to the log file. If not provided, the class will log to the console.
        docker_image: str, optional
            The Docker image to use. This is required if the 'ansys_installation' option is set to
            'docker'. If not provided, the class will use the default Docker image.
        in_memory: bool, optional
            If True, the class will run in in-memory mode. If not provided, the class will require a
            database directory or databases to be specified.

    Raises
    ------
    ADRException
        Raised if there is an error during the setup process.
    DatabaseMigrationError
        Raised if there is an error during the database migration process.
    GeometryMigrationError
        Raised if there is an error during the geometry migration process.
    ImproperlyConfiguredError
        Raised if the configuration is incorrect.
    InvalidAnsysPath
        Raised if the Ansys installation path is invalid.
    InvalidPath
        Raised if the path is invalid.
    StaticFilesCollectionError
        Raised if there is an error during the static files collection process.

    Examples
    --------
    >>> install_loc = "C:\\Program Files\\ANSYS Inc\v252"
    >>> db_dir = "C:\\DBs\\docex"
    >>> from ansys.dynamicreporting.core.serverless import ADR, String
    >>> adr = ADR(ansys_installation=install_loc, db_directory=db_dir, static_directory=f"{doc_ex_dir}\\static")
    >>> adr.setup(collect_static=True)
    >>> item = adr.create_item(String, name="intro_text", content="It's alive!", tags="dp=dp227 section=intro", source="sls-test")
    >>> template = adr.create_template(BasicLayout, name="Serverless Simulation Report", parent=None, tags="dp=dp227")
    >>> template.set_filter("A|i_tags|cont|dp=dp227;")
    >>> template.save()
    >>> html_content = adr.render_report(name="Serverless Simulation Report", context={}, item_filter="A|i_tags|cont|dp=dp227;")
    """

    _instance = None  # singleton instance
    _is_setup = False  # setup flag

    def __new__(cls, *args, **kwargs):
        """Ensure that only one instance of the class is created"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        *,
        ansys_installation: str | None = None,
        ansys_version: int | None = None,
        db_directory: str | None = None,
        databases: dict | None = None,
        media_directory: str | None = None,
        static_directory: str | None = None,
        media_url: str | None = None,
        static_url: str | None = None,
        debug: bool | None = None,
        opts: dict | None = None,
        request: HttpRequest | None = None,
        logfile: str | None = None,
        docker_image: str = DOCKER_REPO_URL,
        in_memory: bool = False,
    ) -> None:
        self._db_directory = None
        self._media_directory = None
        self._static_directory = None
        self._media_url = media_url
        self._static_url = static_url
        self._debug = debug
        self._request = request  # passed when used in the context of a webserver.
        self._session = None
        self._dataset = None
        self._logger = get_logger(logfile)
        self._tmp_dirs = []
        self._in_memory = in_memory

        if opts is None:
            opts = {}
        os.environ.update(opts)

        # database configuration
        if self._in_memory:
            self._databases = {
                "default": {
                    "ENGINE": "sqlite3",
                    "NAME": ":memory:",
                }
            }
        else:
            self._databases = databases or {}

        # check the database directory
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

                os.environ["CEI_NEXUS_LOCAL_DB_DIR"] = str(db_directory)
            elif "CEI_NEXUS_LOCAL_DB_DIR" in os.environ:
                self._db_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_DB_DIR"])
            else:
                raise ImproperlyConfiguredError(
                    "A database must be specified using either the 'db_directory'"
                    " or the 'databases' option."
                )

        if self._in_memory:
            tmp_media_dir = tempfile.TemporaryDirectory()
            self._media_directory = self._check_dir(Path(tmp_media_dir.name))
            tmp_static_dir = tempfile.TemporaryDirectory()
            self._static_directory = self._check_dir(Path(tmp_static_dir.name))
            self._tmp_dirs.extend([tmp_media_dir, tmp_static_dir])
        else:
            # check the media directory
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
            # check the static directory
            if static_directory is not None:
                self._static_directory = self._check_dir(static_directory)
                os.environ["CEI_NEXUS_LOCAL_STATIC_DIR"] = str(static_directory)
            elif "CEI_NEXUS_LOCAL_STATIC_DIR" in os.environ:
                self._static_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_STATIC_DIR"])

        # check the Ansys installation
        if ansys_installation == "docker":
            try:
                docker_launcher = DockerLauncher(image_url=docker_image)
                docker_launcher.pull_image()
                docker_launcher.create_container()
            except Exception as e:
                error_message = f"Error during Docker setup: {str(e)}\n"
                self._logger.error(error_message)
                raise ADRException(error_message)

            # create a temporary directory to store the installation
            tmp_install_dir = tempfile.TemporaryDirectory()
            self._tmp_dirs.append(tmp_install_dir)
            try:
                # Copy the installation from the container to the host
                docker_launcher.copy_to_host("/Nexus/CEI", dest=tmp_install_dir.name)
            except Exception as e:  # pragma: no cover
                error_message = f"Error copying the installation from the container: {str(e)}"
                self._logger.error(error_message)
                raise ADRException(error_message)

            # Clean up the Docker container
            try:
                docker_launcher.cleanup(close=True)
            except Exception as e:
                self._logger.warning(f"Problem shutting down container/service: {str(e)}")

            # Set the installation directory
            install_dir, self._ansys_version = get_install_info(
                ansys_installation=tmp_install_dir.name, ansys_version=ansys_version
            )
        else:
            # local installation
            install_dir, self._ansys_version = get_install_info(
                ansys_installation=ansys_installation, ansys_version=ansys_version
            )
        if install_dir is None:
            raise InvalidAnsysPath(f"Unable to detect an installation in: {ansys_installation}")
        self._ansys_installation = Path(install_dir)

    @staticmethod
    def _check_dir(dir_):
        dir_path = Path(dir_) if not isinstance(dir_, Path) else dir_
        if not dir_path.exists() or not dir_path.is_dir():
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    @staticmethod
    def _migrate_db(db):
        try:  # upgrade databases
            call_command("migrate", "--no-input", "--database", db, "--verbosity", 0)
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

    @classmethod
    def get_database_config(cls) -> dict | None:
        """Get the database configuration."""
        if not cls._is_setup:
            return None
        from django.conf import settings

        return settings.DATABASES

    def _is_sqlite(self, database: str) -> bool:
        return not self._in_memory and "sqlite" in self.get_database_config().get(database, {}).get(
            "ENGINE", ""
        )

    def _get_db_path(self, database: str) -> str:
        if self._is_sqlite(database):
            return self.get_database_config().get(database, {}).get("NAME", "")
        return ""

    @classmethod
    def get_instance(cls) -> "ADR":
        """Retrieve the configured ADR instance."""
        if cls._instance is None:
            raise RuntimeError("There is no ADR instance available. Instantiate ADR first.")
        return cls._instance

    @classmethod
    def ensure_setup(cls):
        """
        Check if the singleton ADR instance has been set up.
        Raise a RuntimeError if not.
        """
        if cls._instance is None or not cls._is_setup:
            raise RuntimeError("ADR has not been set up. Instantiate ADR first and call setup().")

    def setup(self, collect_static: bool = False) -> None:
        """
        Set up the ADR environment.

        Parameters
        ----------
        collect_static : bool, optional
            If True, collect the static files to static_directory. Default is False.

        Raises
        ------
        ImportError
            Raised if there is an error importing the required modules or the Ansys installation.
        DatabaseMigrationError
            Raised if there is an error during the database migration process.
        GeometryMigrationError
            Raised if there is an error during the geometry migration process.
        ImproperlyConfiguredError
            Raised if the configuration is incorrect.
        StaticFilesCollectionError
            Raised if there is an error during the static files collection process.

        Returns
        -------
        None
        """

        if ADR._is_setup:
            raise RuntimeError("ADR has already been configured. setup() can only be called once.")
        # look for enve, but keep it optional.
        try:
            import enve
        except ImportError:
            pf = "winx64" if platform.system().startswith("Wind") else "linx64"
            dirs_to_check = [
                # Path('C:/Program Files/ANSYS Inc/v252/CEI').parent is "C:/Program Files/ANSYS Inc/v252"
                self._ansys_installation.parent / "commonfiles" / "ensight_components" / pf,
                # for older versions < 2025R1
                self._ansys_installation.parent
                / "commonfiles"
                / "fluids"
                / "ensight_components"
                / pf,
            ]
            try:
                for enve_path in dirs_to_check:
                    try:
                        enve_path.resolve(strict=True)
                        sys.path.append(str(enve_path))
                        break
                    except OSError:
                        continue

                from enve_common import enve
            except ImportError as e:
                self._logger.warning(
                    f"Failed to import 'enve' from the Ansys installation. Animations may not render correctly: {e}"
                )
                warnings.warn(
                    f"Failed to import 'enve' from the Ansys installation. Animations may not render correctly: {e}",
                    ImportWarning,
                )

        # import hack
        try:
            adr_path = (
                self._ansys_installation / f"nexus{self._ansys_version}" / "django"
            ).resolve(strict=True)
            sys.path.append(str(adr_path))
            from ceireports import settings_serverless
        except (ImportError, OSError) as e:
            raise ImportError(f"Failed to import ADR from the Ansys installation: {e}")

        overrides = {}
        for setting in dir(settings_serverless):
            if setting.isupper():
                overrides[setting] = getattr(settings_serverless, setting)

        if self._debug is not None:
            overrides["DEBUG"] = self._debug

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

        # in-memory media storage
        if self._in_memory:
            overrides.update(
                {
                    "DEFAULT_FILE_STORAGE": "django.core.files.storage.InMemoryStorage",
                    "FILE_UPLOAD_HANDLERS": [
                        "django.core.files.uploadhandler.MemoryFileUploadHandler"
                    ],
                    "FILE_UPLOAD_MAX_MEMORY_SIZE": 1 * 10**9,  # 1 GB
                }
            )

        # Check for Linux TZ issue
        report_utils.apply_timezone_workaround()

        # django configuration
        try:
            from django.conf import settings

            if not settings.configured:
                import django

                settings.configure(**overrides)
                django.setup()
        except Exception as e:
            raise ImproperlyConfiguredError(extra_detail=str(e))

        # migrations
        database_config = self.get_database_config()
        if database_config:
            for db in database_config:
                self._migrate_db(db)
        elif self._db_directory is not None:
            self._migrate_db("default")

        # geometry migration
        try:
            from data.geofile_rendering import do_geometry_update_check

            do_geometry_update_check(self._logger.info)
        except Exception as e:
            raise GeometryMigrationError(extra_detail=str(e))

        # collect static files
        if collect_static:
            if self._static_directory is None:
                raise ImproperlyConfiguredError(
                    "The 'static_directory' option must be specified to collect static files."
                )
            try:
                call_command("collectstatic", "--no-input", "--verbosity", 0)
            except Exception as e:
                raise StaticFilesCollectionError(extra_detail=str(e))

        # setup is complete
        ADR._is_setup = True

        # create session and dataset w/ defaults
        self._session = Session.create()
        self._dataset = Dataset.create()

    def close(self):
        """Ensure that everything is cleaned up"""
        # close db connections
        try:
            connections.close_all()
        except DatabaseError:  # pragma: no cover
            pass
        # cleanup temp files
        for tmp_dir in self._tmp_dirs:
            tmp_dir.cleanup()

    def backup_database(
        self,
        output_directory: str | Path = ".",
        *,
        database: str = "default",
        compress: bool = False,
        ignore_primary_keys: bool = False,
    ) -> None:
        if self._in_memory:
            raise ADRException("Backup is not available in in-memory mode.")
        if database != "default" and database not in self.get_database_config():
            raise ADRException(f"{database} must be configured first using the 'databases' option.")
        target_dir = Path(output_directory).resolve(strict=True)
        if not target_dir.is_dir():
            raise InvalidPath(extra_detail=f"'{output_directory}' is not a valid directory.")
        # call django management command to dump the database
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_path = target_dir / f"backup_{timestamp}.json{'.gz' if compress else ''}"
        args = [
            "dumpdata",
            "--all",
            "--database",
            database,
            "--output",
            str(file_path),
            "--verbosity",
            0,
            "--natural-foreign",
        ]
        if ignore_primary_keys:
            args.append("--natural-primary")
        try:
            call_command(*args)
        except Exception as e:
            raise ADRException(f"Backup failed: {e}")

    def restore_database(self, input_file: str | Path, *, database: str = "default") -> None:
        if database != "default" and database not in self.get_database_config():
            raise ADRException(f"{database} must be configured first using the 'databases' option.")
        backup_file = Path(input_file).resolve(strict=True)
        if not backup_file.is_file():
            raise InvalidPath(extra_detail=f"{input_file} is not a valid file.")
        # call django management command to load the database
        try:
            call_command(
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
    def is_setup(self) -> bool:
        return ADR._is_setup

    @property
    def ansys_installation(self) -> str:
        return str(self._ansys_installation)

    @property
    def ansys_version(self) -> int:
        return self._ansys_version

    @property
    def db_directory(self) -> str:
        db_dir = self._db_directory or Path(self._get_db_path("default")).parent
        return str(db_dir)

    @property
    def media_directory(self) -> str:
        return str(self._media_directory)

    @property
    def static_directory(self) -> str:
        return str(self._static_directory)

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

    def create_item(self, item_type: type[Item], **kwargs: Any) -> Item:
        if not issubclass(item_type, Item):
            raise TypeError(f"{item_type.__name__} is not a subclass of Item")
        if not kwargs:
            raise ADRException("At least one keyword argument must be provided to create the item.")
        return item_type.create(
            session=kwargs.pop("session", self._session),
            dataset=kwargs.pop("dataset", self._dataset),
            **kwargs,
        )

    @staticmethod
    def create_template(template_type: type[Template], **kwargs: Any) -> Template:
        if not issubclass(template_type, Template):
            raise TypeError(f"{template_type.__name__} is not a subclass of Template")
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

    @staticmethod
    def get_report(**kwargs) -> Template:
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        try:
            return Template.get(parent=None, **kwargs)
        except Exception as e:
            raise ADRException(f"Report not found: {e}")

    @staticmethod
    def get_reports(*, fields: list | None = None, flat: bool = False) -> ObjectSet | list:
        # return list of reports by default.
        # if fields are mentioned, return value list
        out = Template.filter(parent=None)
        if fields:
            out = out.values_list(*fields, flat=flat)
        return out

    def get_list_reports(self, r_type: str | None = "name") -> ObjectSet | list:
        supported_types = ("name", "report")
        if r_type and r_type not in supported_types:
            raise ADRException(f"r_type must be one of {supported_types}")
        if not r_type or r_type == "report":
            return self.get_reports()
        # if r_type == "name":
        return self.get_reports(
            fields=[
                r_type,
            ],
            flat=True,
        )

    def render_report(
        self, *, context: dict | None = None, item_filter: str = "", **kwargs: Any
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
            raise ADRException(f"Report rendering failed: {e}")

    @staticmethod
    def query(
        query_type: Session | Dataset | type[Item] | type[Template],
        *,
        query: str = "",
        **kwargs: Any,
    ) -> ObjectSet:
        if not issubclass(query_type, (Item, Template, Session, Dataset)):
            raise TypeError(
                f"'{query_type.__name__}' is not a type of Item, Template, Session, or Dataset"
            )
        return query_type.find(query=query, **kwargs)

    @staticmethod
    def create_objects(
        objects: list | ObjectSet,
        **kwargs: Any,
    ) -> int:
        if not isinstance(objects, Iterable):
            raise ADRException("objects must be an iterable")
        count = 0
        for obj in objects:
            if obj.db and kwargs.get("using", "default") != obj.db:  # pragma: no cover
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
        object_type: Session | Dataset | type[Item] | type[Template],
        target_database: str,
        *,
        query: str = "",
        target_media_dir: str | Path = "",
        test: bool = False,
    ) -> int:
        """
        This copies a selected collection of objects from one database to another.

        GUIDs are preserved and any referenced session and dataset objects are copied as
        well.
        """
        source_database = "default"  # todo: allow for source database to be specified

        if not issubclass(object_type, (Item, Template, Session, Dataset)):
            raise TypeError(
                f"'{object_type.__name__}' is not a type of Item, Template, Session, or Dataset"
            )

        database_config = self.get_database_config()
        if target_database not in database_config or source_database not in database_config:
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
                        media_dir = Path(target_media_dir).resolve(strict=True)
                    elif self._is_sqlite(target_database):
                        media_dir = self._check_dir(
                            Path(self._get_db_path(target_database)).parent / "media"
                        )
                    else:
                        raise ADRException(
                            "'target_media_dir' argument must be specified because one of the objects"
                            " contains media to copy.'"
                        )
                # try to load sessions, datasets - since it is possible they are shared
                # and were saved already.
                try:
                    session = Session.get(guid=item.session.guid, using=target_database)
                except Session.DoesNotExist:
                    session = Session.create(**item.session.as_dict(), using=target_database)
                try:
                    dataset = Dataset.get(guid=item.dataset.guid, using=target_database)
                except Dataset.DoesNotExist:
                    dataset = Dataset.create(**item.dataset.as_dict(), using=target_database)
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
