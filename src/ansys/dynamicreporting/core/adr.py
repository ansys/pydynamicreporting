import os
import re
from typing import Optional

from django.shortcuts import render

from .adr_utils import get_logger
from .exceptions import (
    InvalidAnsysPath,
    AnsysVersionAbsentError,
    ImproperlyConfiguredError,
    DatabaseMigrationError,
    StaticFilesCollectionError
)
from django.http import HttpRequest
from django.template.loader import render_to_string

from .internals.reports.engine import TemplateEngine
from django.core import management
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission


class BaseModel:

    def __init__(self, *args, **kwargs):
        ...

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self)

    def __str__(self):
        return "%s object (%s)" % (self.__class__.__name__, self.guid)


class Item(BaseModel):

    @property
    def tags(self):
        ...

    def set_tags(self):
        ...

    def get_tags(self):
        ...

    def add_tag(self):
        ...

    # todo: abstract or overrideable
    def set_content(self):
        ...

    def create(self):
        ...

    def save(
            self,
            *args,
    ):
        ...

    def delete(self):
        ...

    def visualize(self):  # or render()
        ...


class String(Item):
    ...


class Text(String):
    ...


class Table(Item):
    ...


class Plot(Table):
    ...


class Tree(Item):
    ...


class Scene(Item):
    ...


class Image(Item):
    ...


class HTML(Item):
    ...


class Animation(Item):
    ...


class File(Item):
    ...


class Session(BaseModel):
    ...


class Dataset(BaseModel):
    ...


class Template(BaseModel):
    def visualize(self):
        ...

    def get_html(self):
        ...

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
    from ansys.dynamicreporting.core.adr import ADR
    adr = ADR(opts = { "CEI_NEXUS_DEBUG" : "0", "CEI_NEXUS_SECRET_KEY": "h1kuvl)j#e6_7rbhr&f@_3%)$nle*b8t$82wta*e3wu-(5v$$o", "CEI_NEXUS_LOCAL_DB_DIR": "C:\cygwin64\home\vrajendr\doc_ex" })
    first_text = adr.create_item(content="<h1>My Title</h1>This is the first example")
    content = adr.get_report_content()
    """

    def __init__(
            self,
            ansys_installation: Optional[str] = None,
            db_directory: str = None,
            media_directory: str = None,
            static_directory: str = None,
            logfile: str = None,
            opts: dict = None,
            request: HttpRequest = None
    ) -> None:
        self._db_directory = db_directory
        self._media_directory = media_directory
        self._static_directory = static_directory
        self._logger = get_logger(logfile)
        self._request = request  # must be passed when used in the context of a webserver.

        install_dir = ansys_installation
        if install_dir is not None:
            # Backward compatibility: if the path passed is only up to the version directory,
            # append the CEI directory
            if not install_dir.endswith("CEI"):
                install_dir = os.path.join(install_dir, "CEI")
                # verify new path
                if not os.path.isdir(install_dir):
                    # Option for local development build
                    if "CEIDEVROOTDOS" in os.environ:
                        install_dir = os.environ["CEIDEVROOTDOS"]
                    else:
                        raise InvalidAnsysPath(install_dir)
            # try to get version from install path
            matches = re.search(r".*v([0-9]{3}).*", install_dir)
            if matches is None:
                # Option for local development build
                if os.environ.get("ANSYS_REL_INT_I") is not None:
                    self._ansys_version = int(os.environ.get("ANSYS_REL_INT_I"))
                else:
                    raise AnsysVersionAbsentError
            else:
                try:
                    self._ansys_version = int(matches.group(1))
                except IndexError:
                    raise AnsysVersionAbsentError

        self._ansys_installation = install_dir
        if opts is None:
            opts = {}
        self._configure(opts)

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
        # migrations
        try:
            management.call_command('migrate')
        except Exception as e:
            self._logger.error(f"{e}")
            raise DatabaseMigrationError(extra_detail=str(e))
        else:
            if not User.objects.filter(is_superuser=True).exists():
                user = User.objects.create_superuser("nexus", "", "cei")
                # include the nexus group (with all permissions)
                nexus_group, created = Group.objects.get_or_create(name='nexus')
                if created:
                    nexus_group.permissions.set(Permission.objects.all())
                nexus_group.user_set.add(user)
        # collecstatic
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

