import os
from pathlib import Path
import platform
import re
import sys
from typing import Any, Optional, Type

import django
from django.core import management
from django.http import HttpRequest

from .. import DEFAULT_ANSYS_VERSION
from ..adr_utils import get_logger
from ..exceptions import (
    AnsysVersionAbsentError,
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
        db_directory: str = None,
        media_directory: str = None,
        static_directory: str = None,
        opts: dict = None,
        request: HttpRequest = None,
        logfile: str = None,
    ) -> None:
        self._db_directory = None
        self._media_directory = None
        self._static_directory = None

        self._ansys_version = DEFAULT_ANSYS_VERSION
        os.environ["CEI_APEX_SUFFIX"] = self._ansys_version

        self._ansys_installation = self._get_install_directory(ansys_installation)
        os.environ["CEI_NEXUS_INSTALLATION_DIR"] = str(self._ansys_installation)

        try:
            # import hack
            sys.path.append(
                str(self._ansys_installation / f"nexus{self._ansys_version}" / "django")
            )
            from .item import Dataset, Item, Session
            from .template import Template
        except ImportError as e:
            raise ImportError(f"Failed to import from the Ansys installation: {e}")
        else:
            self._dataset_cls = Dataset
            self._session_cls = Session
            self._item_cls = Item
            self._template_cls = Template

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

        self._request = request  # passed when used in the context of a webserver.
        self._session = None
        self._dataset = None
        self._logger = get_logger(logfile)

    def _get_install_directory(self, ansys_installation: Optional[str]) -> Path:
        dirs_to_check = []
        if ansys_installation:
            # User passed directory
            dirs_to_check.extend([Path(ansys_installation) / "CEI", Path(ansys_installation)])
        else:
            # Environmental variable
            if "PYADR_ANSYS_INSTALLATION" in os.environ:
                env_inst = Path(os.environ["PYADR_ANSYS_INSTALLATION"])
                dirs_to_check.append(env_inst)
                # Note: PYADR_ANSYS_INSTALLATION is designed for devel builds
                # where there is no CEI directory, but for folks using it in other
                # ways, we'll add that one too, just in case.
                dirs_to_check.append(env_inst / "CEI")
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
        dir_path = Path(dir_)
        if not dir_path.is_dir():
            self._logger.error(f"Invalid directory path: {dir_}")
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    def setup(self, collect_static=False) -> None:
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE",
            "ceireports.settings_serverless",
        )
        # django.setup() may only be called once.
        try:
            django.setup()
        except Exception as e:
            self._logger.error(f"{e}")
            raise ImproperlyConfiguredError(extra_detail=str(e))

        # create session and dataset w/ defaults if not provided.
        if self._session is None:
            self._session = self._session_cls.create()

        if self._dataset is None:
            self._dataset = self._dataset_cls.create()

        # migrations
        if self._db_directory is not None:
            try:
                management.call_command("migrate", verbosity=0)
            except Exception as e:
                self._logger.error(f"{e}")
                raise DatabaseMigrationError(extra_detail=str(e))
            else:
                from django.contrib.auth.models import Group, Permission, User

                if not User.objects.filter(is_superuser=True).exists():
                    user = User.objects.create_superuser("nexus", "", "cei")
                    # include the nexus group (with all permissions)
                    nexus_group, created = Group.objects.get_or_create(name="nexus")
                    if created:
                        nexus_group.permissions.set(Permission.objects.all())
                    nexus_group.user_set.add(user)

        # collectstatic
        if collect_static and self._static_directory is not None:
            try:
                management.call_command("collectstatic", "--no-input", verbosity=0)
            except Exception as e:
                self._logger.error(f"{e}")
                raise StaticFilesCollectionError(extra_detail=str(e))

    @property
    def session(self):
        return self._session

    @property
    def dataset(self):
        return self._dataset

    @session.setter
    def session(self, session: "Session"):
        if not isinstance(session, self._session_cls):
            raise TypeError("Must be an instance of type 'Session'")
        self._session = session

    @dataset.setter
    def dataset(self, dataset: "Dataset"):
        if not isinstance(dataset, self._dataset_cls):
            raise TypeError("Must be an instance of type 'Dataset'")
        self._dataset = dataset

    def set_default_session(self, session: "Session"):
        self.session = session

    def set_default_dataset(self, dataset: "Dataset"):
        self.dataset = dataset

    @property
    def session_guid(self):
        """GUID of the session associated with the service."""
        return self._session.guid

    def create_item(self, item_type: Type["Item"], **kwargs: Any):
        if not issubclass(item_type, self._item_cls):
            raise TypeError(f"{item_type} is not valid")
        return item_type.create(session=self._session, dataset=self._dataset, **kwargs)

    def create_template(self, template_type: Type["Template"], **kwargs: Any):
        if not issubclass(template_type, self._template_cls):
            self._logger.error(f"{template_type} is not valid")
            raise TypeError(f"{template_type} is not valid")
        template = template_type.create(**kwargs)
        parent = kwargs.get("parent")
        if parent is not None:
            parent.children.append(template)
            parent.save()
        return template

    def get_report(self, **kwargs):
        try:
            return self._template_cls.get(master=True, **kwargs)
        except Exception as e:
            self._logger.error(f"{e}")
            raise e

    def get_reports(self, fields=None, flat=False):
        # return list of reports by default.
        # if fields are mentioned, return value list
        try:
            out = self._template_cls.filter(master=True)
            if fields:
                out = out.values_list(*fields, flat=flat)
        except Exception as e:
            self._logger.error(f"{e}")
            raise e

        return list(out)

    def get_list_reports(self, *fields):
        return self.get_reports(*fields)

    def render_report(self, context=None, query=None, **kwargs):
        try:
            return self._template_cls.get(**kwargs).render(
                request=self._request, context=context, query=query
            )
        except Exception as e:
            self._logger.error(f"{e}")
            raise e

    def query(self, query_type: str = "Item", filter: Optional[str] = "") -> list:
        ...

    def create(self, objects: list) -> None:
        ...

    def delete(self, objects: list) -> None:
        ...
