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

"""Tests for the serverless item import on ``ADR``."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ansys.dynamicreporting.core.exceptions import ImportItemValidationError
from ansys.dynamicreporting.core.serverless import ADR
from ansys.dynamicreporting.core.serverless.item import (
    HTML,
    Animation,
    File,
    Image,
    Scene,
    String,
    Table,
    Tree,
)
from ansys.dynamicreporting.core.utils.json_item_import.spec import ITEM_TYPES
from tests.json_import.helpers import build_item as _item

ITEM_CLASS = {item_type: ADR._import_item_class(item_type) for item_type in ITEM_TYPES}


@pytest.fixture
def adr(serverless_adr):
    return serverless_adr


# --------------------------------------------------------------------------
# Class maps
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_html_binds_to_the_html_class_not_string():
    assert ITEM_CLASS["html"] is HTML
    assert ITEM_CLASS["text"] is String


@pytest.mark.unit
def test_animation_binds_to_the_animation_class_not_image():
    assert ITEM_CLASS["animation"] is Animation
    assert ITEM_CLASS["image"] is Image


@pytest.mark.unit
def test_item_class_map_is_a_bijection_onto_the_eight_classes():
    assert set(ITEM_CLASS.values()) == {String, HTML, Table, Tree, Image, Animation, Scene, File}
    assert len(set(ITEM_CLASS.values())) == len(ITEM_CLASS) == 8


@pytest.mark.unit
@pytest.mark.parametrize("item_type", sorted(ITEM_CLASS))
def test_every_item_type_dispatches_to_its_class(item_type, adr, tmp_path: Path):
    payloads = {
        "text": {"value": "body"},
        "html": {"value": "<p>body</p>"},
        "table": {"columns": ["a", "b"], "rows": [[1, 2]]},
        "tree": {"nodes": [{"name": "root"}]},
        "image": {"path": "a.png"},
        "animation": {"path": "a.mp4"},
        "scene": {"path": "a.avz"},
        "file": {"path": "a.txt"},
    }
    model = _item({"item_type": item_type, "name": "n", **payloads[item_type]}, str(tmp_path))
    adr._populate_item(model, "")

    assert adr.create_item.call_args.args[0] is ITEM_CLASS[item_type]


# --------------------------------------------------------------------------
# Items
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_text_content_is_the_inline_value(adr):
    adr._populate_item(_item({"item_type": "text", "name": "n", "value": "body"}), "")
    assert adr.create_item.call_args.kwargs["content"] == "body"


@pytest.mark.unit
def test_source_and_sequence_are_forwarded(adr):
    model = _item({"item_type": "text", "name": "n", "value": "v", "source": "mech", "sequence": 7})
    adr._populate_item(model, "")
    kwargs = adr.create_item.call_args.kwargs
    assert kwargs["source"] == "mech"
    assert kwargs["sequence"] == 7


@pytest.mark.unit
def test_document_and_item_tags_are_merged(adr):
    model = _item({"item_type": "text", "name": "n", "value": "v", "tags": [{"section": "intro"}]})
    adr._populate_item(model, "report=run42")
    assert adr.create_item.call_args.kwargs["tags"] == "report=run42 section=intro"


@pytest.mark.unit
def test_media_paths_resolve_against_the_document_directory(adr, tmp_path: Path):
    model = _item({"item_type": "image", "name": "n", "path": "plot.png"}, str(tmp_path))
    adr._populate_item(model, "")
    assert adr.create_item.call_args.kwargs["content"] == str(tmp_path / "plot.png")


@pytest.mark.unit
def test_absolute_media_paths_are_left_alone(adr, tmp_path: Path):
    absolute = str(tmp_path / "plot.png")
    model = _item({"item_type": "image", "name": "n", "path": absolute}, str(tmp_path / "other"))
    adr._populate_item(model, "")
    assert adr.create_item.call_args.kwargs["content"] == absolute


@pytest.mark.unit
def test_tree_content_is_flattened_recursively(adr):
    model = _item(
        {
            "item_type": "tree",
            "name": "t",
            "nodes": [{"name": "root", "children": [{"name": "child"}]}],
        }
    )
    adr._populate_item(model, "")
    content = adr.create_item.call_args.kwargs["content"]
    assert content[0]["name"] == "root"
    assert content[0]["children"][0]["name"] == "child"


# --------------------------------------------------------------------------
# Tables
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
def test_table_content_is_transposed_to_series_per_row(adr):
    adr._populate_item(_table_model(), "")
    array = adr.create_item.call_args.kwargs["content"]
    assert array.shape == (3, 2)


@pytest.mark.unit
def test_table_labels_row_matches_the_array_rows(adr):
    item = adr._populate_item(_table_model(), "")
    array = adr.create_item.call_args.kwargs["content"]
    assert item.labels_row == ["time", "T_max", "T_min"]
    assert len(item.labels_row) == array.shape[0]


@pytest.mark.unit
def test_table_axes_are_derived_from_the_columns(adr):
    item = adr._populate_item(_table_model(), "")
    assert item.xaxis == "time"
    assert item.yaxis == ["T_max", "T_min"]


@pytest.mark.unit
def test_table_explicit_axes_win(adr):
    item = adr._populate_item(_table_model(xaxis="T_max", yaxis=["T_min"]), "")
    assert item.xaxis == "T_max"
    assert item.yaxis == ["T_min"]


@pytest.mark.unit
def test_table_display_fields_are_applied(adr):
    item = adr._populate_item(_table_model(plot="line", format="floatdot1"), "")
    assert item.plot == "line"
    assert item.format == "floatdot1"


@pytest.mark.unit
def test_table_is_saved_once_after_its_metadata(adr):
    item = adr._populate_item(_table_model(), "")
    item.save.assert_called_once()


@pytest.mark.unit
def test_simple_item_is_not_saved_a_second_time(adr):
    item = adr._populate_item(_item({"item_type": "text", "name": "n", "value": "v"}), "")
    item.save.assert_not_called()


@pytest.mark.unit
def test_a_failed_table_save_removes_the_created_table(adr):
    # create_item() has already persisted the row; leaving it would keep a
    # table without labels or axes while the import reports a failure.
    created = []

    def create_item(item_class, **kwargs):
        item = MagicMock(name="table")
        item.save.side_effect = RuntimeError("db down")
        created.append(item)
        return item

    adr.create_item = create_item
    with pytest.raises(RuntimeError, match="db down"):
        adr._populate_item(_table_model(), "")
    created[0].delete.assert_called_once()


@pytest.mark.unit
def test_a_simple_item_is_never_deleted(adr):
    item = adr._populate_item(_item({"item_type": "text", "name": "n", "value": "v"}), "")
    item.delete.assert_not_called()


# --------------------------------------------------------------------------
# ADR.import_items_from_json
# --------------------------------------------------------------------------


def _write(tmp_path: Path, **overrides) -> Path:
    payload = {"schema_version": "1.0", "app_id": "demo-app", **overrides}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.unit
def test_import_requires_a_set_up_adr(adr, tmp_path: Path):
    with patch.object(ADR, "ensure_setup", side_effect=RuntimeError("not set up")):
        with pytest.raises(RuntimeError):
            adr.import_items_from_json(_write(tmp_path))
    adr.create_item.assert_not_called()


@pytest.mark.unit
def test_import_resolves_media_against_the_document_directory(adr, tmp_path: Path):
    path = _write(tmp_path, items=[{"item_type": "image", "name": "i", "path": "a.png"}])
    with patch.object(ADR, "ensure_setup"):
        result = adr.import_items_from_json(path)
    assert result.items_saved == 1
    assert adr.create_item.call_args.kwargs["content"] == str(tmp_path / "a.png")


@pytest.mark.unit
def test_import_forwards_base_dir(adr, tmp_path: Path):
    path = _write(tmp_path, items=[{"item_type": "image", "name": "i", "path": "a.png"}])
    with patch.object(ADR, "ensure_setup"):
        adr.import_items_from_json(path, base_dir=str(tmp_path / "media"))
    assert adr.create_item.call_args.kwargs["content"] == str(tmp_path / "media" / "a.png")


@pytest.mark.unit
def test_import_forwards_on_error(adr, tmp_path: Path):
    adr.create_item.side_effect = RuntimeError("db down")
    path = _write(tmp_path, items=[{"item_type": "text", "name": "t", "value": "v"}])
    with patch.object(ADR, "ensure_setup"):
        with pytest.raises(RuntimeError):
            adr.import_items_from_json(path, on_error="raise")


@pytest.mark.unit
def test_import_logs_through_the_adr_logger(adr, tmp_path: Path):
    adr.create_item.side_effect = RuntimeError("db down")
    path = _write(tmp_path, items=[{"item_type": "text", "name": "t", "value": "v"}])
    with patch.object(ADR, "ensure_setup"):
        adr.import_items_from_json(path)
    adr._logger.error.assert_called_once()


# --------------------------------------------------------------------------
# Dict documents
# --------------------------------------------------------------------------


def _document(**overrides) -> dict:
    return {"schema_version": "1.0", "app_id": "demo-app", **overrides}


@pytest.mark.unit
def test_import_accepts_a_decoded_document(adr, tmp_path: Path):
    document = _document(items=[{"item_type": "image", "name": "i", "path": "a.png"}])
    with patch.object(ADR, "ensure_setup"):
        result = adr.import_items_from_json(document, base_dir=tmp_path)
    assert result.items_saved == 1
    assert adr.create_item.call_args.kwargs["content"] == str(tmp_path / "a.png")


@pytest.mark.unit
def test_a_dict_leaves_relative_media_to_the_working_directory(adr):
    document = _document(items=[{"item_type": "image", "name": "i", "path": "a.png"}])
    with patch.object(ADR, "ensure_setup"):
        adr.import_items_from_json(document)
    assert adr.create_item.call_args.kwargs["content"] == "a.png"


@pytest.mark.unit
def test_import_validates_before_creating(adr):
    with patch.object(ADR, "ensure_setup"):
        with pytest.raises(ImportItemValidationError):
            adr.import_items_from_json({"schema_version": "1.0"})
    adr.create_item.assert_not_called()
