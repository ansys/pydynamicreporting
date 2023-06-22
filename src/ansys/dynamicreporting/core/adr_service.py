"""
Service module.

Module to create a ADR Service instance

Examples::

    import ansys.dynamicreporting.core as adr
    adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
    ret = adr_service.connect()
    my_img = adr_service.create_item()
    my_img.item_image = 'Image_to_push_on_report'
    adr_service.visualize_report()

::
Visualization of the default report
"""

import atexit
import os
import re
import shutil
import tempfile
import time
from typing import Optional

from requests import codes

try:
    from IPython.display import IFrame
except ImportError:  # pragma: no cover
    pass

import webbrowser

from ansys.dynamicreporting.core.utils import report_objects, report_remote_server

from .adr_item import Item
from .adr_report import Report
from .adr_utils import dict_items, get_logger, in_ipynb, type_maps
from .constants import DOCKER_DEFAULT_PORT, DOCKER_REPO_URL
from .docker_support import DockerLauncher
from .exceptions import (
    AnsysVersionAbsentError,
    CannotCreateDatabaseError,
    DatabaseDirNotProvidedError,
    InvalidAnsysPath,
)


# Main class
class Service:
    """
    Class to create a connection to a dynamic reoprting service.

    Examples
    --------
    Initialize the class and connect to an Ansys Dynamic Reporting service running on
    localhost on port 8010,  with username = admin and password = mypsw,
    using a local Ansys installation::

        import ansys.dynamicreporting.core as adr
        installation_dir = r'C:\\Program Files\\ANSYS Inc\\v232'
        adr_service = adr.Service(ansys_installation = installation_dir)
        ret = adr_service.connect(url = "http://localhost:8010", username = 'admin', password = 'mypsw')
    """

    def __init__(
        self,
        ansys_version: int = None,
        docker_image: str = DOCKER_REPO_URL,
        data_directory: str = None,
        db_directory: str = None,
        port: int = DOCKER_DEFAULT_PORT,
        logfile: str = None,
        ansys_installation: Optional[str] = None,
    ) -> None:
        """
        Initialize a dynamic reporting object.

        Parameters
        ----------
        ansys_installation : str
            Optional argument. This is needed only if the Service instance will be used to
            launch a dynamic reporting service. Not needed if connecting to an existing service.
            Location of the ANSYS installation, including the version directory. Example:
            r'C:\\Program Files\\ANSYS Inc\\v232'
            If there is no local installation and the user wants to use the docker image instead,
            enter 'docker'
            Default:  None
        docker_image : str
            Location of the docker image for Ansys dynamic reporting. Used only if ansys_installation
            is 'docker'
            Default: ghcr.io/ansys-internal/nexus
        data_directory: str
            Host directory where to store temporary copy of files from Docker
            To be used only if ansys_installation is 'docker'
            Default: None, which corresponds to TMP_DIR
        db_directory: str
            Host directory containing the database.
        port: int
            Service port number. Default: 8000
        logfile: str
            Location for the log file. If None, no logging. If 'stdout', use stdout
            Default = None
        """
        self.serverobj = None
        self._session_guid = ""
        self._url = None
        self.logger = get_logger(logfile)
        self._ansys_version = ansys_version
        self._data_directory = None
        self._db_directory = db_directory
        self._delete_db = False
        self._port = port
        self._container = None
        self._docker_image = docker_image
        self._ansys_installation = ansys_installation

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
                self._container = DockerLauncher(docker_image_name=docker_image)
            except Exception as e:
                self.logger.error(f"Error initializing the Docker Container object.\n{str(e)}\n")
                raise e

            try:
                self._container.pull()
            except Exception as e:
                self.logger.error(
                    f"Error pulling the Docker image {self._docker_image}.\n{str(e)}\n"
                )
                raise e

            try:
                # start the container and map specified host directory into the
                # container.  The location in the container is always /host_directory/."
                self._container.start(
                    host_directory=self._data_directory,
                    db_directory=self._db_directory,
                    port=self._port,
                )
            except Exception as e:  # pragma: no cover
                self.logger.error(f"Error starting the Docker Container.\n{str(e)}\n")
                raise e

        elif ansys_installation:  # pragma: no cover
            # verify path
            if not os.path.isdir(ansys_installation):
                raise InvalidAnsysPath(ansys_installation)

        if ansys_installation != "docker" and ansys_installation is not None:  # pragma: no cover
            # Not using docker
            # Backward compatibility: if the path passed is only up to the version directory,
            # append the CEI directory
            if ansys_installation.endswith("CEI") is False:
                ansys_installation = os.path.join(ansys_installation, "CEI")
                self._ansys_installation = ansys_installation
                # verify new path
                if not os.path.isdir(ansys_installation):
                    raise InvalidAnsysPath(ansys_installation)
            if self._ansys_version is None:
                # try to get version from install path
                matches = re.search(r".*v([0-9]{3}).*", ansys_installation)
                try:
                    self._ansys_version = int(matches.group(1))
                except IndexError:
                    raise AnsysVersionAbsentError

    @property
    def session_guid(self):
        """The GUID of the session associated with the service."""
        if self._session_guid == "":
            self.logger.error("No session attached to this instance.")
        else:
            return self._session_guid

    @property
    def url(self):
        """URL of the service."""
        return self._url

    def connect(
        self,
        url: str = f"http://localhost:{DOCKER_DEFAULT_PORT}",
        username: str = "nexus",
        password: str = "cei",
        session: Optional[str] = "",
    ) -> bool:
        """
        Connect to a running service.

        Parameters
        ----------
        url : str
            Service url. Default: http://localhost:8000
        username : str
            Username of the service. Default: nexus
        password : str
            Password of the service. Default: cei
        session : str
            GUID of the session to work with. All created items will be pushed on that session.
            Visualizations will all be filtered to only items for this session. Default: '', which
            will create a new session GUID

        Returns
        -------
        bool
            True: Connection established / False: Could not establish connection

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect(url="http://localhost:8010", username='admin', password = 'mypsw')
        """
        if self._url is not None:  # pragma: no cover
            self.logger.warning("Already connected to a dynamic reporting service.\n")
            return True
        self.serverobj = report_remote_server.Server(url=url, username=username, password=password)
        try:
            self.serverobj.validate()
        except Exception:
            self.logger.error("Can not validate dynamic reporting server.\n")
            return False
        # set url after connection succeeds
        self._url = url
        # set session id
        if session:
            self.serverobj.get_default_session().guid = session
        self._session_guid = self.serverobj.get_default_session().guid
        return True

    def start(
        self,
        username: str = "nexus",
        password: str = "cei",
        create_db: bool = False,
        error_if_create_db_exists: bool = True,
        exit_on_close: bool = False,
        delete_db: bool = False,
    ) -> str:
        """
        Start a new service.

        Parameters
        ----------
        username : str
            Username of the service. Default: nexus
        password : str
            Password of the service. Default: cei
        create_db : bool
            Flag if you want to create a new database before starting the service on top
            of it. If True, then the method will create a database at db_dir and start the
            service on top of it. Error if the directory db_dir already exists and is not empty.
            Default: False
        error_if_create_db_exists : bool
            If true, start() will return an error if create_db is true and the database already
            exists.  If false, start() will use the database found instead of creating a new one.
        exit_on_close : bool
            Flag if you want the launched service to automatically shut down when exiting
            the script. Default: False = the service will keep running
        delete_db : bool
            Flag if you want the database to be automatically deleted when exiting the script.
            Only valid if exit_on_close is also set to True. Default: False = do not delete
            database

        Returns
        -------
        str
            ID of the connected session. If the service could not be started
            this will be '0'

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            installation_dir = r'C:\\Program Files\\ANSYS Inc\\v232'
            adr_service = adr.Service(ansys_installation = installation_dir, port = 8020)
            session_guid = adr_service.start()
        """
        if exit_on_close or self._container:
            atexit.register(self.stop)
            if exit_on_close and delete_db:
                self._delete_db = True

        session_id = "0"
        if self._url is not None:
            self.logger.error("Already connected to a service.\n")
            return session_id

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
                        return session_id
                    else:
                        do_create = False
            if do_create:
                if self._container:
                    create_output = ""
                    try:
                        create_output = self._container.create_nexus_db()
                    except Exception:  # pragma: no cover
                        self._container.stop()
                        self.logger.error(
                            f"Error creating the database at the path {self._db_directory} in the "
                            "Docker container.\n"
                        )
                        return session_id
                    for f in ["db.sqlite3", "view_report.nexdb"]:
                        db_file = os.path.join(self._db_directory, f)
                        if not os.path.isfile(db_file):
                            self._container.stop()
                            self.logger.error(
                                "Error creating the database using Docker at the path "
                                + f"{self._db_directory}.\n"
                                + f"Cannot find file {db_file}.\n"
                            )
                            self.logger(create_output)
                            return session_id
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
                        return session_id

        # launch the server
        if self._container:
            try:
                self._container.launch_nexus_server(
                    username=username,
                    password=password,
                    allow_iframe_embedding=True,
                )
            except Exception as e:  # pragma: no cover
                self.logger.error(
                    f"Error starting the service in the Docker container.\n{str(e)}\n"
                )
                self.logger.error(f"Service started on port {self._port}")
                return session_id
            self.serverobj = report_remote_server.Server(
                url=f"http://127.0.0.1:{self._port}", username=username, password=password
            )

        else:  # pragma: no cover
            # we're not using docker
            self.serverobj = report_remote_server.Server()
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
            if self._ansys_version >= 231:
                launch_kwargs.update({"allow_iframe_embedding": True})

            try:
                launched = report_remote_server.launch_local_database_server(None, **launch_kwargs)
            except Exception as e:
                self.logger.error(
                    "Error starting the service.\n"
                    + f"db_directory: {self._db_directory}\n"
                    + f"{str(e)}\n"
                )
                return session_id

            if not launched:
                self.logger.error(
                    f"Error starting the service.\ndb_directory: {self._db_directory}\n"
                )
                return session_id

        if not self.serverobj.validate():
            self.logger.error(
                f"Error validating the service.\ndb_directory: {self._db_directory}\n"
            )
            return session_id

        self._url = self.serverobj.get_URL()
        self._session_guid = self.serverobj.get_default_session().guid
        return self._session_guid

    def stop(self) -> bool:
        """
        Stop the service connected to this session.

        Returns
        -------
        bool
            True if able to stop the service. False otherwise

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            installation_dir = r'C:\\Program Files\\ANSYS Inc\\v232'
            adr_service = adr.Service(ansys_installation = installation_dir, port = 8020)
            session_guid = adr_service.start(username = 'admin', password = 'mypsw',db_dir ='/tmp/dbase')
            ret_stop = adr_service.stop()
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
                if self._container:
                    self.logger.info("Told service Container to shutdown.\n")
                    self._container.stop()
                    self._container = None
                else:
                    self.logger.info("Told service to shutdown.\n")
                    self.serverobj.stop_local_server()
            except Exception as e:
                self.logger.error(f"Problem shutting down service.\n{str(e)}\n")
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

        return True

    def __check_filter__(self, filter: str = ""):
        """
        Verify validity of query string.

        Parameters
        ----------
        filter : str
            Query filter. Syntax corresponds to the Ansys dynamic reporting syntax,
            which can be found at `this`_ link.

            .. _this: https://nexusdemo.ensight.com/docs/html/Nexus.html?QueryExpressions.html

        Returns
        -------
        bool
            True if filter string is valid. False otherwise.
        """
        for query_stanza in filter.split(";"):
            if len(query_stanza) > 0:
                if len(query_stanza.split("|")) != 4:
                    return False
                if query_stanza.split("|")[0] not in ["A", "O"]:
                    return False
                if query_stanza.split("|")[1][0:2] not in ["i_", "s_", "d_", "t_"]:
                    return False
        return True

    def visualize_report(
        self,
        report_name: Optional[str] = "",
        new_tab: Optional[bool] = False,
        filter: Optional[str] = "",
    ) -> None:
        """
        Render the report.

        Parameters
        ----------
        report_name : str
            Name of the report to visualize. If empty, show all the items
            assigned to the current session
        new_tab : bool
            If the current environment is a Jupyter notebook, then set if the report should be
            rendered in the current location (False, default) or on a new tab (True).
            If the environment is not a Jupyter notebook, always display by opening a new tab.
        filter : str
            Query filter. Syntax corresponds to the Ansys dynamic reporting syntax, which can
            be found at `this`_ link. Default: Empty, aka no filter

            .. _this: https://nexusdemo.ensight.com/docs/html/Nexus.html?QueryExpressions.html

        Returns
        -------
            Rendering of the report.

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
        if self.serverobj is None:
            self.logger.error("No connection to any report")
            return
        url = self._url + "/reports/report_display/?"
        if report_name:
            all_reports = self.serverobj.get_objects(objtype=report_objects.TemplateREST)
            if report_name not in [x.name for x in all_reports]:
                self.logger.error("report_name must exist")
                return
            reportobj = [x for x in all_reports if x.name == report_name][0]
            url += "view=" + reportobj.guid + "&"
        url += "usemenus=off"
        query_str = ""
        if filter:
            valid = self.__check_filter__(filter)
            if valid is False:
                self.logger.warning("Warning: filter string is not valid. Will be ignored.")
            else:
                query_str = "&query="
                for q_stanza in filter.split(";"):
                    if len(q_stanza) > 1:
                        each_item = q_stanza.split("|")
                        query_str += each_item[-4] + "%7C" + each_item[-3]
                        query_str += "%7C" + each_item[-2]
                        query_str += "%7C" + each_item[-1]
        url += query_str
        if in_ipynb() and not new_tab:
            display(IFrame(src=url, width=1000, height=800))
        else:
            webbrowser.open_new(url)

    def create_item(
        self, obj_name: Optional[str] = "default", source: Optional[str] = "ADR"
    ) -> Item:
        """
        Create an item that gets automatically pushed into the database.

        Parameters
        ----------
        obj_name : str
            Name of the item. Default : 'default'
        source : str
            Name of the source the item is being generated from. Default : 'ADR'

        Returns
        -------
            Item object

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            my_img = adr_service.create_item()
        """
        a = Item(service=self, obj_name=obj_name, source=source)
        return a

    def query(self, query_type: str = "Item", filter: Optional[str] = "") -> list:
        """
        Query the database.

        Parameters
        ----------
        query_type : str
            Type of objects to query. Options: Item, Session, Dataset. Default: Item
        filter : str
            Query filter. Syntax corresponds to the Ansys dynamic reporting syntax, which
            can be found at `this`_ link. Default: Empty, aka no filter

            .. _this: https://nexusdemo.ensight.com/docs/html/Nexus.html?QueryExpressions.html

        Returns
        -------
        list
            List of queried objects

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation = r'C:\\Program Files\\ANSYS Inc\\v232')
            ret = adr_service.connect()
            imgs = adr_service.query(type='Item', filter='A|i_type|cont|image;')
        """
        queried_items = []
        valid = self.__check_filter__(filter)
        if valid is False:
            self.logger.warning("Warning: filter string is not valid. Will be ignored.")
            filter = ""
        if query_type == "Item":
            org_queried_items = self.serverobj.get_objects(
                objtype=report_objects.ItemREST, query=filter
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
                objtype=report_objects.SessionREST, query=filter
            )
        elif query_type == "Dataset":
            queried_items = self.serverobj.get_objects(
                objtype=report_objects.DatasetREST, query=filter
            )
        return queried_items

    def delete(self, items: list) -> bool:
        """
        Delete items from the database.

        Parameters
        ----------
        items : list
            List of objects to delete. The objects can be of type Item, Session or Dataset.
            Note that deleting a Session or a Dataset will also delete all the Item
            associated with them.

        Returns
        -------
        bool
            True if able to delete all items. False otherwise

        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation=r'C:\\Program Files\\ANSYS Inc\\v232')
            adr_service.connect(url='http://localhost:8020')
            all_items = adr_service.query(type='Item')
            adr_service.delete(all_items)
        """
        ret = codes.bad
        if type(items) is not list:
            self.logger.error("Error: passed argument is not a list")
            return False
        items_to_delete = [x.item for x in items if type(x) is Item]
        # Check the input
        not_items = [x for x in items if type(x) is not Item]
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
            ret = self.serverobj.del_objects(items_to_delete)
        except Exception as e:
            self.logger.warning(f"Error in deleting items: {e}")
        return ret == codes.ok

    def get_report(self, report_name: str) -> Report:
        """
        Get a Report item that corresponds to a Report in the database with the passed
        name.

        Parameters
        ----------
        report_name : str
            Name of the report in the database. This needs to be a top level report, not the name
            of a subsection of the report

        Returns
        -------
        Report
            Report object. If no such object can be found, return None

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
            return None
        my_report = Report(service=self, report_name=report_name)
        return my_report

    def get_list_reports(self, r_type: Optional[str] = "name") -> list:
        """
        Get the list of top level reports in the database, either as report names or
        Report.

        Parameters
        ----------
        r_type : str
            Type of object to return. If name, return a list of the names of the reports. If
            'report', return a list of the Report items corresponding to the reports.
            Default: 'name'

        Returns
        -------
        list
            List of the top-level report in the database. Can be a list of the names or a
            list of the Report corresponding to the top reports.

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
            return None
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


