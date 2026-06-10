# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Shared JSON report item schemas.

This module should be used for JSON report item imports in both server and
serverless versions. It is the centralized place where Pydantic is used to
validate import payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemModel(BaseModel):
    """Base JSON report item model."""

    model_config = ConfigDict(extra="allow")
    name: str
    tags: List[Dict[str, Any]]
    properties: Optional[List[Dict[str, Any]]] = None


class TableColumnModel(BaseModel):
    """Table column model."""

    name: str
    type: str


class TableContentModel(BaseModel):
    """Table content model containing columns and rows."""

    model_config = ConfigDict(extra="allow")
    columns: List[Union[TableColumnModel, str]] = Field(default_factory=list)
    rows: List[List[Any]]


class TableItemModel(ItemModel):
    """Table item model."""

    item_type: Literal["table"] = "table"
    data: TableContentModel

    @model_validator(mode="before")
    @classmethod
    def _validate_table_content_shape(cls, values: Any) -> Any:
        """Support table items where columns and rows are at item top level."""
        if not isinstance(values, dict):
            return values

        if "data" in values:
            return values

        columns = values.get("columns")
        rows = values.get("rows")

        if columns is not None and rows is not None:
            values = dict(values)
            values["data"] = {
                "columns": columns,
                "rows": rows,
            }

        return values


class TextItemModel(ItemModel):
    """Text item model."""

    item_type: Literal["text"] = "text"
    value: str


class ImageItemModel(ItemModel):
    """Image item model."""

    item_type: Literal["image"] = "image"
    src: str


class FileItemModel(ItemModel):
    """File item model."""

    item_type: Literal["file"] = "file"
    src: str


class SceneItemModel(ItemModel):
    """Scene item model."""

    item_type: Literal["scene"] = "scene"
    src: str


class TreeNodeModel(BaseModel):
    """Tree node model."""

    model_config = ConfigDict(extra="allow")
    name: str
    children: List["TreeNodeModel"] = Field(default_factory=list)


class TreeContentModel(BaseModel):
    """Tree content model."""

    model_config = ConfigDict(extra="allow")
    nodes: List[TreeNodeModel]


class TreeItemModel(ItemModel):
    """Tree item model."""

    item_type: Literal["tree"] = "tree"
    data: TreeContentModel


TreeNodeModel.model_rebuild()

ReportItemModel = Annotated[
    Union[
        TableItemModel,
        TextItemModel,
        ImageItemModel,
        FileItemModel,
        SceneItemModel,
        TreeItemModel,
    ],
    Field(discriminator="item_type"),
]


class ReportItemsModel(BaseModel):
    """Top-level JSON import payload."""

    model_config = ConfigDict(extra="allow")
    app_id: str
    tags: List[Dict[str, Any]]
    items: List[ReportItemModel]

    @classmethod
    def from_json_file(cls, file_path: str | Path) -> "ReportItemsModel":
        """Load and validate JSON report items via Pydantic."""
        with Path(file_path).open("r", encoding="utf-8") as stream:
            raw_payload = json.load(stream)
        return cls.model_validate(raw_payload)


__all__ = [
    "FileItemModel",
    "ImageItemModel",
    "SceneItemModel",
    "TableItemModel",
    "TextItemModel",
    "TreeItemModel",
    "ReportItemsModel",
]
