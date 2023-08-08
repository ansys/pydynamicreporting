"""DynamicReporting custom exceptions."""


class PyadrException(Exception):
    """
    Provides base exceptions.

    All other exceptions inherit from this base class.
    """

    detail: str = "An error occurred."

    def __init__(self, extra_detail: str = None) -> None:
        super().__init__()
        self.extra_detail = extra_detail

    def __str__(self) -> str:
        if self.extra_detail:
            return f"{self.detail} : {self.extra_detail}"
        return self.detail


class DatabaseDirNotProvidedError(PyadrException):
    """Exception raised when the database directory is not provided."""

    detail = "db_directory must be provided when using Docker"


class CannotCreateDatabaseError(PyadrException):
    """Exception raised when unable to create database directory."""

    detail = "The database directory could not be created"


class InvalidAnsysPath(PyadrException):
    """Exception raised if ANSYS installation path is invalid."""

    detail = "Invalid ANSYS installation path"


class AnsysVersionAbsentError(PyadrException):
    """Exception raised when ANSYS version is absent."""

    detail = "The ANSYS installation version has not been provided."


class MissingSession(PyadrException):
    """Exception raised when the ADR session absent."""

    detail = "There is no session attached to this ADR instance."


class NotValidServer(PyadrException):
    """Exception raised if the ADR server can not be validated."""

    detail = "Can not validate dynamic reporting server."


class AlreadyConnectedError(PyadrException):
    """Exception raised if the ADR service is already connected to a service."""

    detail = "Already connected to a service."


class StartingServiceError(PyadrException):
    """Exception raised if the ADR service can not be started."""

    detail = "Error starting the ADR service."


class ConnectionToServiceError(PyadrException):
    """Exception raised if can not connect to ADR service."""

    detail = "Can not connect to ADR service."


class MissingReportError(PyadrException):
    """Exception raised if there is no report."""

    detail = "Can not find the corresponding report."
