# Version
# ------------------------------------------------------------------------------
from pathlib import Path

try:
    import importlib.metadata as importlib_metadata  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import importlib_metadata  # type: ignore
__version__ = importlib_metadata.version(__name__.replace(".", "-"))


def get_examples_download_dir():
    """Return the path to the examples download directory."""
    parent_path = Path.home() / "Downloads"
    parent_path.mkdir(exist_ok=True)
    return parent_path / "adr_examples"

    VERSION = __version__


DEFAULT_ANSYS_VERSION = "252"
EXAMPLES_PATH = str(get_examples_download_dir())

ansys_version = "2025R2"

# Ansys version number that this release is associated with
__ansys_version__ = DEFAULT_ANSYS_VERSION
__ansys_version_str__ = f"{2000+(int(__ansys_version__) // 10)} R{int(__ansys_version__) % 10}"

# Ease imports
# ------------------------------------------------------------------------------

from ansys.dynamicreporting.core.adr_item import Item
from ansys.dynamicreporting.core.adr_report import Report
from ansys.dynamicreporting.core.adr_service import Service
