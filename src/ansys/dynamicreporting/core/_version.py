"""The version module for the pydynamicreporting package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ansys-dynamicreporting-core")
except PackageNotFoundError:  # pragma: no cover
    # Fallback for local dev or editable installs
    __version__ = "0.0.0"
