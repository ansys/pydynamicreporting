# Version
# ------------------------------------------------------------------------------

try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:  # pragma: no cover
    import importlib_metadata  # type: ignore

__version__ = importlib_metadata.version("ansys-dynamicreporting-core")

ansys_version = "2024R1"

# Ease imports
# ------------------------------------------------------------------------------


from ansys.dynamicreporting.core.adr_item import Item
from ansys.dynamicreporting.core.adr_report import Report
from ansys.dynamicreporting.core.adr_service import Service
# serverless
from ansys.dynamicreporting.core.internals.adr import ADR
from ansys.dynamicreporting.core.internals.item import (
    Session,
    Dataset,
    Item,
    String,
    Text,
    HTML,
    Table,
    Plot,
    Tree,
    Image,
    Animation,
    Movie,
    Scene,
    File
)
from ansys.dynamicreporting.core.internals.template import (
    Template,
    BasicLayout,
    PanelLayout
)
