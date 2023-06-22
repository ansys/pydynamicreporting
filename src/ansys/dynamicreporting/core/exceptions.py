"""DynamicReporting custom exceptions."""


class PyadrException(Exception):
    """
    Base exception.

    All other exceptions inherit from here.
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
    """Exception raised when database dir is not provided."""

    detail = "db_directory must be provided when using Docker"


class CannotCreateDatabaseError(PyadrException):
    """Exception raised when unable to create database directory."""

    detail = "The database directory could not be created"


class InvalidAnsysPath(PyadrException):
    """Exception raised if ANSYS install path is invalid."""

    detail = "Invalid ANSYS installation path"


class AnsysVersionAbsentError(PyadrException):
    """Exception raised when ANSYS version is absent."""

    detail = "The ANSYS installation version has not been provided"
