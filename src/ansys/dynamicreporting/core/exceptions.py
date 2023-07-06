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

    detail = "The ANSYS installation version has not been provided"
