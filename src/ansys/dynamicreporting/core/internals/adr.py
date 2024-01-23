import os
import re
from pathlib import Path

from django.http import HttpRequest

from ..adr_utils import get_logger
from ..exceptions import (
    InvalidAnsysPath,
    AnsysVersionAbsentError,
    ImproperlyConfiguredError,
    DatabaseMigrationError,
    StaticFilesCollectionError,
    InvalidPath
)


class BaseModel:

    def __init__(self, *args, **kwargs):
        ...

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self)

    def __str__(self):
        return "%s object (%s)" % (self.__class__.__name__, self.guid)


class ADR:
    """
    from ansys.dynamicreporting.core.adr import ADR
    adr = ADR(opts = { "CEI_NEXUS_DEBUG" : "0", "CEI_NEXUS_SECRET_KEY": "h1kuvl)j#e6_7rbhr&f@_3%)$nle*b8t$82wta*e3wu-(5v$$o", "CEI_NEXUS_LOCAL_DB_DIR": "C:\cygwin64\home\vrajendr\doc_ex" })
    first_text = adr.create_item(content="<h1>My Title</h1>This is the first example")
    content = adr.get_report_content()
    """

    def __init__(
            self,
            ansys_installation,
            db_directory: str = None,
            media_directory: str = None,
            static_directory: str = None,
            logfile: str = None,
            opts: dict = None,
            request: HttpRequest = None
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
            self._ansys_version = int(matches.group(1))
        except IndexError:
            raise AnsysVersionAbsentError

        if db_directory is not None:
            self._db_directory = self._check_dir(db_directory)
            os.environ["CEI_NEXUS_LOCAL_DB_DIR"] = db_directory

        if media_directory is not None:
            self._media_directory = self._check_dir(media_directory)
            os.environ["CEI_NEXUS_LOCAL_MEDIA_DIR"] = media_directory

        if static_directory is not None:
            self._static_directory = self._check_dir(static_directory)
            os.environ["CEI_NEXUS_STATIC_ROOT"] = static_directory

        if opts is None:
            opts = {}
        self._configure(opts)

    def _check_dir(self, dir_):
        dir_path = Path(dir_)
        if not dir_path.is_dir():
            self._logger.error(f"Invalid directory path: {dir_}")
            raise InvalidPath(extra_detail=dir_)
        return dir_path

    def _configure(self, opts: dict) -> None:
        for opt, value in opts.items():
            os.environ[opt] = value
        os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                              "ansys.dynamicreporting.core.internals.report_framework.settings")
        # django.setup() may only be called once.
        try:
            import django
            django.setup()
        except Exception as e:
            self._logger.error(f"{e}")
            raise ImproperlyConfiguredError(extra_detail=str(e))

        from django.core import management
        # migrations
        try:
            management.call_command('migrate')
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
        try:
            management.call_command('collectstatic', '--no-input')
        except Exception as e:
            self._logger.error(f"{e}")
            raise StaticFilesCollectionError(extra_detail=str(e))

    def put_objects(self):
        ...

    def create_item(self, type, content):
        # pass in name, item type (Enum?), payload and tags
        ...

    def create_session(self):
        ...

    def create_dataset(self):
        ...

    def create_template(self):
        # pass in name, parent, template type (Enum), params, filters, properties, HTML header
        ...

    def get_report(self):
        #     take name or guid, return Template obj
        return

    def visualize_report(self):
        ...

    def query(self, query_filter=""):
        ...

    def get_list_reports(self):
        ...

    def export_report_as_pdf(self):
        ...
