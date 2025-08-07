"""
template_editor.exceptions
--------------------------
This module define all exceptions used in the code base for the template editor.
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


class BadRequestError(APIException):
    """Raised if there is something wrong with client's request."""


class TemplateEditorJSONLoadingError(RuntimeError):
    """Raised for errors when loading a JSON file for the template editor"""


class TemplateDoesNotExist(RuntimeError):
    """Raised when the template is not found"""


class TemplateReorderOutOfBounds(RuntimeError):
    """Raised when a template is reordered to be out of the size of the children"""


def raise_bad_request_error(response):
    """
    Generates bad request error message and raises an exception.
    """
    error_messages = []
    for key, messages in response.json().items():
        error_messages.append(messages[0].replace("this field", key))
    message = " ".join(error_messages)
    raise BadRequestError(message)
