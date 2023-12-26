import django
from django.conf import settings


# todo: meant to mirror the service class as much as possible for backwards compatibility.
class ADR:
    """
    Provides for creating a standalone ADR instance for report generation without a server.

    Parameters
    ----------
    data_directory : str, optional
        Path to the directory for storing temporary information from the Docker image.
        The default is creating a new directory inside the OS
        temporary directory. This parameter must pass a directory that exists and
        is empty.
    db_directory : str, optional
        Path to the database directory for the Ansys Dynamic Reporting service.
        The default is ``None``. This parameter must pass a directory that exists and
        is empty.
    logfile : str, optional
        File to write logs to. The default is ``None``. Acceptable values are
        filenames or ``stdout`` for standard output.


    Raises
    ------
    DatabaseDirNotProvidedError
        The ``"db_directory"`` argument has not been provided when using a Docker image.
    CannotCreateDatabaseError
        Can not create the ``"db_directory"`` when using a Docker image.


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
            data_directory: str = None,
            db_directory: str = None,
            logfile: str = None,
            opts: dict = None
    ) -> None:
        self._data_directory = data_directory
        self._db_directory = db_directory
        self._logfile = logfile
        if opts is None:
            opts = {}
        settings.configure(default_settings=DEFAULT_SETTINGS, **opts)
        django.setup()

    def create_item(
        self, obj_name: Optional[str] = "default", source: Optional[str] = "ADR"
    ) -> Item:
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