#    def create_report(self, report_name: Optional[str] = "") -> None:
#        """Create a top level report. Report filter filters out all items
#
#        Parameters
#        ----------
#        report_name : str
#            Name of the report. Must not be empty and must not match any existing report name
#
#        Returns
#        -------
#            None
#        """
#        if report_name == "":
#            self.logger.error("Need a report_name input")
#            return
#        # Verify there isn't already a template with such a name
#        all_reports = self.serverobj.get_objects(
#            objtype=core.report_objects.TemplateREST
#        )
#        if report_name in [x.name for x in all_reports]:
#            self.logger.error("report_name must not already exist")
#            return
#        new_template = self.serverobj.create_template(
#            name=report_name, parent=None, report_type="Layout:panel"
#        )
#        new_template.set_filter("A|i_name|cont|__filterallout__;")
#        self.serverobj.put_objects(new_template)
#
#    def create_slider(self,images: Optional[list] = None, report_name: Optional[str] = "") -> None:
#        """Create a slider template and add it to a specific report

#        Parameters
#        ----------
#        images : list
#            list of images for the slider. Each entry is a dictionary with the following keys:
#            'image': file that contains the image
#            each additional key is information that represents the image. Example:
#            'var': variable the parts is colored by
#            'time': value of timestep the snapshot is taken at
#            These tags will be used to create the slider controllers
#        report_name : str
#            name of the report under which the slider needs to be placed
#        """
#        Returns
#        -------
#            None

