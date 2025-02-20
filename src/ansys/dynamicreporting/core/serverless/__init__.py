# serverless

# Import ADR directly
from .adr import ADR

# Expose ADR immediately
__all__ = ["ADR"]

# for organization and to avoid repeating the same class names in multiple places
_item_classes = [
    "Session",
    "Dataset",
    "Item",
    "String",
    "HTML",
    "Table",
    "Tree",
    "Image",
    "Animation",
    "Scene",
    "File",
]
_template_classes = [
    "Template",
    "BasicLayout",
    "PanelLayout",
    "BoxLayout",
    "TabLayout",
    "CarouselLayout",
    "SliderLayout",
    "FooterLayout",
    "HeaderLayout",
    "IteratorLayout",
    "TagPropertyLayout",
    "TOCLayout",
    "ReportLinkLayout",
    "PPTXLayout",
    "PPTXSlideLayout",
    "DataFilterLayout",
    "UserDefinedLayout",
    "TableMergeGenerator",
    "TableReduceGenerator",
    "TableMergeRCFilterGenerator",
    "TableMergeValueFilterGenerator",
    "TableSortFilterGenerator",
    "TreeMergeGenerator",
    "SQLQueryGenerator",
    "ItemsComparisonGenerator",
    "StatisticalGenerator",
    "IteratorGenerator",
]

# Dynamically import classes from item and template using importlib
import importlib

item_module = importlib.import_module(".item", package=__package__)
template_module = importlib.import_module(".template", package=__package__)

# Dynamically add these to the module namespace and __all__
for cls_name in _item_classes + _template_classes:
    cls = getattr(item_module, cls_name, None) or getattr(template_module, cls_name, None)
    if cls:
        globals()[cls_name] = cls
        __all__.append(cls_name)
