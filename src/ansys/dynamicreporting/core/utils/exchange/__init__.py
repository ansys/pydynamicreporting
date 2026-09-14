"""Shared ADR exchange models and import orchestration."""

from .enums import ItemType, TemplateType
from .errors import ExchangeError, ExchangeValidationError, ExchangeVersionError
from .result import ImportResult, ItemFailure
from .schema import (
    AnimationItem,
    DatasetModel,
    ExchangeDocument,
    FileItem,
    HTMLItem,
    ImageItem,
    ItemModel,
    SceneItem,
    SessionModel,
    TableColumn,
    TableItem,
    TemplateModel,
    TextItem,
    TreeItem,
    TreeNode,
)
from .tags import combine_tags, normalize_tags
from .version import SCHEMA_VERSION, SUPPORTED_MAJOR, check_version, parse_version


def __getattr__(name):
    if name == "ExchangeImporter":
        from .importer import ExchangeImporter

        return ExchangeImporter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ExchangeDocument",
    "ExchangeImporter",
    "ItemType",
    "TemplateType",
    "ItemModel",
    "TextItem",
    "HTMLItem",
    "TableItem",
    "TableColumn",
    "TreeItem",
    "TreeNode",
    "ImageItem",
    "AnimationItem",
    "SceneItem",
    "FileItem",
    "TemplateModel",
    "SessionModel",
    "DatasetModel",
    "ImportResult",
    "ItemFailure",
    "ExchangeError",
    "ExchangeValidationError",
    "ExchangeVersionError",
    "normalize_tags",
    "combine_tags",
    "SCHEMA_VERSION",
    "SUPPORTED_MAJOR",
    "parse_version",
    "check_version",
]
