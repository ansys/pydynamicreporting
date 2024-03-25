"""
Custom exceptions go here
"""


class NexusException(Exception):
    """
    Base exception for any custom errors in Nexus
    """


class SafeUnpickleException(NexusException):
    """
    Raised if utils.safe_unpickle fails
    """


class FileEncodingNotSupportedError(NexusException):
    """
    Raised if uploaded file is not utf-8 encoded
    """


class EmptyUploadedFileError(NexusException):
    """
    Raised if the uploaded file with text contents is empty
    """


class InvalidDateTimeException(NexusException):
    """
    Raised when user input datetime is invalid
    """