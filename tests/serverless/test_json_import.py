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

"""Public-API tests for ``ADR.import_from_json``.

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
from ansys.dynamicreporting.core.utils.json_import import ImportResult


def _write_document(tmp_path: Path, **overrides) -> Path:
    payload = {"schema_version": "1.0", "app_id": "demo-app"}
    payload.update(overrides)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.unit
def test_import_from_json_delegates_to_the_importer(tmp_path: Path):
    adr = ADR.__new__(ADR)
    adr._logger = MagicMock()
    path = _write_document(tmp_path)
    expected = ImportResult(schema_version="1.0", app_id="demo-app")

    with patch(
        "ansys.dynamicreporting.core.utils.json_import.importer.JSONImporter"
    ) as importer_cls:
        importer_cls.return_value.import_file.return_value = expected
        result = adr.import_from_json(path)

    assert result is expected
    importer_cls.return_value.import_file.assert_called_once_with(
        path, on_error="collect", base_dir=None, strict_keys=False
    )


@pytest.mark.unit
def test_import_from_json_forwards_every_option(tmp_path: Path):
    adr = ADR.__new__(ADR)
    adr._logger = MagicMock()
    path = _write_document(tmp_path)

    with patch(
        "ansys.dynamicreporting.core.utils.json_import.importer.JSONImporter"
    ) as importer_cls:
        adr.import_from_json(path, on_error="raise", base_dir="/media", strict_keys=True)

    importer_cls.return_value.import_file.assert_called_once_with(
        path, on_error="raise", base_dir="/media", strict_keys=True
    )


@pytest.mark.unit
def test_importing_the_package_does_not_load_the_import_machinery():
    # The entry point imports its adapter lazily, so a user who never calls
    # import_from_json does not pay for the import layer.
    code = (
        "import sys; import ansys.dynamicreporting.core as adr; "
        "import ansys.dynamicreporting.core.serverless as sls; "
        "print(any('json_import' in name for name in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert completed.stdout.strip() == "False"


@pytest.mark.ado_test
def test_import_from_json_end_to_end(adr_serverless: ADR, tmp_path: Path):
    from ansys.dynamicreporting.core.serverless import HTML, Item, String, Table, Template

    image_path = Path(__file__).parents[1] / "test_data" / "aa_00_0_alpha1.png"
    document = {
        "schema_version": "1.0",
        "app_id": "json-import-e2e",
        "tags": [{"suite": "jsonimport"}],
        "templates": [
            {
                "template_type": "basic",
                "name": "e2e root",
                "html": '<h1 class="title">E2E</h1>',
                "children": [
                    {
                        "template_type": "panel",
                        "name": "e2e panel",
                        "children": [{"template_type": "box", "name": "e2e box"}],
                    }
                ],
            }
        ],
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
                "properties": [{"table_title": "Probe temperatures"}],
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

    result = adr_serverless.import_from_json(path)

    assert result.ok, result.failures
    assert result.app_id == "json-import-e2e"
    assert result.items_saved == 5
    # Every node of the tree, not just the root.
    assert result.templates_created == 3
    assert len(result.root_guids) == 1

    # Structure landed to full depth.
    root = Template.get(name="e2e root")
    assert root.get_params()["HTML"] == '<h1 class="title">E2E</h1>'
    panel = Template.get(name="e2e panel")
    assert panel.parent.guid == root.guid
    assert Template.get(name="e2e box").parent.guid == panel.guid

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
