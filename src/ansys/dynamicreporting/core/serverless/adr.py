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

"""Serverless ADR entry point.

This module defines the :class:`ADR` class, a singleton façade over the
Ansys Dynamic Reporting (ADR) stack that can be used without running the
full ADR/Nexus web server.

It is responsible for:

* Locating and validating an Ansys/Nexus installation (local or Docker).
* Configuring and bootstrapping Django (settings, databases, storage).
* Running migrations and geometry update checks.
* Managing default :class:`Session` and :class:`Dataset` instances.
* Providing high-level helpers to create/query :class:`Item` and
  :class:`Template` objects.
* Rendering and exporting reports to HTML, PDF, and PPTX.
* Copying items/templates across databases and media directories.

Typical usage involves creating a single :class:`ADR` instance, calling
:meth:`ADR.setup`, and then using the high-level methods for items,
templates, and report exports.
"""

from collections.abc import Iterable
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from typing import Any
import uuid
import warnings

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.utils import get_random_secret_key
from django.db import DatabaseError, connections
from django.http import HttpRequest

from ..adr_utils import get_logger
from ..common_utils import get_install_info, populate_template
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
from .html_exporter import ServerlessReportExporter
from .item import Dataset, Item, Session
from .template import PPTXLayout, Template


class ADR:
    """
    Ansys Dynamic Reporting (ADR) class.

    This class provides a high-level API for interacting with ADR without
    running the full web server. It encapsulates Django setup,
    database configuration, media/static configuration, and report
    rendering/export.

    Parameters
    ----------
    ansys_installation : str, optional
        Path to an Ansys/Nexus installation. If ``"docker"``, ADR will
        spin up a Docker container and copy the core bits from it.
        If not provided, :func:`get_install_info` attempts to infer the
        installation location.
    ansys_version : int, optional
        Explicit Ansys version to use. If omitted, ADR tries to infer it
        from the installation content.
    db_directory : str, optional
        Directory for a local SQLite database (and media subdirectory).
        Either this or ``databases`` is required unless ``in_memory=True``.
    databases : dict, optional
        Full Django ``DATABASES`` configuration. If provided, it replaces
        the default SQLite configuration. Must include a ``"default"`` key.
    media_directory : str, optional
        Directory where uploaded media files are stored. If omitted, ADR
        uses ``CEI_NEXUS_LOCAL_MEDIA_DIR`` or falls back to
        ``<db_directory>/media``.
    static_directory : str, optional
        Directory where static files are collected. If omitted, static
        exports are not available.
    media_url : str, default: "/media/"
        Base URL (relative) for serving media files.
    static_url : str, default: "/static/"
        Base URL (relative) for serving static files.
    debug : bool, optional
        Explicit Django DEBUG flag. If omitted, the value from the ADR
        settings module is used.
    opts : dict, optional
        Extra environment variables to inject into :mod:`os.environ`
        before setup.
    request : HttpRequest, optional
        Django request object, useful when ADR is used in a web context.
    logfile : str, optional
        Path to the log file. If omitted, logging typically goes to stderr.
    docker_image : str, optional
        Docker image URL to use when ``ansys_installation="docker"``.
        Defaults to :data:`DOCKER_REPO_URL`.
    in_memory : bool, default: False
        If ``True``, ADR configures an in-memory SQLite database and
        temporary media/static directories, suitable for tests or
        ephemeral usage.

    Raises
    ------
    ADRException
        If Docker bootstrapping or installation copying fails.
    ImproperlyConfiguredError
        If required configuration such as DB or media directories is
        missing or invalid.
    InvalidAnsysPath
        If a valid Ansys installation cannot be located.
    InvalidPath
        If a configured path does not exist and cannot be created.

    Examples
    --------
    Basic local SQLite usage::

        install_loc = r"C:\\Program Files\\ANSYS Inc\\v252"
        db_dir = r"C:\\DBs\\docex"
        from ansys.dynamicreporting.core.serverless import ADR, String, BasicLayout

        adr = ADR(
            ansys_installation=install_loc,
            db_directory=db_dir,
            static_directory=r"C:\\DBs\\static",
        )
        adr.setup(collect_static=True)

        item = adr.create_item(
            String,
            name="intro_text",
            content="It's alive!",
            tags="dp=dp227 section=intro",
            source="sls-test",
        )
        template = adr.create_template(
            BasicLayout,
            name="Serverless Simulation Report",
            parent=None,
            tags="dp=dp227",
        )
        template.set_filter("A|i_tags|cont|dp=dp227;")
        template.save()

        html_content = adr.render_report(
            name="Serverless Simulation Report",
            context={},
            item_filter="A|i_tags|cont|dp=dp227;",
        )
    """

    _instance = None  # Singleton instance
    _is_setup = False  # Global setup flag

    def __new__(cls, *args, **kwargs):
        """Ensure a single ADR instance (singleton pattern)."""
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
        media_url: str = "/media/",
        static_url: str = "/static/",
        debug: bool | None = None,
        opts: dict | None = None,
        request: HttpRequest | None = None,
        logfile: str | None = None,
        docker_image: str = DOCKER_REPO_URL,
        in_memory: bool = False,
    ) -> None:
        # Basic attributes / configuration.
        self._db_directory = None
        self._media_directory = None
        self._static_directory = None
        self._media_url = media_url
        self._static_url = static_url
        self._debug = debug
        self._request = request  # Used when ADR is embedded in a web server.
        self._session: Session | None = None
        self._dataset: Dataset | None = None
        self._logger = get_logger(logfile)
        self._tmp_dirs: list[tempfile.TemporaryDirectory] = []
        self._in_memory = in_memory

        # Apply extra environment variables early.
        if opts is None:
            opts = {}
        os.environ.update(opts)

        # Configure database and media/static directories.
        if self._in_memory:
            # In-memory SQLite database configuration.
            self._databases = {
                "default": {
                    "ENGINE": "sqlite3",
                    "NAME": ":memory:",
                }
            }
            # Ephemeral media/static directories.
            tmp_media_dir = tempfile.TemporaryDirectory()
            self._media_directory = self._check_dir(Path(tmp_media_dir.name))
            tmp_static_dir = tempfile.TemporaryDirectory()
            self._static_directory = self._check_dir(Path(tmp_static_dir.name))
            self._tmp_dirs.extend([tmp_media_dir, tmp_static_dir])
        else:
            self._databases = databases or {}
            # Determine DB directory if databases config is not provided.
            if not self._databases:
                if db_directory is not None:
                    try:
                        self._db_directory = self._check_dir(db_directory)
                    except InvalidPath:
                        # Directory doesn't exist; create it (and "media") plus secret key.
                        self._db_directory = Path(db_directory)
                        self._db_directory.mkdir(parents=True, exist_ok=True)
                        # media dir
                        (self._db_directory / "media").mkdir(parents=True, exist_ok=True)
                        # Create a secret key if not already present.
                        if "CEI_NEXUS_SECRET_KEY" not in os.environ:
                            # Make a random string that could be used as a secret key for the database
                            secret_key = get_random_secret_key()
                            os.environ["CEI_NEXUS_SECRET_KEY"] = secret_key
                            # Auto-launch token for the report viewer.
                            with open(self._db_directory / "view_report.nexdb", "w") as f:
                                f.write(secret_key)

                    os.environ["CEI_NEXUS_LOCAL_DB_DIR"] = str(db_directory)
                elif "CEI_NEXUS_LOCAL_DB_DIR" in os.environ:
                    self._db_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_DB_DIR"])
                else:
                    raise ImproperlyConfiguredError(
                        "A database must be specified using either the 'db_directory'"
                        " or the 'databases' option."
                    )

            # Media directory resolution.
            if media_directory is not None:
                try:
                    self._media_directory = self._check_dir(media_directory)
                except InvalidPath:
                    self._media_directory = Path(media_directory)
                    self._media_directory.mkdir(parents=True, exist_ok=True)

                os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"] = str(self._media_directory.parent)
            # CEI_NEXUS_LOCAL_MEDIA_DIR points to the parent of "media".
            elif "CEI_NEXUS_LOCAL_MEDIA_DIR" in os.environ:
                self._media_directory = (
                    self._check_dir(os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"]) / "media"
                )
            elif self._db_directory is not None:  # fallback to the DB directory
                self._media_directory = self._check_dir(self._db_directory / "media")
            else:
                raise ImproperlyConfiguredError(
                    "A media directory must be specified using either the 'media_directory'"
                    " or the 'db_directory' option."
                )

            # Static directory resolution (only needed for static/export functionality).
            if static_directory is not None:
                try:
                    self._static_directory = self._check_dir(static_directory)
                except InvalidPath:
                    self._static_directory = Path(static_directory)
                    self._static_directory.mkdir(parents=True, exist_ok=True)

                os.environ["CEI_NEXUS_LOCAL_STATIC_DIR"] = str(static_directory)
            elif "CEI_NEXUS_LOCAL_STATIC_DIR" in os.environ:
                self._static_directory = self._check_dir(os.environ["CEI_NEXUS_LOCAL_STATIC_DIR"])

        # Resolve Ansys installation (local or Docker).
        if ansys_installation == "docker":
            # Bootstrap from Docker.
            try:
                docker_launcher = DockerLauncher(image_url=docker_image)
                docker_launcher.pull_image()
                docker_launcher.create_container()
            except Exception as e:
                error_message = f"Error during Docker setup: {str(e)}\n"
                self._logger.error(error_message)
                raise ADRException(error_message)

            # Copy installation from container to a local temp directory.
            tmp_install_dir = tempfile.TemporaryDirectory()
            self._tmp_dirs.append(tmp_install_dir)
            try:
                docker_launcher.copy_to_host("/Nexus/CEI", dest=tmp_install_dir.name)
            except Exception as e:  # pragma: no cover
                error_message = f"Error copying the installation from the container: {str(e)}"
                self._logger.error(error_message)
                raise ADRException(error_message)

            # Tear down container regardless of copy outcome.
            try:
                docker_launcher.cleanup(close=True)
            except Exception as e:
                self._logger.warning(f"Problem shutting down container/service: {str(e)}")

            install_dir, self._ansys_version = get_install_info(
                ansys_installation=tmp_install_dir.name,
                ansys_version=ansys_version,
            )
        else:
            # Local installation.
            install_dir, self._ansys_version = get_install_info(
                ansys_installation=ansys_installation,
                ansys_version=ansys_version,
            )

        if install_dir is None:
            raise InvalidAnsysPath(f"Unable to detect an installation in: {ansys_installation}")
        self._ansys_installation = Path(install_dir)

    @staticmethod
    def _check_dir(dir_):
        """Validate that *dir_* exists and is a directory, returning it as a Path."""
        dir_path = Path(dir_) if not isinstance(dir_, Path) else dir_
        if not dir_path.exists() or not dir_path.is_dir():
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    @staticmethod
    def _migrate_db(db: str) -> None:
        """Run Django migrations for the given database alias.

        For the ``"default"`` database, a ``nexus`` superuser and group
        (with all permissions) is created if none exists.
        """
        try:
            call_command("migrate", "--no-input", "--database", db, "--verbosity", 0)
        except Exception as e:
            raise DatabaseMigrationError(extra_detail=str(e))
        else:
            # Users/groups only for default DB.
            if db != "default":
                return

            from django.contrib.auth.models import Group, Permission, User

            if not User.objects.filter(is_superuser=True).exists():
                user = User.objects.create_superuser("nexus", "", "cei")
                # Create or reuse the 'nexus' group with all permissions.
                nexus_group, created = Group.objects.get_or_create(name="nexus")
                if created:
                    nexus_group.permissions.set(Permission.objects.all())
                nexus_group.user_set.add(user)

    @classmethod
    def get_database_config(cls: type["ADR"], raise_exception: bool = False) -> dict | None:
        """Return the Django ``DATABASES`` configuration, if available.

        Parameters
        ----------
        raise_exception : bool, default: False
            If ``True``, raise :class:`ImproperlyConfiguredError` when
            settings are not yet configured.

        Returns
        -------
        dict or None
            The ``DATABASES`` mapping, or ``None`` if settings are not
            configured and ``raise_exception`` is ``False``.

        Raises
        ------
        ImproperlyConfiguredError
            If Django settings are not configured and
            ``raise_exception=True``.
        """
        try:
            from django.conf import settings

            return settings.DATABASES
        except ImproperlyConfigured as e:
            if raise_exception:
                raise ImproperlyConfiguredError(
                    "The ADR instance has not been set up. Call setup() first."
                ) from e
            return None

    def _is_sqlite(self, database: str) -> bool:
        """Return ``True`` if the given database alias uses a SQLite backend."""
        return not self._in_memory and "sqlite" in self.get_database_config().get(database, {}).get(
            "ENGINE", ""
        )

    def _get_db_path(self, database: str) -> str:
        """Return the filesystem path to the DB file for a SQLite database.

        If the engine is not SQLite, an empty string is returned.
        """
        if self._is_sqlite(database):
            return self.get_database_config().get(database, {}).get("NAME", "")
        return ""

    @classmethod
    def get_instance(cls) -> "ADR":
        """Retrieve the configured ADR singleton instance.

        Returns
        -------
        ADR
            The existing :class:`ADR` instance.

        Raises
        ------
        RuntimeError
            If no instance has been created yet.
        """
        if cls._instance is None:
            raise RuntimeError("There is no ADR instance available. Instantiate ADR first.")
        return cls._instance

    @classmethod
    def ensure_setup(cls) -> None:
        """Verify that :class:`ADR` has been instantiated and :meth:`setup` called.

        Raises
        ------
        RuntimeError
            If no instance exists or setup has not been completed.
        """
        if cls._instance is None or not cls._is_setup:
            raise RuntimeError("ADR has not been set up. Instantiate ADR first and call setup().")

    def setup(self, collect_static: bool = False) -> None:
        """Configure Django and perform ADR initialization.

        This method:

        * Optionally locates and imports the ``enve`` module for geometry.
        * Adds the Nexus Django directory to ``sys.path`` and imports
          the serverless settings module.
        * Builds an overrides dict and calls :func:`django.conf.settings.configure`.
        * Runs Django migrations for all configured databases.
        * Runs geometry migration/update checks.
        * Optionally collects static files to :attr:`_static_directory`.
        * Creates a default :class:`Session` and :class:`Dataset`.

        Parameters
        ----------
        collect_static : bool, optional
            If ``True``, run ``collectstatic`` into :attr:`_static_directory`.

        Raises
        ------
        ImportError
            If the Nexus Django settings could not be imported.
        DatabaseMigrationError
            If migrations fail on any database.
        GeometryMigrationError
            If geometry update checks fail.
        ImproperlyConfiguredError
            If settings or required paths are invalid.
        StaticFilesCollectionError
            If ``collectstatic`` fails.
        """
        if ADR._is_setup:
            raise RuntimeError("ADR has already been configured. setup() can only be called once.")

        # Try to import 'enve', optionally adding paths based on installation layout.
        try:
            import enve  # type: ignore[unused-ignore]
        except ImportError:
            # On Windows/Linux, attempt known Ansys paths.
            if platform.system().lower().startswith("win"):
                dirs_to_check = [
                    # Windows path from commonfiles
                    self._ansys_installation.parent
                    / "commonfiles"
                    / "ensight_components"
                    / "winx64",
                    # Old Windows path
                    self._ansys_installation.parent
                    / "commonfiles"
                    / "fluids"
                    / "ensight_components"
                    / "winx64",
                    # Windows path from apex folder
                    self._ansys_installation
                    / f"apex{self._ansys_version}"
                    / "machines"
                    / "win64"
                    / "CEI",
                ]
            else:  # Linux
                dirs_to_check = [
                    # Linux path from commonfiles
                    self._ansys_installation.parent
                    / "commonfiles"
                    / "ensight_components"
                    / "linx64",
                    # Old Linux path
                    self._ansys_installation.parent
                    / "commonfiles"
                    / "fluids"
                    / "ensight_components"
                    / "linx64",
                    # Linux path from apex folder
                    self._ansys_installation
                    / f"apex{self._ansys_version}"
                    / "machines"
                    / "linux_2.6_64"
                    / "CEI",
                ]

            module_found = False
            for path in dirs_to_check:
                if path.is_dir():
                    sys.path.append(str(path))
                    module_found = True
                    break

            if module_found:
                try:
                    # Newer packaging style.
                    from enve_common import enve  # type: ignore[unused-ignore]
                except ImportError:
                    try:
                        # Fallback to direct import.
                        import enve  # type: ignore[unused-ignore]
                    except ImportError as e:
                        msg = (
                            "Failed to import 'enve' from the Ansys installation. "
                            f"Animations may not render correctly: {e}"
                        )
                        self._logger.warning(msg)
                        warnings.warn(msg, ImportWarning)

        # Add the Nexus Django folder to sys.path and import settings.
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

        # Allow explicit override of DEBUG.
        if self._debug is not None:
            overrides["DEBUG"] = self._debug

        # Override MEDIA_ROOT for serverless mode.
        overrides["MEDIA_ROOT"] = str(self._media_directory)

        # Configure static if a directory is provided.
        if self._static_directory is not None:
            # collect static files to this directory
            overrides["STATIC_ROOT"] = str(self._static_directory)
            # Replace STATICFILES_DIRS to only include the pre-collected directory
            # from the Ansys installation.
            source_static_dir = (
                self._ansys_installation / f"nexus{self._ansys_version}" / "django" / "static"
            )
            if not source_static_dir.exists():
                raise ImproperlyConfiguredError(
                    f"The static files directory '{source_static_dir}' does not exist in the "
                    "installation. Please check your Ansys installation and version."
                )
            overrides["STATICFILES_DIRS"] = [str(source_static_dir)]

        # Enforce relative media/static URLs.
        if self._media_url is not None:
            if not self._media_url.startswith("/") or not self._media_url.endswith("/"):
                raise ImproperlyConfiguredError(
                    "The 'media_url' option must be a relative URL and start and end with a "
                    "forward slash. Example: '/media/'"
                )
            overrides["MEDIA_URL"] = self._media_url

        if self._static_url is not None:
            if not self._static_url.startswith("/") or not self._static_url.endswith("/"):
                raise ImproperlyConfiguredError(
                    "The 'static_url' option must be a relative URL and start and end with a "
                    "forward slash. Example: '/static/'"
                )
            overrides["STATIC_URL"] = self._static_url

        # Inject explicit database configuration if provided.
        if self._databases:
            if "default" not in self._databases:
                raise ImproperlyConfiguredError(
                    """The 'databases' option must be a dictionary of the following format with
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

        # In-memory media storage configuration (no on-disk files).
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

        # Work around Linux timezone issues when needed.
        report_utils.apply_timezone_workaround()

        # Django settings + setup.
        try:
            from django.conf import settings

            if not settings.configured:
                import django

                settings.configure(**overrides)
                django.setup()
        except ImproperlyConfigured as e:
            raise ImproperlyConfiguredError(extra_detail=str(e))

        # Run migrations.
        database_config = self.get_database_config()
        if database_config:
            for db in database_config:
                self._migrate_db(db)
        elif self._db_directory is not None:
            self._migrate_db("default")

        # Geometry migration/update checks.
        try:
            from data.geofile_rendering import do_geometry_update_check

            do_geometry_update_check(self._logger.info)
        except Exception as e:
            raise GeometryMigrationError(extra_detail=str(e))

        # Optionally collect static files.
        if collect_static:
            if self._static_directory is None:
                raise ImproperlyConfiguredError(
                    "The 'static_directory' option must be specified to collect static files."
                )
            try:
                call_command("collectstatic", "--no-input", "--verbosity", 0)
            except Exception as e:
                raise StaticFilesCollectionError(extra_detail=str(e))

        # Mark setup as complete and create default session/dataset.
        ADR._is_setup = True

        # create session and dataset w/ defaults
        self._session = Session.create()
        self._dataset = Dataset.create()

    def close(self) -> None:
        """Close DB connections and clean up any temporary directories.

        This is safe to call multiple times and is typically used when
        tearing down an ADR instance at process exit or the end of a test.
        """
        # Close database connections.
        try:
            connections.close_all()
        except DatabaseError:  # pragma: no cover
            pass

        # Clean up any TemporaryDirectory objects we created.
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
        """Create a JSON (optionally gzipped) backup of an ADR database.

        Parameters
        ----------
        output_directory : str or Path, default: "."
            Directory in which to place the backup file.
        database : str, default: "default"
            ADR database alias to back up.
        compress : bool, default: False
            If ``True``, write a ``.json.gz`` file instead of plain JSON.
        ignore_primary_keys : bool, default: False
            If ``True``, use ``--natural-primary`` to ignore primary key
            values and rely on natural keys instead.

        Raises
        ------
        ADRException
            If in-memory mode is active, the target DB is not configured,
            the output directory is invalid, or the backup command fails.
        """
        if self._in_memory:
            raise ADRException("Backup is not available in in-memory mode.")
        if database != "default" and database not in self.get_database_config(raise_exception=True):
            raise ADRException(f"{database} must be configured first using the 'databases' option.")

        target_dir = Path(output_directory).resolve(strict=True)
        if not target_dir.is_dir():
            raise InvalidPath(extra_detail=f"'{output_directory}' is not a valid directory.")

        # Call Django management command to dump the database.
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
        """Restore a database from a JSON (or JSON.gz) dump file.

        Parameters
        ----------
        input_file : str or Path
            Path to the dump file.
        database : str, default: "default"
            Django database alias to restore into.

        Raises
        ------
        ADRException
            If the target DB is not configured, the file does not exist,
            or the load command fails.
        """
        if database != "default" and database not in self.get_database_config(raise_exception=True):
            raise ADRException(f"{database} must be configured first using the 'databases' option.")

        backup_file = Path(input_file).resolve(strict=True)
        if not backup_file.is_file():
            raise InvalidPath(extra_detail=f"{input_file} is not a valid file.")

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
        """Return ``True`` if :meth:`setup` has been successfully completed."""
        return ADR._is_setup

    @property
    def ansys_installation(self) -> str:
        """Absolute path to the resolved Ansys/Nexus installation."""
        return str(self._ansys_installation)

    @property
    def ansys_version(self) -> int:
        """Detected or configured Ansys version."""
        return self._ansys_version

    @property
    def db_directory(self) -> str:
        """Directory where the primary database resides.

        If :attr:`_db_directory` is not set, this attempts to infer the
        directory from the SQLite DB path associated with the default
        database alias.
        """
        db_dir = self._db_directory or Path(self._get_db_path("default")).parent
        return str(db_dir)

    @property
    def media_directory(self) -> str:
        """Directory where media files (uploads) are stored."""
        return str(self._media_directory)

    @property
    def static_directory(self) -> str:
        """Directory where static files are collected."""
        return str(self._static_directory)

    @property
    def static_url(self) -> str:
        """Relative URL prefix used for static files."""
        return self._static_url

    @property
    def media_url(self) -> str:
        """Relative URL prefix used for media files."""
        return self._media_url

    @property
    def session(self) -> Session:
        """Default :class:`Session` associated with this ADR instance."""
        return self._session

    @property
    def dataset(self) -> Dataset:
        """Default :class:`Dataset` associated with this ADR instance."""
        return self._dataset

    @session.setter
    def session(self, session: Session) -> None:
        """Replace the default :class:`Session`."""
        if not isinstance(session, Session):
            raise TypeError("Must be an instance of type 'Session'")
        self._session = session

    @dataset.setter
    def dataset(self, dataset: Dataset) -> None:
        """Replace the default :class:`Dataset`."""
        if not isinstance(dataset, Dataset):
            raise TypeError("Must be an instance of type 'Dataset'")
        self._dataset = dataset

    def set_default_session(self, session: Session) -> None:
        """Convenience method for setting :attr:`session`."""
        self.session = session

    def set_default_dataset(self, dataset: Dataset) -> None:
        """Convenience method for setting :attr:`dataset`."""
        self.dataset = dataset

    @property
    def session_guid(self) -> uuid.UUID:
        """GUID of the default :class:`Session`."""
        return self._session.guid

    def create_item(self, item_type: type[Item], **kwargs: Any) -> Item:
        """Create and persist a new :class:`Item` of the given type.

        Parameters
        ----------
        item_type : type[Item]
            Concrete :class:`Item` subclass (e.g. ``String``, ``HTML``).
        **kwargs : Any
            Field values to use when constructing the new item.

        Returns
        -------
        Item
            The newly created item instance.

        Raises
        ------
        TypeError
            If ``item_type`` is not a subclass of :class:`Item`.
        ADRException
            If no keyword arguments are provided.
        """
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
    def _create_template_with_parent(template_type: type[Template], **kwargs: Any) -> Template:
        """Internal helper to create a template and attach it to its parent."""
        template = template_type.create(**kwargs)
        parent = kwargs.get("parent")
        if parent is not None:
            parent.children.append(template)
            parent.save()
        return template

    @staticmethod
    def create_template(template_type: type[Template], **kwargs: Any) -> Template:
        """Create and persist a new :class:`Template` of the given type.

        Parameters
        ----------
        template_type : type[Template]
            Concrete :class:`Template` subclass (e.g. ``BasicLayout``).
        **kwargs : Any
            Attributes for template creation. May include ``parent``.

        Returns
        -------
        Template
            The newly created template instance.

        Raises
        ------
        TypeError
            If ``template_type`` is not a subclass of :class:`Template`.
        ADRException
            If no keyword arguments are provided.
        """
        if not issubclass(template_type, Template):
            raise TypeError(f"{template_type.__name__} is not a subclass of Template")
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to create the template."
            )
        return ADR._create_template_with_parent(template_type, **kwargs)

    def _populate_template(self, id_str, attr, parent_template) -> Template:
        """Internal helper to create a :class:`Template` from JSON attributes.

        Delegates to :func:`populate_template` with this ADR's logger
        and :class:`Template` factory.
        """
        return populate_template(
            id_str,
            attr,
            parent_template,
            ADR._create_template_with_parent,
            self._logger,
            Template,
        )

    def _build_templates_from_parent(self, parent_id_str, parent_template, templates_json):
        """Recursively build child templates from a JSON template tree."""
        children_id_strs = templates_json[parent_id_str]["children"]
        if not children_id_strs:
            return

        for child_id_str in children_id_strs:
            child_attr = templates_json[child_id_str]
            child_template = self._populate_template(child_id_str, child_attr, parent_template)
            child_template.save()
            self._build_templates_from_parent(child_id_str, child_template, templates_json)

    def load_templates_from_file(self, file_path: str | Path) -> None:
        """Load a template tree from a JSON file.

        Parameters
        ----------
        file_path : str or Path
            Path to the JSON file containing templates exported via
            :meth:`Template.to_json`.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        """
        if not Path(file_path).exists():
            raise FileNotFoundError(f"The file '{file_path}' does not exist.")

        with open(file_path, encoding="utf-8") as f:
            templates_json = json.load(f)

        self.load_templates(templates_json)

    def load_templates(self, templates: dict) -> None:
        """Load a template tree from a Python dictionary.

        Parameters
        ----------
        templates : dict
            A mapping produced by :meth:`Template.to_dict`, typically by
            reading JSON and decoding it.

        Raises
        ------
        ADRException
            If no root (parent-less) template can be found in the mapping.
        """
        root_id_str = None
        for template_id_str, template_attr in templates.items():
            if template_attr["parent"] is None:
                root_id_str = template_id_str
                break

        if root_id_str is None:
            raise ADRException("No report or root template found in the provided templates.")

        root_attr = templates[root_id_str]
        root_template = self._populate_template(root_id_str, root_attr, None)
        root_template.save()
        self._build_templates_from_parent(root_id_str, root_template, templates)

    @staticmethod
    def get_report(**kwargs) -> Template:
        """Fetch a root report template (no parent) using template fields.

        Parameters
        ----------
        **kwargs : Any
            Filter arguments (for example, ``name="Report Name"``).

        Returns
        -------
        Template
            The matching root template.

        Raises
        ------
        ADRException
            If no kwargs are provided or the template cannot be found.
        """
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
        """Return all root report templates, optionally as a values-list.

        Parameters
        ----------
        fields : list, optional
            If provided, use ``values_list`` on the underlying queryset
            with these fields.
        flat : bool, default: False
            Passed through to ``values_list``. Typically used when a
            single field name is provided in ``fields``.

        Returns
        -------
        ObjectSet or list
            Either an :class:`ObjectSet` of templates or a list of
            field tuples/values.
        """
        out = Template.filter(parent=None)
        if fields:
            out = out.values_list(*fields, flat=flat)
        return out

    def get_list_reports(self, r_type: str | None = "name") -> ObjectSet | list:
        """Return a list of reports or just their names.

        Parameters
        ----------
        r_type : {"name", "report", None}, optional
            If ``"name"``, return a list of report names. If ``"report"`` or
            ``None``, return an :class:`ObjectSet` of templates.

        Returns
        -------
        ObjectSet or list
            Either templates or report names.

        Raises
        ------
        ADRException
            If ``r_type`` is not one of the supported options.
        """
        supported_types = ("name", "report")
        if r_type and r_type not in supported_types:
            raise ADRException(f"r_type must be one of {supported_types}")
        if not r_type or r_type == "report":
            return self.get_reports()
        # r_type == "name"
        return self.get_reports(
            fields=[r_type],
            flat=True,
        )

    def render_report(
        self,
        *,
        context: dict | None = None,
        item_filter: str = "",
        embed_scene_data: bool = False,
        **kwargs: Any,
    ) -> str:
        """Render a report as an HTML string.

        Parameters
        ----------
        context : dict, optional
            Context to pass to the report template.
        item_filter : str, optional
            ADR filter applied to items in the report.
        embed_scene_data: bool, optional
            Whether to include full scene data for 3D visualizations in the output HTML.
             This can increase the size of the output significantly, so it is disabled by default.
        **kwargs : Any
            Additional keyword arguments to pass to the report template. Eg: `guid`, `name`, etc.
            At least one keyword argument must be provided to fetch the report.

        Returns
        -------
        str
            Rendered HTML content (media type ``text/html``).

        Raises
        ------
        ADRException
            If no keyword arguments are provided or if the report rendering fails.

        Examples
        --------
        >>> from ansys.dynamicreporting.core.serverless import ADR
        >>> adr = ADR(ansys_installation=r"C:\\Program Files\\ANSYS Inc\\v252", db_directory=r"C:\\DBs\\docex")
        >>> html_content = adr.render_report(name="Serverless Simulation Report", item_filter="A|i_tags|cont|dp=dp227;")
        >>> with open("report.html", "w", encoding="utf-8") as f:
        ...     f.write(html_content)
        """
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        try:
            return Template.get(**kwargs).render(
                context=context,
                item_filter=item_filter,
                embed_scene_data=embed_scene_data,
                request=self._request,
            )
        except Exception as e:
            raise ADRException(f"Report rendering failed: {e}")

    def render_report_as_pptx(
        self, *, context: dict | None = None, item_filter: str = "", **kwargs: Any
    ) -> bytes:
        """Render a report as a PPTX byte stream.

        Only templates of type :class:`PPTXLayout` are supported.

        Parameters
        ----------
        context : dict, optional
            Context to pass to the report template.
        item_filter : str, optional
            ADR filter applied to items in the report.
        **kwargs : Any
            Additional keyword arguments to pass to the report template. Eg: `guid`, `name`, etc. At least one
            keyword argument must be provided to fetch the report.

        Returns
        -------
        bytes
            PPTX document bytes
            (media type
            ``application/vnd.openxmlformats-officedocument.presentationml.presentation``).

        Raises
        ------
        ADRException
            If no keyword arguments are provided or if the template is not of type PPTXLayout or
            if the report rendering fails.

        Examples
        --------
        >>> from ansys.dynamicreporting.core.serverless import ADR
        >>> adr = ADR(ansys_installation=r"C:\\Program Files\\ANSYS Inc\\v252", db_directory=r"C:\\DBs\\docex")
        >>> adr.setup()
        >>> pptx_stream = adr.render_report_as_pptx(name="Serverless Simulation Report", item_filter="A|i_tags|cont|dp=dp227;")
        >>> with open("report.pptx", "wb") as f:
        ...     f.write(pptx_stream)
        """
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        template = Template.get(**kwargs)
        if not isinstance(template, PPTXLayout):
            raise ADRException(
                "The template must be of type 'PPTXLayout' to render as a PowerPoint presentation."
            )
        try:
            return template.render_pptx(
                context=context,
                item_filter=item_filter,
                request=self._request,
            )
        except Exception as e:
            raise ADRException(f"PPTX Report rendering failed: {e}")

    def render_report_as_pdf(
        self, *, context: dict | None = None, item_filter: str = "", **kwargs: Any
    ) -> bytes:
        """Render a report as a PDF byte stream.

        Parameters
        ----------
        context : dict, optional
            Context to pass to the report template.
        item_filter : str, optional
            ADR filter applied to items in the report.
        **kwargs : Any
            Additional keyword arguments to pass to the report template. Eg: `guid`, `name`, etc.
            At least one keyword argument must be provided to fetch the report.

        Returns
        -------
        bytes
            PDF document bytes (media type ``application/pdf``).

        Raises
        ------
        ADRException
            If no keyword arguments are provided or if the report rendering fails.

        Examples
        --------
        >>> from ansys.dynamicreporting.core.serverless import ADR
        >>> adr = ADR(ansys_installation=r"C:\\Program Files\\ANSYS Inc\\v252", db_directory=r"C:\\DBs\\docex")
        >>> adr.setup()
        >>> pdf_stream = adr.render_report_as_pdf(name="Serverless Simulation Report")
        >>> with open("report.pdf", "wb") as f:
        ...     f.write(pdf_stream)
        """
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        try:
            return Template.get(**kwargs).render_pdf(
                context=context,
                item_filter=item_filter,
                request=self._request,
            )
        except Exception as e:
            raise ADRException(f"PDF Report rendering failed: {e}")

    def export_report_as_pptx(
        self,
        *,
        filename: str | Path = None,
        context: dict | None = None,
        item_filter: str = "",
        **kwargs: Any,
    ) -> None:
        """Render a PPTX report and write it to disk.

        If ``filename`` is not provided, the template's ``output_pptx``
        property is used, or a fallback based on the template GUID.

        Parameters
        ----------
        filename : str or Path, optional
            Target PPTX filename. If omitted, use the template's
            ``output_pptx`` property or ``"<guid>.pptx"``.
        context : dict, optional
            Context to pass to the report template.
        item_filter : str, optional
            ADR filter applied to items in the report.
        **kwargs : Any
            Additional keyword arguments to pass to the report template. Eg: `guid`, `name`, etc. At least one
            keyword argument must be provided to fetch the report.

        Returns
        -------
            None

        Raises
        ------
        ADRException
            If no keyword arguments are provided or if the template is not of type PPTXLayout or
            if the report rendering fails.

        Examples
        --------
        >>> from ansys.dynamicreporting.core.serverless import ADR
        >>> adr = ADR(ansys_installation=r"C:\\Program Files\\ANSYS Inc\\v252", db_directory=r"C:\\DBs\\docex")
        >>> adr.setup()
        >>> adr.export_report_as_pptx(name="Serverless Simulation Report", item_filter="A|i_tags|cont|dp=dp227;")
        """
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        template = Template.get(**kwargs)
        if not isinstance(template, PPTXLayout):
            raise ADRException(
                "The template must be of type 'PPTXLayout' to export as a PowerPoint presentation."
            )
        try:
            pptx_stream = template.render_pptx(
                context=context,
                item_filter=item_filter,
                request=self._request,
            )
        except Exception as e:
            raise ADRException(f"PPTX Report rendering failed: {e}")

        output_path = (
            Path(filename) if filename else Path(template.output_pptx or f"{template.guid}.pptx")
        )
        with open(output_path, "wb") as f:
            f.write(pptx_stream)
        self._logger.info(f"Successfully exported report to: {output_path}")

    def export_report_as_html(
        self,
        output_directory: str | Path,
        *,
        filename: str = "index.html",
        dark_mode: bool = False,
        context: dict | None = None,
        item_filter: str = "",
        **kwargs: Any,
    ) -> Path:
        """Export a report as a standalone HTML file (plus assets).

        Parameters
        ----------
        output_directory : str or Path
            Directory where the report will be exported. It is created if
            it does not exist.
        filename : str, default: "index.html"
            Name of the HTML file within ``output_directory``.
        dark_mode : bool, default: False
            If ``True``, the report is rendered using a dark theme (where
            supported).
        context : dict, optional
            Context to pass to the report template.
        item_filter : str, optional
            ADR filter applied to items in the report.
        **kwargs : Any
            Additional keyword arguments to pass to fetch the report template. Eg: `guid`, `name`, etc.
            At least one keyword argument must be provided to fetch the report.

        Returns
        -------
        Path
            Path to the generated HTML file.

        Raises
        ------
        ADRException
            If no keyword arguments are provided or if the static directory is not configured.
        ImproperlyConfiguredError
            If the static directory is not configured or if the output directory cannot be created.

        Examples
        --------
        >>> from ansys.dynamicreporting.core.serverless import ADR
        >>> adr = ADR(
                    ansys_installation=r"C:\\Program Files\\ANSYS Inc\\v252",
                    db_directory=r"C:\\DBs\\docex",
                    media_directory=r"C:\\DBs\\docex\\media",
                    static_directory=r"C:\\static"
                )
        >>> adr.setup(collect_static=True)
        >>> output_path = adr.export_report_as_html(
                    Path.cwd() / "htmlex",
                    context={},
                    item_filter="A|i_tags|cont|dp=dp227;",
                    name="Serverless Simulation Report",
                )
        """
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        if self._static_directory is None:
            raise ImproperlyConfiguredError(
                "The 'static_directory' must be configured to export a report."
            )

        output_dir = Path(output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Render HTML via the template system.
        html_content = self.render_report(
            context=context,
            item_filter=item_filter,
            **kwargs,
        )

        # Use the serverless exporter to inline assets, rewrite links, etc.
        exporter = ServerlessReportExporter(
            html_content=html_content,
            output_dir=output_dir,
            media_dir=self._media_directory,
            static_dir=self._static_directory,
            media_url=self._media_url,
            static_url=self._static_url,
            filename=filename,
            ansys_version=str(self._ansys_version),
            dark_mode=dark_mode,
            debug=self._debug,
            logger=self._logger,
        )
        exporter.export()

        # Return the path to the generated file.
        final_path = output_dir / filename
        self._logger.info(f"Successfully exported report to: {final_path}")
        return final_path

    def export_report_as_pdf(
        self,
        *,
        filename: str | Path = None,
        context: dict | None = None,
        item_filter: str = "",
        **kwargs: Any,
    ) -> None:
        """Render a PDF report and write it to disk.

        Parameters
        ----------
        filename : str or Path, optional
            Target PDF filename. If omitted, use ``"<guid>.pdf"`` based
            on the template GUID.
        context : dict, optional
            Context to pass to the report template.

        item_filter : str, optional
            ADR filter applied to items in the report.
        **kwargs : Any
            Additional keyword arguments to pass to the report template. Eg: `guid`, `name`, etc.
            At least one keyword argument must be provided to fetch the report.

        Returns
        -------
            None

        Raises
        ------
        ADRException
            If no keyword arguments are provided or if the report rendering fails.

        Examples
        --------
        >>> from ansys.dynamicreporting.core.serverless import ADR
        >>> adr = ADR(ansys_installation=r"C:\\Program Files\\ANSYS Inc\\v252", db_directory=r"C:\\DBs\\docex")
        >>> adr.setup()
        >>> adr.export_report_as_pdf(filename="report.pdf", name="Serverless Simulation Report", item_filter="A|i_tags|cont|dp=dp227;")
        """
        if not kwargs:
            raise ADRException(
                "At least one keyword argument must be provided to fetch the report."
            )
        template = Template.get(**kwargs)
        try:
            pdf_stream = template.render_pdf(
                context=context,
                item_filter=item_filter,
                request=self._request,
            )
        except Exception as e:
            raise ADRException(f"PDF Report rendering failed: {e}")

        output_path = Path(filename) if filename else Path(f"{template.guid}.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_stream)
        self._logger.info(f"Successfully exported report to: {output_path}")

    @staticmethod
    def query(
        query_type: Session | Dataset | type[Item] | type[Template],
        *,
        query: str = "",
        **kwargs: Any,
    ) -> ObjectSet:
        """Run an ADR query against sessions, datasets, items, or templates.

        Parameters
        ----------
        query_type : type
            One of :class:`Session`, :class:`Dataset`, :class:`Item`
            subclass, or :class:`Template`.
        query : str, default: ""
            ADR query string (e.g. ``"A|i_tags|cont|dp=dp227;"``).
        **kwargs : Any
            Additional keyword arguments forwarded to ``.find``.

        Returns
        -------
        ObjectSet
            Query results wrapped in :class:`ObjectSet`.

        Raises
        ------
        TypeError
            If ``query_type`` is not a supported ADR model type.
        """
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
        """Persist multiple ADR objects, returning the count of saved objects.

        Parameters
        ----------
        objects : list or ObjectSet
            Iterable of ADR model instances to save.
        **kwargs : Any
            Additional keyword arguments passed to each object's ``save``
            method (for example, ``using="remote"``).

        Returns
        -------
        int
            Number of objects successfully saved.

        Raises
        ------
        ADRException
            If ``objects`` is not iterable.
        """
        if not isinstance(objects, Iterable):
            raise ADRException("objects must be an iterable")
        count = 0
        for obj in objects:
            # When copying across databases, reset the object's DB if needed.
            if obj.db and kwargs.get("using", "default") != obj.db:  # pragma: no cover
                # required if copying across databases
                obj.reinit()
            obj.save(**kwargs)
            count += 1
        return count

    def _copy_template(self, template: Template, **kwargs) -> Template:
        """Internal helper to deep-copy a template subtree into another DB.

        This performs a depth-first copy of ``template`` and all its
        descendants, preserving GUIDs and child ordering.
        """
        # Depth-first walk down from the root and copy children along the way.
        out_template = copy.deepcopy(template)
        if out_template.parent is not None:
            parent = out_template.parent
            # Parents are always copied first, so they should exist in the target.
            out_template.parent = Template.get(
                guid=parent.guid,
                using=kwargs.get("using", "default"),
            )
        # Preserve legacy ordering semantics.
        out_template.reorder_children()
        children = out_template.children
        out_template.children = []
        out_template.reinit()
        out_template.save(**kwargs)

        new_children: list[Template] = []
        for child in children:
            child.parent = out_template
            new_child = self._copy_template(child, **kwargs)
            new_children.append(new_child)
        out_template.children = new_children
        out_template.update_children_order()
        out_template.save(**kwargs)
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
        """Copy ADR objects (and associated media) between databases.

        This method:

        * Queries objects of the given type from the **source** database
          (currently hard-coded to ``"default"``).
        * For :class:`Item` objects, ensures their :class:`Session` and
          :class:`Dataset` are also present in the target database, creating
          them as needed.
        * For :class:`Template` objects, only copies root templates
          (children are copied recursively).
        * Copies media files to a target media directory, optionally
          rebuilding 3D geometry files.

        Parameters
        ----------
        object_type : type
            One of :class:`Session`, :class:`Dataset`, :class:`Item`
            subclass, or :class:`Template`.
        target_database : str
            Django database alias to copy into.
        query : str, default: ""
            ADR query string used to select objects from the source DB.
        target_media_dir : str or Path, default: ""
            Target directory for media files, required when copying items
            with associated files and the target database is not SQLite.
        test : bool, default: False
            If ``True``, do not actually write anything; just log and
            return the count of objects that would be copied.

        Returns
        -------
        int
            Number of objects copied (or that would be copied in test mode).

        Raises
        ------
        ADRException
            If misconfigured (e.g. missing DB aliases, invalid media
            directory, non-top-level templates, or copy errors).
        """
        source_database = "default"  # TODO: allow caller to specify source DB.

        if not issubclass(object_type, (Item, Template, Session, Dataset)):
            raise TypeError(
                f"'{object_type.__name__}' is not a type of Item, Template, Session, or Dataset"
            )

        database_config = self.get_database_config(raise_exception=True)
        if target_database not in database_config or source_database not in database_config:
            raise ADRException(
                f"'{source_database}' and '{target_database}' must be configured first using the "
                "'databases' option."
            )

        objects = self.query(object_type, query=query)
        copy_list: list[Any] = []
        media_dir: Path | None = None

        if issubclass(object_type, Item):
            for item in objects:
                # Determine media directory if any item references a physical file.
                if getattr(item, "has_file", False) and media_dir is None:
                    if target_media_dir:
                        media_dir = Path(target_media_dir).resolve(strict=True)
                    elif self._is_sqlite(target_database):
                        media_dir = self._check_dir(
                            Path(self._get_db_path(target_database)).parent / "media"
                        )
                    else:
                        raise ADRException(
                            "'target_media_dir' argument must be specified because one of the "
                            "objects contains media to copy.'"
                        )

                # Ensure session and dataset exist in target DB (reuse if present).
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
            # Only copy top-level templates (children are handled recursively).
            for template in objects:
                if template.parent is not None:
                    raise ADRException("Only top-level templates can be copied.")
                new_template = self._copy_template(template, using=target_database)
                copy_list.append(new_template)
        else:  # Session or Dataset
            copy_list = list(objects)

        if test:
            self._logger.info(f"Copying {len(copy_list)} objects...")
            return len(copy_list)

        try:
            count = self.create_objects(copy_list, using=target_database)
        except Exception as e:
            raise ADRException(f"Some objects could not be copied: {e}")

        # Copy associated media files, rebuilding 3D geometry when needed.
        if issubclass(object_type, Item) and media_dir is not None:
            for item in objects:
                if not getattr(item, "has_file", False):
                    continue
                shutil.copy(Path(item.content), media_dir)
                file_name = str((media_dir / Path(item.content).name).resolve(strict=True))
                if file_is_3d_geometry(file_name, file_item_only=(item.type == "file")):
                    rebuild_3d_geometry(file_name)

        return count