#        if images is None:
#            images = []
#        if not images:
#            self.logger.warning("No images passed")
#            return
#        if not report_name:
#            self.logger.error("Need to input a report name")
#            return
#        uniquetag = str(uuid.uuid1())
#        list_tags = []
#        all_items = []
#        for index_i, i in enumerate(images):
#            if index_i * 10 % len(images) == 0:
#                self.logger.info(f"Loading slider images progress: {index_i * 100 / len(images)}%")
#            if "image" not in i.keys():
#                self.logger.error("All entries must contain the image key")
#                return
#            a = Item(nexus=self)
#            a.item_image = i["image"]
#            for local_key in i.keys():
#                if local_key != "image":
#                    # Apparently, if the tag value is 0 / 1, Nexus interprets it as True/False bool
#                    # Make it into a string to avoid it
#                    if i[local_key] == 0.0 or i[local_key] == 1.0:
#                        a.item.add_tag(local_key, str(i[local_key]))
#                    else:
#                        a.item.add_tag(local_key, i[local_key])
#                    if local_key not in [x.split("|")[0] for x in list_tags]:
#                        if type(i[local_key]) is float or type(i[local_key]) is int:
#                            list_tags.append(local_key + "|numeric_up")
#                        else:
#                            list_tags.append(local_key + "|text_up")
#            # add a tag to allow the template filter to get these elements
#            a.item.add_tag("slidertag", uniquetag)
#            all_items.append(a.item)
#        self.serverobj.put_objects(all_items)
#        # Create the slider and put it under the named report
#        all_reports = self.serverobj.get_objects(
#            objtype=core.report_objects.TemplateREST
#        )
#        if report_name not in [x.name for x in all_reports]:
#            self.logger.error("Report name invalid")
#            return
#        my_parent = [x for x in all_reports if x.name == report_name][0]
#        slider_template = self.serverobj.create_template(
#            name="Slider Template", parent=my_parent, report_type="Layout:slider"
#        )
#        my_parent.add_filter("O|i_tags|cont|" + uniquetag + ";")
#        slider_template.set_filter("A|i_tags|cont|" + uniquetag + ";")
#        slider_template.set_map_to_slider(list_tags)
#        self.serverobj.put_objects(slider_template)
#        self.serverobj.put_objects(my_parent)
