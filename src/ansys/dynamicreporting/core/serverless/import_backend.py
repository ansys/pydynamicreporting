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

"""Serverless backend adapter for the ADR JSON importer.

The adapter only calls the existing public creation APIs
(:meth:`ADR.create_item` and :meth:`ADR.create_template`), so the serverless
validators still run underneath every imported object.
"""

from __future__ import annotations

from typing import Any

from ..adr_utils import get_logger
from ..utils.json_import.mapping import (
    apply_properties,
    column_labels,
    derive_axes,
    flatten_tree,
    resolve_path,
    rows_to_array,
)
from ..utils.json_import.models import ItemPayload, TemplatePayload
from ..utils.json_import.tags import combine_tags
from .item import HTML, Animation, File, Image, Scene, String, Table, Tree
from .template import (
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
    TableMapGenerator,
    TableMergeGenerator,
    TableMergeRCFilterGenerator,
    TableMergeValueFilterGenerator,
    TableReduceGenerator,
    TableSortFilterGenerator,
    TagPropertyLayout,
    TOCLayout,
    TreeMergeGenerator,
    UserDefinedLayout,
)

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

TEMPLATE_CLASS: dict[str, type] = {
    "basic": BasicLayout,
    "panel": PanelLayout,
    "box": BoxLayout,
    "tabs": TabLayout,
    "carousel": CarouselLayout,
    "slider": SliderLayout,
    "header": HeaderLayout,
    "footer": FooterLayout,
    "toc": TOCLayout,
    "iterator": IteratorLayout,
    "tagproperty": TagPropertyLayout,
    "reportlink": ReportLinkLayout,
    "pptx": PPTXLayout,
    "pptx_slide": PPTXSlideLayout,
    "datafilter": DataFilterLayout,
    "userdefined": UserDefinedLayout,
    "sqlquery": SQLQueryGenerator,
    "tablemerge": TableMergeGenerator,
    "tablereduce": TableReduceGenerator,
    "tablemergercfilter": TableMergeRCFilterGenerator,
    "tablemergevaluefilter": TableMergeValueFilterGenerator,
    "tablemap": TableMapGenerator,
    "tablesortfilter": TableSortFilterGenerator,
    "treemerge": TreeMergeGenerator,
    "statistical": StatisticalGenerator,
    "itemscomparison": ItemsComparisonGenerator,
    "iterator_generator": IteratorGenerator,
}
"""Wire ``template_type`` to the serverless template class."""


class ServerlessImportBackend:
    """Translate import payloads into serverless ADR objects."""

    def __init__(self, adr: Any) -> None:
        self._adr = adr
        self.logger = getattr(adr, "_logger", None) or get_logger()

    def ensure_ready(self) -> None:
        """Verify the ADR singleton has been set up."""
        self._adr.ensure_setup()

    def create_template(self, model: TemplatePayload, parent: Any = None) -> Any:
        """Create and persist one template node."""
        template = self._adr.create_template(
            TEMPLATE_CLASS[model.template_type],
            name=model.name,
            parent=parent,
            tags=combine_tags(model.tags),
        )

        params = dict(model.params)
        if model.html is not None:
            params["HTML"] = model.html
        template.set_params(params)

        # Layout-only; the parser rejects these on generator templates.
        if model.column_count is not None:
            template.set_column_count(model.column_count)
        if model.column_widths is not None:
            template.set_column_widths(list(model.column_widths))

        if model.item_filter:
            template.set_filter(filter_str=model.item_filter)
        if model.sort_selection is not None:
            template.set_sort_selection(model.sort_selection)
        if model.sort_fields is not None:
            template.set_sort_fields(list(model.sort_fields))
        if model.filter_mode is not None:
            template.set_filter_mode(model.filter_mode)

        template.save()
        return template

    def save_item(self, model: ItemPayload, doc_tags: str) -> Any:
        """Create and persist one item."""
        item = self._adr.create_item(
            ITEM_CLASS[model.item_type],
            name=model.name,
            content=self._content_for(model),
            source=model.source,
            sequence=model.sequence,
            tags=combine_tags(doc_tags, model.tags),
        )

        needs_resave = False
        if model.item_type == "table":
            self._set_table_meta(item, model)
            needs_resave = True
        if model.properties:
            apply_properties(item, model.properties, self.logger)
            needs_resave = True

        # create_item() already persisted the item; only attributes applied
        # afterwards require a second write.
        if needs_resave:
            item.save()
        return item

    @staticmethod
    def _content_for(model: ItemPayload) -> Any:
        """Build the backend content payload for one item."""
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
