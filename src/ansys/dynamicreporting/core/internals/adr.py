import os
import re
from pathlib import Path
from typing import Any, Type

from django.core import management
from django.db.models import Model
from django.http import HttpRequest

from .item import Item, Session, Dataset
from .template import Template
from ..adr_utils import get_logger
from ..exceptions import (
    InvalidAnsysPath,
    AnsysVersionAbsentError,
    ImproperlyConfiguredError,
    DatabaseMigrationError,
    StaticFilesCollectionError,
    InvalidPath,
    ObjectDoesNotExistError
)


class ADR:
    """
        >> from ansys.dynamicreporting.core import ADR, Table
        >> opts = { "CEI_NEXUS_DEBUG" : "0", "CEI_NEXUS_SECRET_KEY":"", "CEI_NEXUS_LOCAL_DB_DIR":r"C:\cygwin64\home\vrajendr\ogdocex" }
        >> adr = ADR(r"C:\Program Files (x86)\ANSYSv231", opts = opts)
        >> adr.configure()
        >> table = adr.create_item(Table, name="table1", content={}, tags="dp=1 part=bumper")
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
            session: str = None,
            dataset: str = None,
            logfile: str = None
    ) -> None:
        self._db_directory = None
        self._media_directory = None
        self._static_directory = None

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

        self._request = request  # passed when used in the context of a webserver.

        self._session = session
        self._dataset = dataset

        self._logger = get_logger(logfile)

    @property
    def session(self):
        return self._session

    @property
    def dataset(self):
        return self._dataset

    def _check_dir(self, dir_):
        dir_path = Path(dir_)
        if not dir_path.is_dir():
            self._logger.error(f"Invalid directory path: {dir_}")
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    def setup(self, collect_static=False) -> None:
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

    def _validate_kwargs(self, type_, kwargs):
        valid_fields = type_.get_field_names()
        for kwarg, value in kwargs.items():
            if kwarg not in valid_fields:
                detail = f"{type_.__name__} has no attribute {kwarg}"
                self._logger.error(detail)
                raise AttributeError(detail)

    def create_item(self, item_type: Type[Item], **kwargs: Any):
        if not issubclass(item_type, Item):
            raise TypeError(f"{item_type} is not valid")
        self._validate_kwargs(item_type, kwargs)
        item = item_type(**kwargs)
        # save session and dataset before creating the relation
        try:
            if self._session is None:
                session = Session()
                session.save()
            else:
                session = Session.get(guid=self._session)
        except Model.DoesNotExist:
            raise ObjectDoesNotExistError(f"Session '{self._session}' not found")
        try:
            if self._dataset is None:
                dataset = Dataset()
                dataset.save()
            else:
                dataset = Dataset.get(guid=self._dataset)
        except Model.DoesNotExist:
            raise ObjectDoesNotExistError(f"Dataset '{self._dataset}' not found")

        item.session = session
        item.dataset = dataset
        item.save()
        return item

    def create_template(self, template_type: Type[Template], **kwargs):
        # pass in name, parent, template type (Enum), params, filters, properties, HTML header
        if not issubclass(template_type, Template):
            raise TypeError(f"{template_type} is not valid")
        self._validate_kwargs(template_type, kwargs)
        template = template_type(**kwargs)
        template.save()
        # handle parents automatically
        parent = kwargs.get("parent")
        if parent is not None:
            ...
        return template

    def render_report(self):  # replacement for visualize_report
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
