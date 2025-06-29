# Version
# ------------------------------------------------------------------------------

from ._version import __version__

VERSION = __version__
DEFAULT_ANSYS_VERSION = "261"

ansys_version = "2026R1"

# Ansys version number that this release is associated with
__ansys_version__ = DEFAULT_ANSYS_VERSION
__ansys_version_str__ = f"{2000+(int(__ansys_version__) // 10)} R{int(__ansys_version__) % 10}"

# Ease imports
# ------------------------------------------------------------------------------

from ansys.dynamicreporting.core.adr_item import Item
from ansys.dynamicreporting.core.adr_report import Report
from ansys.dynamicreporting.core.adr_service import Service
