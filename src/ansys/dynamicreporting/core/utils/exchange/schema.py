"""Pydantic models for the ADR exchange JSON contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import ExchangeValidationError, ExchangeVersionError
from .tags import normalize_tags
from .version import SCHEMA_VERSION, check_version, parse_version


class TagObject(BaseModel):
    """A single tag object represented as a string-to-scalar mapping."""

    model_config = ConfigDict(extra="allow")

    @classmethod
    def _coerce(cls, value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            return {"value": value}
        return None


TagList: TypeAlias = list[dict[str, Any]]


def _coerce_tags(raw: Any) -> TagList:
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[dict[str, Any]] = []
        for entry in raw:
            if isinstance(entry, dict):
                out.append(entry)
            elif entry is not None:
                out.append({"value": str(entry)})
        return out
    if isinstance(raw, dict):
        return [raw]
    return [{"value": str(raw)}]


class ItemModel(BaseModel):
    """Common fields shared by every exchange item."""

    model_config = ConfigDict(extra="allow")

    item_type: str
    name: str
    tags: Annotated[TagList, Field(default_factory=list)] = Field(default_factory=list)
    source: str = ""
    sequence: int = 0
    properties: list[dict[str, Any]] = Field(default_factory=list)


class TableColumn(BaseModel):
    """A single table column definition."""

    name: str
    type: str = "string"


class TableContent(BaseModel):
    """Table content expressed as columns and rows."""

    model_config = ConfigDict(extra="allow")

    columns: list[TableColumn | str] = Field(default_factory=list)
    rows: list[list[Any]]


class TextItem(ItemModel):
    """Text payload item."""

    item_type: Literal["text"] = "text"
    value: str


class HTMLItem(ItemModel):
    """HTML payload item."""

    item_type: Literal["html"] = "html"
    value: str


class TableItem(ItemModel):
    """Table payload item."""

    item_type: Literal["table"] = "table"
    columns: list[TableColumn | str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    data: TableContent | None = None
    plot: str | None = None
    format: str | None = None
    xaxis: str | None = None
    yaxis: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_table_shape(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "data" in value:
            return value
        if "columns" in value and "rows" in value:
            normalized = dict(value)
            normalized["data"] = {"columns": value["columns"], "rows": value["rows"]}
            return normalized
        return value

    @model_validator(mode="after")
    def _sync_data_fields(self) -> "TableItem":
        if self.data is None:
            self.data = TableContent(columns=self.columns, rows=self.rows)
        if not self.columns and self.data.columns:
            self.columns = self.data.columns
        if not self.rows and self.data.rows:
            self.rows = self.data.rows
        return self


class TreeNode(BaseModel):
    """Recursive tree node model."""

    model_config = ConfigDict(extra="allow")

    name: str
    key: str | None = None
    value: Any = None
    children: list["TreeNode"] = Field(default_factory=list)


class TreeItem(ItemModel):
    """Tree payload item."""

    item_type: Literal["tree"] = "tree"
    nodes: list[TreeNode] = Field(default_factory=list)


class ImageItem(ItemModel):
    """Image payload item."""

    item_type: Literal["image"] = "image"
    path: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_path_alias(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "src" in value and "path" not in value:
            value = dict(value)
            value["path"] = value["src"]
        return value


class AnimationItem(ItemModel):
    """Animation payload item."""

    item_type: Literal["animation"] = "animation"
    path: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_path_alias(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "src" in value and "path" not in value:
            value = dict(value)
            value["path"] = value["src"]
        return value


class SceneItem(ItemModel):
    """Scene payload item."""

    item_type: Literal["scene"] = "scene"
    path: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_path_alias(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "src" in value and "path" not in value:
            value = dict(value)
            value["path"] = value["src"]
        return value


class FileItem(ItemModel):
    """File payload item."""

    item_type: Literal["file"] = "file"
    path: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_path_alias(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "src" in value and "path" not in value:
            value = dict(value)
            value["path"] = value["src"]
        return value


class TemplateModel(BaseModel):
    """A single report template node."""

    model_config = ConfigDict(extra="allow")

    template_type: str
    name: str
    tags: Annotated[TagList, Field(default_factory=list)] = Field(default_factory=list)
    item_filter: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    html: str | None = None
    column_count: int | None = None
    column_widths: list[float] | None = None
    sort_selection: str | None = None
    sort_fields: list[str] | None = None
    filter_mode: str | None = None
    children: list["TemplateModel"] = Field(default_factory=list)


class SessionModel(BaseModel):
    """Session description."""

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    tags: Annotated[TagList, Field(default_factory=list)] = Field(default_factory=list)
    application: str | None = None
    hostname: str | None = None


class DatasetModel(BaseModel):
    """Dataset description."""

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    tags: Annotated[TagList, Field(default_factory=list)] = Field(default_factory=list)
    filename: str | None = None
    format: str | None = None


ItemModelType: TypeAlias = Annotated[
    TextItem | HTMLItem | TableItem | TreeItem | ImageItem | AnimationItem | SceneItem | FileItem,
    Field(discriminator="item_type"),
]


class ExchangeDocument(BaseModel):
    """Top-level ADR exchange payload."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = SCHEMA_VERSION
    app_id: str
    tags: Annotated[TagList, Field(default_factory=list)] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    sessions: list[SessionModel] = Field(default_factory=list)
    datasets: list[DatasetModel] = Field(default_factory=list)
    items: list[ItemModelType] = Field(default_factory=list)
    templates: list[TemplateModel] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_document(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if "schema_version" not in normalized:
            normalized["schema_version"] = SCHEMA_VERSION
        if "tags" in normalized:
            normalized["tags"] = _coerce_tags(normalized["tags"])
        if "items" in normalized:
            normalized["items"] = [_normalize_item(item) for item in normalized["items"]]
        if "templates" in normalized:
            normalized["templates"] = list(normalized["templates"])
        return normalized

    @model_validator(mode="after")
    def _validate_version(self) -> "ExchangeDocument":
        try:
            check_version(self.schema_version)
        except ExchangeVersionError:
            raise
        return self

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ExchangeDocument":
        """Load and validate an exchange document from a JSON file."""
        with Path(path).open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return cls.model_validate(raw)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the document to a Python dictionary."""
        return self.model_dump(mode="python")

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize the document to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_json_file(self, path: str | Path, *, indent: int = 2) -> Path:
        """Write the document to a JSON file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json(indent=indent), encoding="utf-8")
        return target


def _normalize_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    normalized = dict(item)
    if "tags" in normalized:
        normalized["tags"] = _coerce_tags(normalized["tags"])
    if "item_type" in normalized and normalized["item_type"] == "image":
        if "src" in normalized and "path" not in normalized:
            normalized["path"] = normalized["src"]
    elif "item_type" in normalized and normalized["item_type"] in {"file", "scene", "animation"}:
        if "src" in normalized and "path" not in normalized:
            normalized["path"] = normalized["src"]
    if "properties" in normalized and normalized["properties"] is None:
        normalized["properties"] = []
    return normalized


TreeNode.model_rebuild()
