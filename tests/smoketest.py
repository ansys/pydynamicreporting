# version
# ADR service core
from ansys.dynamicreporting.core import Item, Report, Service, __version__

# ADR serverless core
from ansys.dynamicreporting.core.serverless import ADR
from ansys.dynamicreporting.core.serverless.item import HTML, Animation, Dataset, File, Image
from ansys.dynamicreporting.core.serverless.item import Item as ServerlessItem
from ansys.dynamicreporting.core.serverless.item import Scene, Session, String, Table, Tree
from ansys.dynamicreporting.core.serverless.template import (
    BasicLayout,
    BoxLayout,
    CarouselLayout,
    DataFilterLayout,
    FooterLayout,
    HeaderLayout,
    ItemsComparisonGenerator,
    IteratorGenerator,
    IteratorLayout,
    PanelLayout,
    PPTXLayout,
    PPTXSlideLayout,
    ReportLinkLayout,
    SliderLayout,
    SQLQueryGenerator,
    StatisticalGenerator,
    TabLayout,
    TableMergeGenerator,
    TableMergeRCFilterGenerator,
    TableMergeValueFilterGenerator,
    TableReduceGenerator,
    TableSortFilterGenerator,
    TagPropertyLayout,
    Template,
    TOCLayout,
    TreeMergeGenerator,
    UserDefinedLayout,
)

print(__version__)
