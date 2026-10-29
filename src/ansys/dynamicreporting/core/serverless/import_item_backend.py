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

"""Serverless backend adapter for the ADR JSON item importer.

The adapter only calls the existing public creation API
(:meth:`ADR.create_item`), so the serverless validators still run underneath
every imported item.
"""

from __future__ import annotations

from typing import Any

from ..adr_utils import get_logger
from ..utils.json_item_import.mapping import (
    apply_properties,
    column_labels,
    derive_axes,
    flatten_tree,
    resolve_path,
    rows_to_array,
)
from ..utils.json_item_import.tags import combine_tags
from .item import HTML, Animation, File, Image, Scene, String, Table, Tree

ITEM_CLASS: dict[str, type] = {
    "text": String,
    "html": HTML,
    "table": Table,
    "tree": Tree,
    "image": Image,
    "animation": Animation,
    "scene": Scene,
    "file": File,
}
"""Wire ``item_type`` to the serverless item class.

``html`` binds to :class:`HTML` and ``animation`` binds to :class:`Animation`.
Collapsing them onto :class:`String`/:class:`Image` would skip the markup
validation and route video files through the image save path.
"""


class ServerlessImportBackend:
    """Translate import item payloads into serverless ADR item objects."""

    def __init__(self, adr: Any) -> None:
        self._adr = adr
        self.logger = getattr(adr, "_logger", None) or get_logger()

    def ensure_ready(self) -> None:
        """Verify the ADR singleton has been set up."""
        self._adr.ensure_setup()

    def save_item(self, item_data: dict[str, Any], doc_tags: str) -> Any:
        """Create and persist one item."""
        item = self._adr.create_item(
            ITEM_CLASS[item_data["item_type"]],
            name=item_data["name"],
            content=self._content_for(item_data),
            source=item_data["source"],
            sequence=item_data["sequence"],
            tags=combine_tags(doc_tags, item_data["tags"]),
        )

        needs_resave = False
        if item_data["item_type"] == "table":
            self._set_table_meta(item, item_data)
            needs_resave = True
        if apply_properties(item, item_data["properties"], self.logger):
            needs_resave = True

        if needs_resave:
            item.save()
        return item

    @staticmethod
    def _content_for(item_data: dict[str, Any]) -> Any:
        """Build the backend content payload for one item."""
        item_type = item_data["item_type"]
        if item_type in ("text", "html"):
            return item_data["value"]
        if item_type == "table":
            return rows_to_array(item_data["rows"], len(item_data["columns"]))
        if item_type == "tree":
            return flatten_tree(item_data["nodes"])
        return resolve_path(item_data["path"], item_data["base_dir"])

    @staticmethod
    def _set_table_meta(item: Any, item_data: dict[str, Any]) -> None:
        """Apply table labels, axes, and display fields."""
        columns = item_data["columns"]
        item.labels_row = column_labels(columns)
        xaxis, yaxis = derive_axes(columns, item_data["xaxis"], item_data["yaxis"])
        if xaxis is not None:
            item.xaxis = xaxis
        if yaxis:
            item.yaxis = yaxis
        if item_data["plot"] is not None:
            item.plot = item_data["plot"]
        if item_data["format"] is not None:
            item.format = item_data["format"]
