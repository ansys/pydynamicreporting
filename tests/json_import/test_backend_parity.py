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

"""Cross-backend parity.

The same document is driven through both adapters and the outcomes are
compared. This is the gate that keeps the two adapters from drifting; it
catches divergence that neither adapter's own unit tests can see.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy
import pytest

from ansys.dynamicreporting.core.import_backend_server import (
    ITEM_ATTRIBUTE,
    ServerImportBackend,
)
from ansys.dynamicreporting.core.serverless.import_backend import (
    ITEM_CLASS,
    TEMPLATE_CLASS,
    ServerlessImportBackend,
)
from ansys.dynamicreporting.core.utils.json_import.enums import (
    ITEM_TYPES,
    TEMPLATE_REPORT_TYPE,
    TEMPLATE_TYPES,
)
from ansys.dynamicreporting.core.utils.json_import.importer import JSONImporter
from ansys.dynamicreporting.core.utils.json_import.parser import build_document

DOCUMENT = {
    "schema_version": "1.0",
    "app_id": "parity-app",
    "tags": [{"report": "parity"}],
    "templates": [
        {
            "template_type": "basic",
            "name": "root",
            "html": "<h1>Parity</h1>",
            "children": [
                {
                    "template_type": "panel",
                    "name": "mid",
                    "children": [{"template_type": "box", "name": "leaf"}],
                }
            ],
        }
    ],
    "items": [
        {"item_type": "text", "name": "txt", "tags": [{"section": "intro"}], "value": "body"},
        {"item_type": "html", "name": "htm", "value": "<p>body</p>"},
        {
            "item_type": "table",
            "name": "tbl",
            "columns": ["time", "T_max", "T_min"],
            "rows": [[0.0, 300.1, 290.0], [1.0, 320.5, 295.2]],
            "plot": "line",
        },
        {
            "item_type": "tree",
            "name": "mesh",
            "nodes": [{"name": "Assembly", "children": [{"name": "Part A"}]}],
        },
        {"item_type": "image", "name": "img", "path": "plot.png"},
    ],
}


@dataclass
class Run:
    """Everything one adapter produced for the shared document."""

    result: Any
    items: dict[str, Any] = field(default_factory=dict)
    item_order: list[str] = field(default_factory=list)
    template_order: list[str] = field(default_factory=list)

    def content(self, name: str) -> Any:
        """Return the payload the adapter assigned to item ``name``."""
        return self.items[name].imported_content

    def tags(self, name: str) -> str:
        """Return the tag string the adapter assigned to item ``name``."""
        return self.items[name].imported_tags


def _run_serverless(base_dir: str) -> Run:
    adr = MagicMock()
    adr._logger = MagicMock()
    items: dict[str, Any] = {}
    item_order: list[str] = []
    template_order: list[str] = []

    def create_item(item_class, **kwargs):
        item = MagicMock()
        item.imported_content = kwargs["content"]
        item.imported_tags = kwargs["tags"]
        item.imported_class = item_class
        items[kwargs["name"]] = item
        item_order.append(kwargs["name"])
        return item

    def create_template(template_class, **kwargs):
        template_order.append(kwargs["name"])
        return MagicMock()

    adr.create_item.side_effect = create_item
    adr.create_template.side_effect = create_template

    document = build_document(DOCUMENT, base_dir=base_dir)
    result = JSONImporter(ServerlessImportBackend(adr)).import_document(document)
    return Run(result, items, item_order, template_order)


def _run_server(base_dir: str) -> Run:
    service = MagicMock()
    service.logger = MagicMock()
    items: dict[str, Any] = {}
    item_order: list[str] = []
    template_order: list[str] = []

    def create_item(**kwargs):
        item = MagicMock()
        item.imported_tags = None
        item.set_tags.side_effect = lambda value: setattr(item, "imported_tags", value)
        items[kwargs["obj_name"]] = item
        item_order.append(kwargs["obj_name"])
        return item

    def create_template(**kwargs):
        template_order.append(kwargs["name"])
        return MagicMock()

    service.create_item.side_effect = create_item
    service.serverobj.create_template.side_effect = create_template

    document = build_document(DOCUMENT, base_dir=base_dir)
    result = JSONImporter(ServerImportBackend(service)).import_document(document)

    # The server adapter assigns the payload to a type-specific attribute.
    for model in document.items:
        item = items[model.name]
        item.imported_content = getattr(item, ITEM_ATTRIBUTE[model.item_type])
    return Run(result, items, item_order, template_order)


@pytest.fixture
def serverless_run(tmp_path: Path) -> Run:
    return _run_serverless(str(tmp_path))


@pytest.fixture
def server_run(tmp_path: Path) -> Run:
    return _run_server(str(tmp_path))


# --------------------------------------------------------------------------
# Static map parity
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_both_adapters_cover_every_item_type():
    assert set(ITEM_CLASS) == set(ITEM_ATTRIBUTE) == set(ITEM_TYPES)


@pytest.mark.unit
def test_both_adapters_cover_every_template_type():
    assert set(TEMPLATE_CLASS) == set(TEMPLATE_REPORT_TYPE) == set(TEMPLATE_TYPES)


@pytest.mark.unit
@pytest.mark.parametrize("template_type", sorted(TEMPLATE_TYPES))
def test_template_class_report_type_matches_the_wire_map(template_type):
    assert TEMPLATE_CLASS[template_type].report_type == TEMPLATE_REPORT_TYPE[template_type]


# --------------------------------------------------------------------------
# Run-level parity
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_both_backends_report_the_same_result(serverless_run: Run, server_run: Run):
    assert serverless_run.result.templates_created == server_run.result.templates_created == 3
    assert serverless_run.result.items_saved == server_run.result.items_saved == 5
    assert serverless_run.result.app_id == server_run.result.app_id
    assert serverless_run.result.schema_version == server_run.result.schema_version
    assert serverless_run.result.ok and server_run.result.ok


@pytest.mark.unit
def test_both_backends_build_the_same_template_tree(serverless_run: Run, server_run: Run):
    assert serverless_run.template_order == server_run.template_order == ["root", "mid", "leaf"]


@pytest.mark.unit
def test_both_backends_create_the_same_items_in_order(serverless_run: Run, server_run: Run):
    expected = ["txt", "htm", "tbl", "mesh", "img"]
    assert serverless_run.item_order == server_run.item_order == expected


@pytest.mark.unit
def test_both_backends_produce_the_same_table_array(serverless_run: Run, server_run: Run):
    serverless_array = serverless_run.content("tbl")
    server_array = server_run.content("tbl")
    assert serverless_array.shape == server_array.shape == (3, 2)
    assert numpy.array_equal(serverless_array, server_array)


@pytest.mark.unit
def test_both_backends_label_the_table_identically(serverless_run: Run, server_run: Run):
    serverless_item = serverless_run.items["tbl"]
    server_item = server_run.items["tbl"]
    assert serverless_item.labels_row == server_item.labels_row == ["time", "T_max", "T_min"]
    assert serverless_item.xaxis == server_item.xaxis == "time"
    assert serverless_item.yaxis == server_item.yaxis == ["T_max", "T_min"]
    assert serverless_item.plot == server_item.plot == "line"


@pytest.mark.unit
def test_both_backends_produce_the_same_flattened_tree(serverless_run: Run, server_run: Run):
    serverless_tree = serverless_run.content("mesh")
    server_tree = server_run.content("mesh")
    assert serverless_tree == server_tree
    # Children must survive in both; a non-recursive flatten in one adapter
    # would silently drop them.
    assert server_tree[0]["children"][0]["name"] == "Part A"


@pytest.mark.unit
def test_both_backends_merge_tags_identically(serverless_run: Run, server_run: Run):
    assert serverless_run.tags("txt") == server_run.tags("txt") == "report=parity section=intro"


@pytest.mark.unit
def test_both_backends_resolve_media_paths_identically(
    serverless_run: Run, server_run: Run, tmp_path: Path
):
    expected = str(tmp_path / "plot.png")
    assert serverless_run.content("img") == server_run.content("img") == expected


@pytest.mark.unit
def test_both_backends_carry_the_same_inline_values(serverless_run: Run, server_run: Run):
    assert serverless_run.content("txt") == server_run.content("txt") == "body"
    assert serverless_run.content("htm") == server_run.content("htm") == "<p>body</p>"
