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

"""Tests for the REST item import on ``report_remote_server.Server``."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from unittest.mock import MagicMock

from PIL import Image as PILImage
import pytest

from ansys.dynamicreporting.core.exceptions import (
    ADRItemImportError,
    ImportItemValidationError,
)
from ansys.dynamicreporting.core.utils.json_item_import.spec import (
    ITEM_TYPE_TO_ADR_TYPE,
    ITEM_TYPES,
)
from ansys.dynamicreporting.core.utils.report_objects import ItemREST
from ansys.dynamicreporting.core.utils.report_remote_server import Server
from tests.json_import.helpers import build_item as _item

PNG = Path(__file__).parents[1] / "test_data" / "aa_00_0_alpha1.png"


def _media(tmp_path: Path) -> dict[str, dict[str, str]]:
    """Write one valid payload file per media type and return their item fields."""
    shutil.copy(PNG, tmp_path / "a.png")
    for name in ("a.mp4", "a.avz", "a.txt"):
        (tmp_path / name).write_bytes(b"payload")
    return {
        "image": {"path": "a.png"},
        "animation": {"path": "a.mp4"},
        "scene": {"path": "a.avz"},
        "file": {"path": "a.txt"},
    }


_INLINE = {
    "text": {"value": "body"},
    "html": {"value": "<p>body</p>"},
    "table": {"columns": ["a", "b"], "rows": [[1, 2]]},
    "tree": {"nodes": [{"name": "root"}]},
}


# --------------------------------------------------------------------------
# Payload dispatch onto the existing ItemREST model
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_payload_setter_map_covers_every_item_type():
    assert set(Server._IMPORT_PAYLOAD_SETTERS) == set(ITEM_TYPES)
    for setter in Server._IMPORT_PAYLOAD_SETTERS.values():
        assert callable(getattr(ItemREST, setter))


@pytest.mark.unit
@pytest.mark.parametrize("item_type", sorted(ITEM_TYPES))
def test_every_item_type_builds_an_itemrest_of_the_mapped_type(
    item_type, rest_server, tmp_path: Path
):
    payloads = {**_INLINE, **_media(tmp_path)}
    model = _item({"item_type": item_type, "name": "n", **payloads[item_type]}, str(tmp_path))

    item = rest_server._populate_item(model, "")

    assert isinstance(item, ItemREST)
    assert item.type == ITEM_TYPE_TO_ADR_TYPE[item_type]
    rest_server.put_objects.assert_called_once_with([item])


@pytest.mark.unit
def test_name_source_and_sequence_are_stored_verbatim(rest_server):
    model = _item({"item_type": "text", "name": "n", "value": "v", "source": "", "sequence": 4})
    item = rest_server._populate_item(model, "")
    assert item.name == "n"
    assert item.source == ""
    assert item.sequence == 4


@pytest.mark.unit
def test_document_and_item_tags_are_merged(rest_server):
    model = _item({"item_type": "text", "name": "n", "value": "v", "tags": [{"a": "1"}]})
    item = rest_server._populate_item(model, "doc=1")
    assert item.get_tags() == "doc=1 a=1"


@pytest.mark.unit
def test_non_png_images_are_converted_before_the_payload(rest_server, tmp_path: Path):
    PILImage.new("RGB", (4, 3)).save(tmp_path / "plot.jpg")
    model = _item({"item_type": "image", "name": "n", "path": "plot.jpg"}, str(tmp_path))
    item = rest_server._populate_item(model, "")
    assert item.type == "image"
    assert (item.width, item.height) == (4, 3)


@pytest.mark.unit
def test_a_missing_media_file_fails_the_item(rest_server, tmp_path: Path):
    model = _item({"item_type": "file", "name": "n", "path": "missing.txt"}, str(tmp_path))
    with pytest.raises(FileNotFoundError):
        rest_server._populate_item(model, "")
    rest_server.put_objects.assert_not_called()


@pytest.mark.unit
def test_a_rejected_push_fails_the_item(rest_server):
    rest_server.put_objects.return_value = 500
    rest_server._last_error = "boom"
    with pytest.raises(ADRItemImportError) as excinfo:
        rest_server._populate_item(_item({"item_type": "text", "name": "n", "value": "v"}), "")
    assert "HTTP 500" in str(excinfo.value)
    assert "boom" in str(excinfo.value)


@pytest.mark.unit
def test_a_rejected_push_removes_the_partial_item(rest_server):
    rest_server.put_objects.return_value = 500
    with pytest.raises(ADRItemImportError):
        rest_server._populate_item(_item({"item_type": "text", "name": "n", "value": "v"}), "")
    pushed = rest_server.put_objects.call_args.args[0]
    rest_server.del_objects.assert_called_once_with(pushed)


@pytest.mark.unit
def test_a_successful_push_deletes_nothing(rest_server):
    rest_server._populate_item(_item({"item_type": "text", "name": "n", "value": "v"}), "")
    rest_server.del_objects.assert_not_called()


@pytest.mark.unit
def test_a_failed_cleanup_does_not_mask_the_push_error(rest_server):
    logger = MagicMock()
    rest_server.put_objects.return_value = 500
    rest_server._last_error = "boom"
    rest_server.del_objects.side_effect = RuntimeError("network down")
    with pytest.raises(ADRItemImportError) as excinfo:
        rest_server._populate_item(
            _item({"item_type": "text", "name": "n", "value": "v"}), "", logger=logger
        )
    assert "boom" in str(excinfo.value)
    assert any("network down" in str(c) for c in logger.warning.call_args_list)


@pytest.mark.unit
@pytest.mark.parametrize(("status", "warned"), [(404, False), (500, True)])
def test_cleanup_status_is_reported_only_when_the_item_may_remain(rest_server, status, warned):
    logger = MagicMock()
    rest_server.put_objects.return_value = 500
    rest_server.del_objects.return_value = status
    with pytest.raises(ADRItemImportError):
        rest_server._populate_item(
            _item({"item_type": "text", "name": "n", "value": "v"}), "", logger=logger
        )
    assert logger.warning.called is warned


# --------------------------------------------------------------------------
# Tables and trees
# --------------------------------------------------------------------------


def _table_model(**overrides):
    raw = {
        "item_type": "table",
        "name": "t",
        "columns": ["time", "T_max", "T_min"],
        "rows": [[0.0, 300.1, 290.0], [1.0, 320.5, 295.2]],
    }
    raw.update(overrides)
    return _item(raw)


@pytest.mark.unit
def test_table_payload_carries_the_array_and_display_fields(rest_server):
    item = rest_server._populate_item(_table_model(plot="line", format="floatdot1"), "")
    payload = item.payloaddata
    assert payload["array"].shape == (3, 2)
    assert payload["labels_row"] == ["time", "T_max", "T_min"]
    assert payload["xaxis"] == "time"
    assert payload["yaxis"] == ["T_max", "T_min"]
    assert payload["plot"] == "line"
    assert payload["format"] == "floatdot1"


@pytest.mark.unit
def test_tree_children_are_not_dropped(rest_server):
    model = _item(
        {
            "item_type": "tree",
            "name": "t",
            "nodes": [{"name": "root", "children": [{"name": "child"}]}],
        }
    )
    item = rest_server._populate_item(model, "")
    assert item.payloaddata[0]["children"][0]["name"] == "child"


# --------------------------------------------------------------------------
# Server.import_items_from_json
# --------------------------------------------------------------------------


def _write(tmp_path: Path, **overrides) -> Path:
    payload = {"schema_version": "1.0", "app_id": "demo-app", **overrides}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.unit
def test_import_resolves_media_against_the_document_directory(rest_server, tmp_path: Path):
    shutil.copy(PNG, tmp_path / "plot.png")
    path = _write(tmp_path, items=[{"item_type": "image", "name": "i", "path": "plot.png"}])

    result = rest_server.import_items_from_json(path)

    assert result.ok, result.failures
    assert result.items_saved == 1


@pytest.mark.unit
def test_import_collects_per_item_failures(rest_server, tmp_path: Path):
    path = _write(
        tmp_path,
        items=[
            {"item_type": "text", "name": "good", "value": "v"},
            {"item_type": "file", "name": "bad", "path": "missing.txt"},
        ],
    )
    result = rest_server.import_items_from_json(path)
    assert result.items_saved == 1
    assert [failure.name for failure in result.failures] == ["bad"]


@pytest.mark.unit
def test_import_forwards_on_error(rest_server, tmp_path: Path):
    path = _write(tmp_path, items=[{"item_type": "file", "name": "bad", "path": "missing.txt"}])
    with pytest.raises(FileNotFoundError):
        rest_server.import_items_from_json(path, on_error="raise")


# --------------------------------------------------------------------------
# Dict documents
# --------------------------------------------------------------------------


def _document(**overrides) -> dict:
    return {"schema_version": "1.0", "app_id": "demo-app", **overrides}


@pytest.mark.unit
def test_import_accepts_a_decoded_document(rest_server, tmp_path: Path):
    shutil.copy(PNG, tmp_path / "plot.png")
    document = _document(
        items=[
            {"item_type": "text", "name": "t", "value": "v"},
            {"item_type": "image", "name": "i", "path": "plot.png"},
        ]
    )

    result = rest_server.import_items_from_json(document, base_dir=tmp_path)

    assert result.ok, result.failures
    assert result.items_saved == 2


@pytest.mark.unit
def test_a_dict_resolves_relative_media_against_the_working_directory(
    rest_server, tmp_path: Path, monkeypatch
):
    shutil.copy(PNG, tmp_path / "plot.png")
    monkeypatch.chdir(tmp_path)
    document = _document(items=[{"item_type": "image", "name": "i", "path": "plot.png"}])

    result = rest_server.import_items_from_json(document)

    assert result.ok, result.failures


@pytest.mark.unit
def test_import_validates_before_pushing(rest_server):
    with pytest.raises(ImportItemValidationError) as excinfo:
        rest_server.import_items_from_json({"schema_version": "1.0"})
    assert "app_id" in str(excinfo.value)
    rest_server.put_objects.assert_not_called()
