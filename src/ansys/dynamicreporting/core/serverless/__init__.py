# serverless

# Import ADR directly (does not depend on setup)
from .adr import ADR

# Expose ADR immediately
__all__ = ["ADR"]


# Lazy import mechanism for dependent classes
class _LazyLoader:
    """
    Lazy loader for dependent classes to defer imports until accessed.
    This allows ADR.setup() to be called before triggering the imports.
    """

    def __init__(self):
        self._initialized = False

    def _initialize(self):
        """Perform the actual imports when accessed for the first time."""
        # Ensure ADR has been set up
        ADR.ensure_setup()

        # Define the modules to be imported
        item_classes = (
            "Item",
            "HTML",
            "Animation",
            "Dataset",
            "File",
            "Image",
            "Scene",
            "Session",
            "String",
            "Table",
            "Tree",
        )
        template_classes = (
            "Template",
            "BasicLayout",
            "BoxLayout",
            "CarouselLayout",
            "DataFilterLayout",
            "FooterLayout",
            "HeaderLayout",
            "ItemsComparisonGenerator",
            "IteratorGenerator",
            "IteratorLayout",
            "PanelLayout",
            "PPTXLayout",
            "PPTXSlideLayout",
            "ReportLinkLayout",
            "SliderLayout",
            "SQLQueryGenerator",
            "StatisticalGenerator",
            "TabLayout",
            "TableMergeGenerator",
            "TableMergeRCFilterGenerator",
            "TableMergeValueFilterGenerator",
            "TableReduceGenerator",
            "TableSortFilterGenerator",
            "TagPropertyLayout",
            "TOCLayout",
            "TreeMergeGenerator",
            "UserDefinedLayout",
        )

        # Dynamically import classes from item and template using importlib
        import importlib

        item_module = importlib.import_module(".item", package=__package__)
        template_module = importlib.import_module(".template", package=__package__)

        # Dynamically add these to the module namespace and __all__
        for cls_name in item_classes + template_classes:
            cls = getattr(item_module, cls_name, None) or getattr(template_module, cls_name, None)
            if cls:
                globals()[cls_name] = cls
                __all__.append(cls_name)

        self._initialized = True

    def __getattr__(self, name):
        if not self._initialized:
            self._initialize()
        return globals()[name]


# Create a lazy loader instance
_lazy_loader = _LazyLoader()


# Define a custom module-level __getattr__ to defer imports
def __getattr__(name):
    return getattr(_lazy_loader, name)
