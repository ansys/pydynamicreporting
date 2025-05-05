"""
Service module.

Module for creating an Ansys Dynamic Reporting Service instance.

Examples::

    import ansys.dynamicreporting.core as adr
    adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
    ret = adr_service.connect()
    my_img = adr_service.create_item()
    my_img.item_image = 'Image_to_push_on_report'
    adr_service.visualize_report()
"""

import atexit
import json
import os
import shutil
import tempfile
import time

try:
    from IPython.display import IFrame
except ImportError:  # pragma: no cover
    pass

import warnings
import webbrowser

from ansys.dynamicreporting.core.utils import exceptions as adr_utils_exceptions
from ansys.dynamicreporting.core.utils import report_objects, report_remote_server, report_utils

from .adr_item import Item
from .adr_report import Report
from .adr_utils import build_query_url, check_filter, dict_items, get_logger, in_ipynb, type_maps
from .common_utils import get_install_info
from .constants import DOCKER_DEFAULT_PORT, DOCKER_REPO_URL
from .docker_support import DockerLauncher
from .exceptions import (
    AlreadyConnectedError,
    CannotCreateDatabaseError,
    ConnectionToServiceError,
    DatabaseDirNotProvidedError,
    MissingReportError,
    MissingSession,
    NotValidServer,
    StartingServiceError,
)


