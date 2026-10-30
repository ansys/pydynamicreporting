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

"""Public-API tests for ``ADR.import_items_from_json``.

The delegation tests use a bare ``ADR`` instance and never touch a database;
the end-to-end test is gated behind ``ado_test``.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from ansys.dynamicreporting.core.serverless import ADR
from ansys.dynamicreporting.core.utils.json_item_import import ImportResult

IMPORT_PACKAGE = "ansys.dynamicreporting.core.utils.json_item_import"


def _write_document(tmp_path: Path, **overrides) -> Path:
    payload = {"schema_version": "1.0", "app_id": "demo-app"}
    payload.update(overrides)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _adr() -> ADR:
    # object.__new__ bypasses the singleton so these mocks never leak into
    # the shared instance the end-to-end tests use.
    adr = object.__new__(ADR)
    adr._logger = MagicMock()
    return adr


@pytest.mark.unit
def test_import_from_json_delegates_to_the_shared_importer(tmp_path: Path):
    adr = _adr()
    path = _write_document(tmp_path)
    expected = ImportResult(schema_version="1.0", app_id="demo-app")

    with (
        patch.object(ADR, "ensure_setup"),
        patch(f"{IMPORT_PACKAGE}.import_items", return_value=expected) as import_items,
    ):
        result = adr.import_items_from_json(path)

    assert result is expected
    document, populate_item = import_items.call_args.args
    assert document.app_id == "demo-app"
    # Mirrors load_templates: the backend hands its own model builder to the
    # shared helper, the way it hands _create_template_with_parent to
    # populate_template.
    assert populate_item == adr._populate_item
    assert import_items.call_args.kwargs == {"on_error": "collect", "logger": adr._logger}


@pytest.mark.unit
def test_import_from_json_forwards_every_option(tmp_path: Path):
    adr = _adr()
    path = _write_document(tmp_path)

    with (
        patch.object(ADR, "ensure_setup"),
        patch(f"{IMPORT_PACKAGE}.load_document") as load_document,
        patch(f"{IMPORT_PACKAGE}.import_items") as import_items,
    ):
        adr.import_items_from_json(path, on_error="raise", base_dir="/media")

    load_document.assert_called_once_with(path, base_dir="/media", logger=adr._logger)
    assert import_items.call_args.kwargs["on_error"] == "raise"


@pytest.mark.unit
def test_importing_the_package_does_not_load_the_import_machinery():
    # The entry points annotate ImportResult under TYPE_CHECKING and import the
    # shared importer inside the method, so users who never import JSON pay nothing.
    code = (
        "import sys; "
        "import ansys.dynamicreporting.core; "
        "import ansys.dynamicreporting.core.serverless; "
        "print([n for n in sys.modules if 'json_item_import' in n])"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert completed.stdout.strip() == "[]"


@pytest.mark.ado_test
def test_import_from_json_end_to_end(adr_serverless: ADR, tmp_path: Path):
    from ansys.dynamicreporting.core.serverless import HTML, Item, String, Table

    image_path = Path(__file__).parents[1] / "test_data" / "aa_00_0_alpha1.png"
    document = {
        "schema_version": "1.0",
        "app_id": "json-import-e2e",
        "tags": [{"suite": "jsonimport"}],
        "items": [
            {
                "item_type": "text",
                "name": "e2e text",
                "tags": [{"section": "intro"}],
                "value": "Import complete.",
            },
            {
                "item_type": "html",
                "name": "e2e html",
                "value": "<p>All good.</p>",
            },
            {
                "item_type": "table",
                "name": "e2e table",
                "columns": ["time", "T_max", "T_min"],
                "rows": [[0.0, 300.1, 290.0], [1.0, 320.5, 295.2]],
                "plot": "line",
            },
            {
                "item_type": "tree",
                "name": "e2e tree",
                "nodes": [{"name": "Assembly", "children": [{"name": "Part A"}]}],
            },
            {
                "item_type": "image",
                "name": "e2e image",
                "path": str(image_path),
            },
        ],
    }
    path = tmp_path / "e2e.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    result = adr_serverless.import_items_from_json(path)

    assert result.ok, result.failures
    assert result.app_id == "json-import-e2e"
    assert result.items_saved == 5

    # Items landed on the right classes.
    assert isinstance(String.get(name="e2e text"), String)
    assert isinstance(HTML.get(name="e2e html"), HTML)

    # The table is stored series-per-row with matching labels.
    table = Table.get(name="e2e table")
    assert table.content.shape == (3, 2)
    assert table.labels_row == ["time", "T_max", "T_min"]
    assert table.xaxis == "time"
    assert table.yaxis == ["T_max", "T_min"]
    assert table.plot == "line"

    # Document and item tags were merged.
    text_item = Item.get(name="e2e text")
    assert "suite=jsonimport" in text_item.tags
    assert "section=intro" in text_item.tags
