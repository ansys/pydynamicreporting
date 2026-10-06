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

"""Server (REST) backend adapter for the ADR JSON importer.

The adapter drives the existing :class:`~ansys.dynamicreporting.core.adr_item.Item`
attribute dispatch; it changes nothing in ``adr_item`` or ``report_objects``.
"""

from __future__ import annotations

from typing import Any

from .utils.json_import.mapping import (
    apply_properties,
    column_labels,
    derive_axes,
    flatten_tree,
    resolve_path,
    rows_to_array,
)
from .utils.json_import.models import ItemPayload
from .utils.json_import.tags import combine_tags

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


class ServerImportBackend:
    """Translate import payloads into REST service objects."""

    def __init__(self, service: Any) -> None:
        self._service = service
        self.logger = service.logger

    def ensure_ready(self) -> None:
        """Verify the service is connected to a server."""
        if getattr(self._service, "serverobj", None) is None:
            raise RuntimeError("The ADR service is not connected; call connect() first.")

    def save_item(self, model: ItemPayload, doc_tags: str) -> Any:
        """Create one item and push it to the server."""
        item = self._service.create_item(obj_name=model.name, source=model.source or "ADR")
        # Set before the payload: assigning the payload attribute pushes.
        item.item.sequence = model.sequence

        setattr(item, ITEM_ATTRIBUTE[model.item_type], self._content_for(model))

        if model.item_type == "table":
            self._set_table_meta(item, model)
        apply_properties(item, model.properties, self.logger)

        item.set_tags(combine_tags(doc_tags, model.tags))
        return item

    @staticmethod
    def _content_for(model: ItemPayload) -> Any:
        """Build the REST content payload for one item."""
        if model.item_type in ("text", "html"):
            return model.value
        if model.item_type == "table":
            return rows_to_array(model.rows, len(model.columns))
        if model.item_type == "tree":
            return flatten_tree(model.nodes)
        return resolve_path(model.path, model.base_dir)

    @staticmethod
    def _set_table_meta(item: Any, model: ItemPayload) -> None:
        """Apply table labels, axes, and display fields."""
        item.labels_row = column_labels(model.columns)
        xaxis, yaxis = derive_axes(model.columns, model.xaxis, model.yaxis)
        if xaxis is not None:
            item.xaxis = xaxis
        if yaxis:
            item.yaxis = yaxis
        if model.plot is not None:
            item.plot = model.plot
        if model.table_format is not None:
            item.format = model.table_format