# Main class
class Service:
    """
    Provides for creating a connection to an Ansys Dynamic Reporting service.

    Parameters
    ----------
    ansys_version : int, optional
        Three-digit format for a locally installed Ansys version.
        For example, ``232`` for Ansys 2023 R2. The default is ``None``.
    docker_image : str, optional
        Docker image to use if you do not have a local Ansys installation.
        The default is ``"ghcr.io/ansys-internal/nexus"``.
    data_directory : str, optional
        Path to the directory for storing temporary information from the Docker image.
        The default is creating a new directory inside the OS
        temporary directory. This parameter must pass a directory that exists and
        is empty.
    db_directory : str, optional
        Path to the database directory for the Ansys Dynamic Reporting service.
        The default is ``None``. This parameter must pass a directory that exists and
        is empty.
    port : int, optional
        Port to run the Ansys Dynamic Reporting service on. The default is ``8000``.
    logfile : str, optional
        File to write logs to. The default is ``None``. Acceptable values are
        filenames or ``stdout`` for standard output.
    ansys_installation : str, optional
        Path to the directory where Ansys is installed locally. If Ansys is not
        installed locally but is to be run in a Docker image, set the
        value for this paraemter to ``"docker"``.


    Raises
    ------
    DatabaseDirNotProvidedError
        The ``"db_directory"`` argument has not been provided when using a Docker image.
    CannotCreateDatabaseError
        Can not create the ``"db_directory"`` when using a Docker image.
    InvalidAnsysPath
        The ``"ansys_installation"`` does not correspond to a valid Ansys installation.
        directory
    AnsysVersionAbsentError
        Can not find the Ansys version number from the installation directory.


    Examples
    --------
    Initialize the class and connect to an Ansys Dynamic Reporting service running on
    the localhost on port 8010 with ``username`` set to ``"admin"`` and ``password``
    set to ``"mypsw"`` using a local Ansys installation::

        import ansys.dynamicreporting.core as adr
        installation_dir = r'C:\\Program Files\\ANSYS Inc\\v232'
        adr_service = adr.Service(ansys_installation = installation_dir)
        ret = adr_service.connect(url = "http://localhost:8010", username = "admin", password = "mypsw")
    """

    def __init__(
        self,
        ansys_version: int = None,
        docker_image: str = DOCKER_REPO_URL,
        data_directory: str = None,
        db_directory: str = None,
        port: int = DOCKER_DEFAULT_PORT,
        logfile: str = None,
        ansys_installation: str | None = None,
    ) -> None:
        """
        Initialize an Ansys Dynamic Reporting object.

        Parameters
        ----------
        ansys_installation : str, optional
            Location of the Ansys installation, including the version directory.
            For example, r'C:\\Program Files\\ANSYS Inc\\v232'. The default is
            ``None``. This parameter is needed only if the Service instance is
            to launch a dynamic Reporting service. It is not needed if connecting
            to an existing service. If there is no local Ansys installation and
            a Docker image is to be used instead, enter ``"docker"``.
        docker_image : str, optional
            Location of the Docker image for Ansys Dynamic Reporting. The default
            is ghcr.io/ansys-internal/nexus. This parameter is used only if the
            value for the ``ansys_installation`` parameter is set to ``"docker"``.
            Default:
        data_directory: str, optional
            Directory where Docker is to store temporary copy of files. The
            default is ``None``, in which case ``TMP_DIR`` is used. This parameter
            is used only if the value for the ``ansys_installation`` parameter
            is set to ``"docker"``.
        db_directory: str, optional
            Directory containing the database. The default is ``None``.
        port: int
            Service port number. The default is ``DOCKER_DEFAULT_PORT``, in which
            case ``8000`` is used.
        logfile: str, optional
            Location for the log file. The default is None.
            If this parameter is set to ``stdout``, the output will be printed
            to stdout.
        """
        self.serverobj = None
        self._session_guid = ""
        self._url = None
        self.logger = get_logger(logfile)
        self._data_directory = None
        self._db_directory = db_directory
        self._delete_db = False
        self._port = port
        self._docker_launcher = None
        self._docker_image = docker_image

        if ansys_installation == "docker":
            if not self._db_directory:
                self.logger.error("db_directory cannot be None when using Docker.\n")
                raise DatabaseDirNotProvidedError

            if not os.path.isdir(self._db_directory):
                try:
                    os.mkdir(self._db_directory, mode=0o755)
                except Exception as e:  # pragma: no cover
                    self.logger.error(
                        f"Can't create db_directory {self._db_directory}.\n{str(e)}\n"
                    )
                    raise CannotCreateDatabaseError(f"{self._db_directory} : {str(e)}")

            if not data_directory:
                self._data_directory = tempfile.mkdtemp()
            elif not os.path.isdir(data_directory):
                self.logger.warning(
                    f"data_directory {data_directory} does not exist. "
                    f"Replacing it with tmp directory.\n"
                )
                self._data_directory = tempfile.mkdtemp()
            else:
                self._data_directory = data_directory

            try:
                self._docker_launcher = DockerLauncher(image_url=docker_image)
            except Exception as e:
                self.logger.error(f"Error initializing the Docker Container object.\n{str(e)}\n")
                raise e

            try:
                self._docker_launcher.pull_image()
            except Exception as e:
                self.logger.error(
                    f"Error pulling the Docker image {self._docker_image}.\n{str(e)}\n"
                )
                raise e

            try:
                # start the container and map specified host directory into the
                # container.  The location in the container is always /host_directory/."
                self.__checkport__()
                self._docker_launcher.start(
                    host_directory=self._data_directory,
                    db_directory=self._db_directory,
                    port=self._port,
                    ansys_version=ansys_version,
                )
            except Exception as e:  # pragma: no cover
                self.logger.error(f"Error starting the Docker Container.\n{str(e)}\n")
                raise e

            self._ansys_installation, self._ansys_version = (ansys_installation, ansys_version)

        else:  # pragma: no cover
            # local installation
            self._ansys_installation, self._ansys_version = get_install_info(
                ansys_installation=ansys_installation, ansys_version=ansys_version
            )

    @property
    def session_guid(self):
        """GUID of the session associated with the service."""
        if self._session_guid == "":
            self.logger.error("No session attached to this instance.")
            raise MissingSession
        else:
            return self._session_guid

    @property
    def url(self):
        """URL for the service."""
        return self._url

    def connect(
        self,
        url: str = f"http://localhost:{DOCKER_DEFAULT_PORT}",
        username: str = "nexus",
        password: str = "cei",
        session: str | None = "",
    ) -> None:
        """
        Connect to a running service.

        Parameters
        ----------
        url : str, optional
            URL for the service. The default is ``http://localhost:8000``.
        username : str, optional
            Username for the service. The default is ``"nexus"``.
        password : str, optional
            Password for the service. The default is ``"cei"``.
        session : str, optional
            GUID for the session to work with. The default is ``""``,
            in which case a new session with its own GUID is created.
            All created items are then pushed on this session. Visualizations
            are all filtered so that only items for this session are shown.


        Raises
        ------
        NotValidServer
            The current Service doesn not have a valid server associated to it.


        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect(url="http://localhost:8010", username='admin', password = 'mypsw')
        """
        if self._url is not None:  # pragma: no cover
            self.logger.warning("Already connected to a dynamic reporting service.\n")
            return
        self.serverobj = report_remote_server.Server(
            url=url, username=username, password=password, ansys_version=self._ansys_version
        )
        try:
            self.serverobj.validate()
        except Exception:
            self.logger.error("Can not validate dynamic reporting server.\n")
            raise NotValidServer
        # set url after connection succeeds
        self._url = url
        # set session id
        if session:
            self.serverobj.get_default_session().guid = session
        self._session_guid = self.serverobj.get_default_session().guid
        return

    def start(
        self,
        username: str = "nexus",
        password: str = "cei",
        create_db: bool = False,
        error_if_create_db_exists: bool = False,
        exit_on_close: bool = False,
        delete_db: bool = False,
    ) -> str:
        """
        Start a new service.

        Parameters
        ----------
        username : str, optional
            Username for the service. The default is ``"nexus"``.
        password : str, optional
            Password for the service. The default is ``"cei"``.
        create_db : bool, optional
            Whether to create a new database before starting the service on top
            of it. The default is ``False``. If ``True``, this method creates a
            database in the directory specified by the ``db_directory``
            parameter and starts the service on top of it. An error is raised
            if the directory specified by the ``db_directory`` parameter
            already exists and is not empty.
        error_if_create_db_exists : bool, optional
            Whether to raise an error if the ``create_db`` parameter is set to
            ``True`` and the database already exists. The default is ``False``,
            in which case the ``start()`` method uses the database found instead
            of creating one.
        exit_on_close : bool, optional
            Whether to automatically shut down the service when exiting the script.
            The default is ``False``, in which case the service continues to run.
        delete_db : bool, optional
            Whether to automatically delete the database when exiting the script. The
            default is ``False``. This parameter is valid only if this parameter and
            the ``exit_on_close`` parameter are set to ``True``.

        Returns
        -------
        str
            ID of the connected session.


        Raises
        ------
        DatabaseDirNotProvidedError
            There is no database directory associated with the Service.
        CannotCreateDatabaseError
            Error when creating the database.
        AlreadyConnectedError
            Object is already connected to a running ADR service.
        StartingServiceError
            Can not start the ADR service.
        NotValidServer
            Can not validate the current ADR service.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            installation_dir = r'C:\\Program Files\\ANSYS Inc\\v232'
            adr_service = adr.Service(ansys_installation = installation_dir,
            db_directory = r'D:\\tmp\\new_db', port = 8020)
            session_guid = adr_service.start()
        """
        if self._db_directory is None:
            self.logger.error("Error: There is no database associated with this Service.\n")
            raise DatabaseDirNotProvidedError

        if exit_on_close or self._docker_launcher:
            atexit.register(self.stop)
            if exit_on_close and delete_db:
                self._delete_db = True

        if self._url is not None:
            self.logger.error("Already connected to a service.\n")
            raise AlreadyConnectedError

        if create_db:
            # create the database if instructed to do so
            do_create = True
            if os.path.isdir(self._db_directory):
                # If the directory exists, check that it is empty. If not, error out
                list_files = os.listdir(self._db_directory)
                if len(list_files) > 0:
                    if error_if_create_db_exists:
                        self.logger.error(
                            f"The directory for the new database {self._db_directory} is "
                            "not empty.\n"
                        )
                        raise CannotCreateDatabaseError
                    else:
                        do_create = False
            if do_create:
                if self._docker_launcher:
                    try:
                        create_output = self._docker_launcher.create_nexus_db()
                    except Exception:  # pragma: no cover
                        self._docker_launcher.cleanup()
                        self.logger.error(
                            f"Error creating the database at the path {self._db_directory} in the "
                            "Docker container.\n"
                        )
                        raise CannotCreateDatabaseError
                    for f in ["db.sqlite3", "view_report.nexdb"]:
                        db_file = os.path.join(self._db_directory, f)
                        if not os.path.isfile(db_file):
                            self._docker_launcher.cleanup()
                            self.logger.error(
                                "Error creating the database using Docker at the path "
                                + f"{self._db_directory}.\n"
                                + f"Cannot find file {db_file}.\n"
                            )
                            self.logger(create_output)
                            raise CannotCreateDatabaseError
                else:
                    create_err = report_remote_server.create_new_local_database(
                        parent=None,
                        directory=self._db_directory,
                        raise_exception=False,
                        exec_basis=self._ansys_installation,
                        ansys_version=self._ansys_version,
                    )
                    if create_err is False:
                        self.logger.error(
                            f"Error creating the database at the path {self._db_directory}.\n"
                        )
                        raise CannotCreateDatabaseError

        # launch the server
        if self._docker_launcher:
            try:
                self._docker_launcher.launch_nexus_server(
                    port=self._port, allow_iframe_embedding=True
                )
            except Exception as e:  # pragma: no cover
                self.logger.error(
                    f"Error starting the service in the Docker container.\n{str(e)}\n"
                )
                self.logger.error(f"Service started on port {self._port}")
                raise StartingServiceError
            self.serverobj = report_remote_server.Server(
                url=f"http://127.0.0.1:{self._port}",
                username=username,
                password=password,
                ansys_version=self._ansys_version,
            )

        else:  # pragma: no cover
            # we're not using docker
            self.serverobj = report_remote_server.Server()
            self.__checkport__()
            launched = False
            launch_kwargs = {
                "directory": self._db_directory,
                "port": self._port,
                "connect": self.serverobj,
                "username": username,
                "password": password,
                "raise_exception": True,
                "exec_basis": self._ansys_installation,
                "ansys_version": self._ansys_version,
            }
            if int(self._ansys_version) >= 231:
                launch_kwargs.update({"allow_iframe_embedding": True})

            try:
                launched = report_remote_server.launch_local_database_server(None, **launch_kwargs)
            except Exception as e:
                self.logger.error(
                    "Error starting the service.\n"
                    + f"db_directory: {self._db_directory}\n"
                    + f"{str(e)}\n"
                )
                raise StartingServiceError

            if not launched:
                self.logger.error(
                    f"Error starting the service.\ndb_directory: {self._db_directory}\n"
                )
                raise StartingServiceError

        if not self.serverobj.validate():
            self.logger.error(
                f"Error validating the service.\ndb_directory: {self._db_directory}\n"
            )
            raise NotValidServer

        self._url = self.serverobj.get_URL()
        self._session_guid = self.serverobj.get_default_session().guid
        return self._session_guid

    def stop(self) -> None:
        """
        Stop the service connected to the session.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            installation_dir = r'C:\\Program Files\\ANSYS Inc\\v232'
            adr_service = adr.Service(ansys_installation = installation_dir, port = 8020)
            session_guid = adr_service.start(username = 'admin', password = 'mypsw',
            db_directory ='/tmp/dbase')
            adr_service.stop()
        """

        if self.serverobj is None:
            self.logger.warning(
                "There is no service connected to the current session. " "Can't shut it down.\n"
            )

        v = False
        try:
            v = self.serverobj.validate()
        except Exception:
            pass
        if v is False:
            self.logger.error("Error validating the connected service. Can't shut it down.\n")
        else:
            # If coming from a docker image, clean that up
            try:
                if self._docker_launcher:
                    self.logger.info("Shutting down container.\n")
                    self._docker_launcher.cleanup(close=True)
                    self._docker_launcher = None
                else:
                    self.logger.info("Shutting down service.\n")
                    self.serverobj.stop_local_server()
            except Exception as e:
                self.logger.error(f"Problem shutting down container/service.\n{str(e)}\n")
                pass

        if self._delete_db and self._db_directory:
            try:
                if os.path.isdir(self._db_directory):
                    # give the server time to shutdown before trying to delete the db dir
                    time.sleep(5)
                    self.logger.info(f"Deleting directory: {self._db_directory}\n")
                    shutil.rmtree(self._db_directory)
            except Exception as e:
                self.logger.warning(f"Problem deleting directory {self._db_directory}\n{str(e)}\n")
                pass

        if self._data_directory:
            try:
                if os.path.isdir(self._data_directory):
                    self.logger.info(f"Deleting directory: {self._data_directory}\n")
                    shutil.rmtree(self._data_directory)
            except Exception as e:
                self.logger.warning(
                    f"Problem deleting directory {self._data_directory}\n{str(e)}\n"
                )
                pass

        self.serverobj = None
        self._url = None

    def visualize_report(
        self,
        report_name: str | None = "",
        new_tab: bool | None = False,
        filter: str | None = "",
        item_filter: str | None = "",
    ) -> None:
        """
        Render the report.

        Parameters
        ----------
        report_name : str, optional
            Name of the report. the default is ``""``, in which
            case all items assigned to the session are shown.
        new_tab : bool, optional
            Whether to render the report in a new tab if the current environment
            is a Jupyter notebook. The default is ``False``, in which case the
            report is rendered in the current location. If the environment is
            not a Jupyter notebook, the report is always rendered in a new tab.
        filter : str, optional
            DEPRECATED. Use item_filter instead.
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query in the documentation for Ansys Dynamic Reporting.
        item_filter : str, optional
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query in the documentation for Ansys Dynamic Reporting.

        Returns
        -------
        Report
            Rendered report.

        Raises
        ------
        ConnectionToServiceError
            There is no ADR service associated with the current object.
        MissingReportError
            The service does not have a report with the input name.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            installation_dir = r'C:\\Program Files\\ANSYS Inc\\v232'
            adr_service = adr.Service(ansys_installation = installation_dir)
            ret = adr_service.connect()
            my_img = adr_service.create_item()
            my_img.item_image = 'Image_to_push_on_report'
            adr_service.visualize_report()
        """
        if filter:
            warnings.warn(
                "The 'filter' parameter is deprecated. Use 'item_filter' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            item_filter = filter
        if self.serverobj is None:
            self.logger.error("No connection to any service")
            raise ConnectionToServiceError
        url = self._url + "/reports/report_display/?"
        if report_name:
            all_reports = self.serverobj.get_objects(objtype=report_objects.TemplateREST)
            if report_name not in [x.name for x in all_reports]:
                self.logger.error("report_name must exist")
                raise MissingReportError
            reportobj = [x for x in all_reports if x.name == report_name][0]
            url += "view=" + reportobj.guid + "&"
        url += "usemenus=off"
        query_str = ""
        if item_filter:
            query_str = build_query_url(logger=self.logger, item_filter=item_filter)
        else:
            query_str = ""
        url += query_str
        if in_ipynb() and not new_tab:
            display(IFrame(src=url, width=1000, height=800))
        else:
            webbrowser.open_new(url)

    def create_item(self, obj_name: str | None = "default", source: str | None = "ADR") -> Item:
        """
        Create an item that gets automatically pushed into the database.

        Parameters
        ----------
        obj_name : str, optional
            Name of the item. The default is ``"default"``.
        source : str, optional
            Name of the source to generate the item from. The default is ``"ADR"``,
            which is Ansys Dynamic Reporting.

        Returns
        -------
        Object
            Item object.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_img = adr_service.create_item()
        """
        a = Item(service=self, obj_name=str(obj_name), source=source)
        return a

    def query(
        self, query_type: str = "Item", filter: str | None = "", item_filter: str | None = ""
    ) -> list:
        """
        Query the database.

        .. _Query: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v251/en/adr_ug/adr_ug_query_expressions.html

        Parameters
        ----------
        query_type : str, optional
            Type of objects to query. The default is ``"Item"``. Options are ``"Item"``,
            ``"Session"``, and ``"Dataset"``.
        filter : str, optional
            DEPRECATED. Use item_filter instead.
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query in the documentation for Ansys Dynamic Reporting.
        item_filter : str, optional
            Query string for filtering. The default is ``""``. The syntax corresponds
            to the syntax for Ansys Dynamic Reporting. For more information, see
            _Query in the documentation for Ansys Dynamic Reporting.

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
            imgs = adr_service.query(query_type='Item', item_filter='A|i_type|cont|image;')
        """
        if filter:
            warnings.warn(
                "The 'filter' parameter is deprecated. Use 'item_filter' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            item_filter = filter
        queried_items = []
        valid = check_filter(item_filter=item_filter)
        if valid is False:
            self.logger.warning("Warning: item_filter string is not valid. Will be ignored.")
            item_filter = ""
        if query_type == "Item":
            org_queried_items = self.serverobj.get_objects(
                objtype=report_objects.ItemREST, query=item_filter
            )
            for i in org_queried_items:
                tmp_item = Item(service=self, obj_name=i.name, source=i.source)
                item_attr = dict_items.get(i.type, "item_text")
                if item_attr == "item_table":
                    assign_error = tmp_item.__setattr__(
                        "item_table", i.payloaddata["array"], only_set=True
                    )
                else:
                    assign_error = tmp_item.__setattr__(item_attr, i.payloaddata, only_set=True)
                if assign_error != 0:
                    self.logger.warning(f"Could not set the payload for item {i.name}")
                else:
                    tmp_item.item = i
                    tmp_item.type = type_maps.get(item_attr, "text")
                    tmp_item.__copyattrs__(dataitem=i)
                    queried_items.append(tmp_item)
        elif query_type == "Session":
            queried_items = self.serverobj.get_objects(
                objtype=report_objects.SessionREST, query=item_filter
            )
        elif query_type == "Dataset":
            queried_items = self.serverobj.get_objects(
                objtype=report_objects.DatasetREST, query=item_filter
            )
        return queried_items

    def delete(self, items: list) -> None:
        """
        Delete objects from the database.

        Parameters
        ----------
        items : list
            List of objects to delete. The objects can be of one of these types:
            ``"Item"``, ``Report``, ``"Session"`` or ``Dataset``.

            .. note:: Deleting a session or a dataset also deletes all items
               associated with the session or dataset. Deleting a Report also
               deletes all its children.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation=r'C:\\Program Files\\ANSYS Inc\\v232')
            adr_service.connect(url='http://localhost:8020')
            all_items = adr_service.query(type='Item')
            adr_service.delete(all_items)
            my_report = adr_service.get_report(report_name='My Report')
            adr_service.delete([my_report])
        """
        if type(items) is not list:
            self.logger.error("Error: passed argument is not a list")
            raise TypeError
        items_to_delete = [x.item for x in items if type(x) is Item]
        reports_to_delete = [x for x in items if type(x) is Report]
        if reports_to_delete:
            self.logger.warning(
                "Warning: Report deletion will result in deletion of " "all its children templates"
            )
            items_to_delete.extend([x.report for x in reports_to_delete])
        # Check the input
        not_items = [x for x in items if (type(x) is not Item) and (type(x) is not Report)]
        if not_items:  # pragma: no cover
            session = [x for x in not_items if type(x) is report_objects.SessionREST]
            if session:
                self.logger.warning(
                    "Warning: Session deletion will result in deletion of "
                    "all Items associated with it"
                )
                items_to_delete.extend(session)
            dataset = [x for x in not_items if type(x) is report_objects.DatasetREST]
            if dataset:
                self.logger.warning(
                    "Warning: Dataset deletion will result in deletion of "
                    "all Items associated with it"
                )
                items_to_delete.extend(dataset)
            not_nexus_items = [
                x
                for x in not_items
                if type(x) is not report_objects.SessionREST
                and type(x) is not report_objects.DatasetREST
            ]
            if not_nexus_items:
                self.logger.warning(
                    "Warning: input list contains elements that can not be "
                    "deleted via this method. They will be skipped"
                )
        # Finally removing from database
        try:
            _ = self.serverobj.del_objects(items_to_delete)
        except Exception as e:
            self.logger.warning(f"Error in deleting items: {e}")

    def get_report(self, report_name: str) -> Report:
        """
        Get a ``Report`` item that corresponds to a report in the database with a given
        name.

        Parameters
        ----------
        report_name : str
            Name of the report in the database. The name must be for a top-level report, not a name
            of a subsection within a report.

        Returns
        -------
        Object
            Report object. If no such object can be found, ``None`` is returned.

        Raises
        ------
        ConnectionToServiceError
            There is no ADR service associated with the current object.
        MissingReportError
            The service does not have a report with the input name.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation=r'C:\\Program Files\\ANSYS Inc\\v232')
            adr_service.connect(url='http://localhost:8020')
            my_report = adr_service.get_report(report_name = "Top Level Report')
        """
        if self.serverobj is None:
            self.logger.error("Error: no connection to any service")
            raise ConnectionToServiceError
        my_report = Report(service=self, report_name=report_name)
        success = my_report.__find_report_obj__()
        if success:
            return my_report
        else:
            self.logger.error("Error: there is no report with the name {report_name}.")
            raise MissingReportError

    def get_list_reports(self, r_type: str | None = "name") -> list:
        """
        Get a list of top-level reports in the database.

        This method can get either a list of the names of the top-level reports
        or a list of ``Report`` items corresponding to these reports.

        Parameters
        ----------
        r_type : str, optional
            Type of object to return. The default is ``"name"``, which returns
            a list of the names of the reports. If you set the value
            for this parameter to ``"report"``, this method returns a list of
            the ``Report`` items corresponding to these reports.

        Returns
        -------
        list
            List of the top-level reports in the database. The list can be of the names
            of these reports or the ``Report`` items corresponding to these reports.

        Raises
        ------
        ConnectionToServiceError
            There is no ADR service associated with the current object.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation=r'C:\\Program Files\\ANSYS Inc\\v232')
            adr_service.connect(url='http://localhost:8020')
            top_reports = adr_service.get_list_reports()
        """
        supported_types = ["name", "report"]
        r_list = []
        if self.serverobj is None:
            self.logger.error("Error: no connection to any service")
            raise ConnectionToServiceError
        elif r_type in supported_types:
            all_reports = self.serverobj.get_objects(objtype=report_objects.TemplateREST)
            if r_type == "name":
                r_list = [x.name for x in all_reports if x.parent is None]
            elif r_type == "report":
                reports = [x for x in all_reports if x.parent is None]
                for i in reports:
                    r_list.append(Report(service=self, report_name=i.name))
        else:
            self.logger.warning("Invalid input: r_type needs to be name or report")
        return r_list

    def load_templates(self, json_file_path: str) -> None:
        """
        Load templates given a JSON-formatted file.
        There will be some interactive inputs if required.

        Parameters
        ----------
        json_file_path : str
            Path of the JSON file to be loaded.

        Returns
        -------
            None.

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr

            adr_service = adr.Service(ansys_installation=r'C:\\Program Files\\ANSYS Inc\\v232')
            adr_service.connect(url='http://localhost:8020', username = "admin", password = "mypassword")
            adr_service.load_templates(r'C:\\tmp\\my_json_file.json')
        """
        try:
            with open(json_file_path, encoding="utf-8") as file:
                templates_json = json.load(file)
        except json.JSONDecodeError as je:
            self.logger.error(
                "The loaded JSON file does not have a correct JSON format!\n"
                f"Please check your JSON file path.\nError details: {je}"
            )
            return

        # Address root name conflict
        # 1. Find the root
        for template_attr in templates_json.values():
            if template_attr["parent"] is None:
                loaded_root_name = template_attr["name"]
                root_attr = template_attr
                break

        # 2. Compare with the existing root template(s)
        templates = self.serverobj.get_objects(objtype=report_objects.TemplateREST)
        existing_root_names = set()
        for template in templates:
            if template.master:
                existing_root_names.add(template.name)

        if loaded_root_name in existing_root_names:
            num_copies = 1
            for name in existing_root_names:
                if (
                    name.startswith(loaded_root_name)
                    and len(name) > len(loaded_root_name) + 2
                    and name[len(loaded_root_name) + 1] == "("
                ):
                    num_copies += 1
            renamed_root_name = f"{loaded_root_name} ({num_copies + 1})"
            self.logger.warning(
                "The root name in the JSON conflicts with one of the existing templates': "
                f"'{loaded_root_name}'. In order to proceed, it is automatically renamed to: '{renamed_root_name}'"
            )
            root_attr["name"] = renamed_root_name

        try:
            self.serverobj.load_templates(templates_json, self.logger)
        except adr_utils_exceptions.TemplateEditorJSONLoadingError as e:
            self.logger.error(
                "The loaded JSON file does not conform to the schema!\nPlease check your JSON file.\n"
                f"Error details: {e}"
            )

            # Clean up already-put template objects
            all_templates = self.serverobj.get_objects(objtype=report_objects.TemplateREST)
            for template in all_templates:
                if template.name == loaded_root_name:
                    self.serverobj.del_objects(template)

    def __checkport__(self):
        """
        Internal method to check if a port is already being used and if yes, change
        self._port to an other free port.

        Parameters
        ----------
        None
        Returns
        -------
        None
        """
        if report_utils.is_port_in_use(self._port):
            self.logger.warning(
                f"Warning: port {self._port} is already in use. Replace with a new port\n"
            )
            self._port = report_utils.find_unused_ports(count=1, start=self._port)[0]
