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

"""Server (REST) backend adapter for the ADR JSON item importer.

The adapter drives the existing :class:`~ansys.dynamicreporting.core.adr_item.Item`
attribute dispatch; it changes nothing in ``adr_item`` or ``report_objects``.
"""

from __future__ import annotations

from typing import Any

from .utils.json_item_import.mapping import (
    apply_properties,
    column_labels,
    derive_axes,
    flatten_tree,
    resolve_path,
    rows_to_array,
)
from .utils.json_item_import.tags import combine_tags

ITEM_ATTRIBUTE: dict[str, str] = {
    "text": "item_text",
    "html": "item_text",
    "table": "item_table",
    "tree": "item_tree",
    "image": "item_image",
    "animation": "item_animation",
    "scene": "item_scene",
    "file": "item_file",
}
"""Wire ``item_type`` to the ``adr_item.Item`` attribute that triggers the push.

``text`` and ``html`` share ``item_text``: the REST payload for that attribute
is always pushed via ``set_payload_html``.
"""


def _stage(item: Any, name: str, value: Any) -> None:
    """Set an attribute without triggering a server round trip.

    ``only_set`` is the same flag ``adr_item.Item.__copyattrs__`` uses to
    populate an item without writing back.
    """
    item.__setattr__(name, value, only_set=True)


class ServerImportBackend:
    """Translate import payloads into REST service objects."""

    def __init__(self, service: Any) -> None:
        self._service = service
        self.logger = service.logger

    def ensure_ready(self) -> None:
        """Verify the service is connected to a server."""
        if getattr(self._service, "serverobj", None) is None:
            raise RuntimeError("The ADR service is not connected; call connect() first.")

    def save_item(self, item_data: dict[str, Any], doc_tags: str) -> Any:
        """Create one item and push it to the server."""
        item = self._service.create_item(obj_name=item_data["name"], source=item_data["source"])
        # adr_item.Item has no 'sequence' passthrough, and its set_tags() pushes
        # on its own. Both are staged on the server object so they ride the
        # payload push instead of costing a round trip each.
        item.item.sequence = item_data["sequence"]
        item.item.set_tags(combine_tags(doc_tags, item_data["tags"]))

        # Assigning the payload sets the item type and performs the first push.
        # Item.__setattr__ re-uploads the whole table on every table_attr write
        # once the array is present, so everything after this point is staged
        # with only_set and pushed once at the end.
        setattr(item, ITEM_ATTRIBUTE[item_data["item_type"]], self._content_for(item_data))

        staged = False
        if item_data["item_type"] == "table":
            self._set_table_meta(item, item_data)
            staged = True
        if apply_properties(item, item_data["properties"], self.logger, setter=_stage):
            staged = True
        if staged:
            item.__pushonly__()

        return item

    @staticmethod
    def _content_for(item_data: dict[str, Any]) -> Any:
        """Build the REST content payload for one item."""
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
        """Stage table labels, axes, and display fields without pushing."""
        columns = item_data["columns"]
        _stage(item, "labels_row", column_labels(columns))
        xaxis, yaxis = derive_axes(columns, item_data["xaxis"], item_data["yaxis"])
        if xaxis is not None:
            _stage(item, "xaxis", xaxis)
        if yaxis:
            _stage(item, "yaxis", yaxis)
        if item_data["plot"] is not None:
            _stage(item, "plot", item_data["plot"])
        if item_data["format"] is not None:
            _stage(item, "format", item_data["format"])
