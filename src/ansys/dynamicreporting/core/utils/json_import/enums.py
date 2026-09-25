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

"""Closed wire vocabularies for the ADR import schema.

This module holds plain data only. It must not import any backend module, so
that the import core stays backend-agnostic; the drift guard asserts these
tables stay in sync with the backend registries.
"""

from __future__ import annotations

ITEM_TYPES: tuple[str, ...] = (
    "text",
    "html",
    "table",
    "tree",
    "image",
    "animation",
    "scene",
    "file",
)
"""Closed set of ``item_type`` discriminator values."""

ITEM_TYPE_TO_ADR_TYPE: dict[str, str] = {
    "text": "string",
    "html": "html",
    "table": "table",
    "tree": "tree",
    "image": "image",
    "animation": "anim",
    "scene": "scene",
    "file": "file",
}
"""Wire ``item_type`` to the canonical ``serverless.item.ItemType`` value.

The wire vocabulary is deliberately more readable than the stored one
(``text`` rather than ``string``, ``animation`` rather than ``anim``). This
table is the only place that translation is allowed to live.
"""

MEDIA_ITEM_TYPES: frozenset[str] = frozenset({"image", "animation", "scene", "file"})
"""Item types whose payload is a file path rather than an inline value."""

LAYOUT_REPORT_TYPE: dict[str, str] = {
    "basic": "Layout:basic",
    "panel": "Layout:panel",
    "box": "Layout:box",
    "tabs": "Layout:tabs",
    "carousel": "Layout:carousel",
    "slider": "Layout:slider",
    "header": "Layout:header",
    "footer": "Layout:footer",
    "toc": "Layout:toc",
    "iterator": "Layout:iterator",
    "tagproperty": "Layout:tagprops",
    "reportlink": "Layout:reportlink",
    "pptx": "Layout:pptx",
    "pptx_slide": "Layout:pptxslide",
    "datafilter": "Layout:datafilter",
    "userdefined": "Layout:userdefined",
}
"""Wire ``template_type`` to ``report_type`` for the layout family."""

GENERATOR_REPORT_TYPE: dict[str, str] = {
    "sqlquery": "Generator:sqlqueries",
    "tablemerge": "Generator:tablemerge",
    "tablereduce": "Generator:tablereduce",
    "tablemergercfilter": "Generator:tablerowcolumnfilter",
    "tablemergevaluefilter": "Generator:tablevaluefilter",
    "tablemap": "Generator:tablemap",
    "tablesortfilter": "Generator:tablesortfilter",
    "treemerge": "Generator:treemerge",
    "statistical": "Generator:statistical",
    "itemscomparison": "Generator:itemscomparison",
    # 'iterator' alone names the layout, which is by far the common case; the
    # generator of the same name is reachable under an explicit wire name.
    "iterator_generator": "Generator:iterator",
}
"""Wire ``template_type`` to ``report_type`` for the generator family."""

TEMPLATE_REPORT_TYPE: dict[str, str] = {**LAYOUT_REPORT_TYPE, **GENERATOR_REPORT_TYPE}
"""Wire ``template_type`` to ``report_type`` for every supported template."""

TEMPLATE_TYPES: tuple[str, ...] = tuple(TEMPLATE_REPORT_TYPE)
"""Closed set of ``template_type`` discriminator values."""

LAYOUT_TEMPLATE_TYPES: frozenset[str] = frozenset(LAYOUT_REPORT_TYPE)
"""Template types that accept the layout-only ``column_count``/``column_widths``."""

SORT_SELECTIONS: tuple[str, ...] = ("all", "first", "last")
"""Accepted ``sort_selection`` values."""

FILTER_MODES: tuple[str, ...] = ("items", "root_replace", "root_append")
"""Accepted ``filter_mode`` values."""
