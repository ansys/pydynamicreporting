"""DynamicReporting custom exceptions."""


class ADRException(Exception):
    """
    Provides base exceptions.

    All other exceptions inherit from this base class.
    """

    detail: str = "An error occurred"

    def __init__(self, extra_detail: str = None) -> None:
        super().__init__()
        self.extra_detail = extra_detail

    def __str__(self) -> str:
        if self.extra_detail:
            return f"{self.detail} : {self.extra_detail}"
        return self.detail


class DatabaseDirNotProvidedError(ADRException):
    """Exception raised when the database directory is not provided."""

    detail = "db_directory must be provided when using Docker"


class CannotCreateDatabaseError(ADRException):
    """Exception raised when unable to create database directory."""

    detail = "The database directory could not be created"


class InvalidAnsysPath(ADRException):
    """Exception raised if ANSYS installation path is invalid."""

    detail = "Invalid ANSYS installation path"


class InvalidPath(ADRException):
    """Exception raised if file/dir path is invalid."""

    detail = "Invalid path provided"


class AnsysVersionAbsentError(ADRException):
    """Exception raised when ANSYS version is absent."""

    detail = "The ANSYS installation version has not been provided."


class MissingSession(ADRException):
    """Exception raised when the ADR session absent."""

    detail = "There is no session attached to this ADR instance."


class NotValidServer(ADRException):
    """Exception raised if the ADR server can not be validated."""

    detail = "Can not validate dynamic reporting server."


class AlreadyConnectedError(ADRException):
    """Exception raised if the ADR service is already connected to a service."""

    detail = "Already connected to a service."


class StartingServiceError(ADRException):
    """Exception raised if the ADR service can not be started."""

    detail = "Error starting the ADR service."


class ConnectionToServiceError(ADRException):
    """Exception raised if can not connect to ADR service."""

    detail = "Can not connect to ADR service."


class MissingReportError(ADRException):
    """Exception raised if there is no report."""

    detail = "Can not find the corresponding report."


class TemplateDoesNotExist(ADRException):
    """Raised when the template is not found"""


class TemplateReorderOutOfBounds(ADRException):
    """Raised when a template is reordered to be out of the size of the children"""


"""Serverless exceptions."""


class ImproperlyConfiguredError(ADRException):
    """Exception raised if ADR is not properly configured."""

    detail = "Some required configuration may be missing"


class DatabaseMigrationError(ADRException):
    """Exception raised if database migrations fails."""

    detail = "The database setup failed to complete"


class GeometryMigrationError(ADRException):
    """Exception raised if database migrations fails."""

    detail = "The geometry migration failed to complete"


class StaticFilesCollectionError(ADRException):
    """Exception raised if collectstatic fails."""

    detail = "The collection of static files to the target directory failed"


class ObjectNotSavedError(ADRException):
    """Exception raised if an object is not saved."""

    detail = "The operation failed because the object needs to be saved first"


class ObjectDoesNotExistError(ADRException):
    """Exception raised if an object is not saved."""

    detail = "The object does not exist in the database"


class MultipleObjectsReturnedError(ADRException):
    """Exception raised if only one object was expected, but multiple were returned."""

    detail = "get() returned more than one object."


class IntegrityError(ADRException):
    """Exception raised if there is a constraint violation while saving an object in the database."""

    detail = "A database integrity check failed."


class InvalidFieldError(ADRException):
    """Exception raised if a field is not valid."""

    detail = "Field is invalid."
