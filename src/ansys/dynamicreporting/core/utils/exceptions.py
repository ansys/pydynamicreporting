"""
template_editor.exceptions
--------------------------
This module definse all exceptions used in the code base for the template editor.
"""


class DBDirNotCreatedError(RuntimeError):
    """Raised when the database directory could not be created."""


class DBNotFoundError(FileNotFoundError):
    """Raised when the database file is not found."""


class DBVersionInvalidError(RuntimeError):
    """Raised when the database version is invalid."""


class DBExistsError(FileExistsError):
    """Raised when the database file already exists."""


class DBCreationFailedError(RuntimeError):
    """Raised when database creation fails."""


class ServerPortUnavailableError(RuntimeError):
    """Raised when no unused port to run the server is found."""


class ServerPortInUseError(RuntimeError):
    """Raised when port is already in use."""


class ServerLaunchError(RuntimeError):
    """Raised when server launch fails."""


class ServerConnectionError(ConnectionError):
    """Raised if unable to connect to server."""


class APIException(Exception):
    """Super class for REST API errors."""


class PermissionDenied(APIException):
    """Raised if user does not have permissions for a server request."""
