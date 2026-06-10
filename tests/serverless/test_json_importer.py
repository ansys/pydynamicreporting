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

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from ansys.dynamicreporting.core.serverless.json_importer import ServerlessReportItemImporter
from ansys.dynamicreporting.core.utils.json_importer_models import (
    FileItemModel,
    ImageItemModel,
    SceneItemModel,
    TableItemModel,
    TextItemModel,
    TreeItemModel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_importer(adr=None):
    """Return an importer backed by a fresh MagicMock ADR if none is provided."""
    if adr is None:
        adr = MagicMock()
    return ServerlessReportItemImporter(adr)


def _mock_adr_item():
    """Return a MagicMock that quacks like an ADR item (has .save())."""
    item = MagicMock()
    item.save = MagicMock()
    return item


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_raises_value_error_when_adr_is_none():
    with pytest.raises(ValueError, match="ADR instance must be provided"):
        ServerlessReportItemImporter(None)


def test_init_stores_adr_instance():
    adr = MagicMock()
    importer = ServerlessReportItemImporter(adr)
    assert importer._adr is adr


def test_init_sets_empty_template_tags():
    importer = _make_importer()
    assert importer.template_tags == ""


# ---------------------------------------------------------------------------
# _normalize_tags
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_tags, expected",
    [
        (None, ""),
        ("already a string", "already a string"),
        ({"key": "val"}, "key=val"),
        ({"key": None}, ""),  # None values are skipped
        ([{"a": "1"}, {"b": "2"}], "a=1 b=2"),
        (["foo", "bar"], "foo bar"),
        (["foo", None, "bar"], "foo bar"),  # None list entries are skipped
        ([{"k": "v"}, "plain"], "k=v plain"),  # mixed dict and string entries
        ([], ""),
    ],
)
def test_normalize_tags(raw_tags, expected):
    importer = _make_importer()
    assert importer._normalize_tags(raw_tags) == expected


def test_normalize_tags_dict_with_multiple_keys():
    importer = _make_importer()
    # Dict with two keys: both should appear in the output (order may vary in older Python,
    # but dicts preserve insertion order since 3.7)
    result = importer._normalize_tags({"section": "A", "report": "B"})
    assert "section=A" in result
    assert "report=B" in result


# ---------------------------------------------------------------------------
# _build_tags
# ---------------------------------------------------------------------------


def test_build_tags_combines_template_and_item_tags():
    importer = _make_importer()
    importer.template_tags = "tmpl=1"
    result = importer._build_tags([{"item": "2"}])
    assert result == "tmpl=1 item=2"


def test_build_tags_returns_only_item_tags_when_template_empty():
    importer = _make_importer()
    importer.template_tags = ""
    result = importer._build_tags([{"item": "2"}])
    assert result == "item=2"


def test_build_tags_returns_only_template_tags_when_item_tags_empty():
    importer = _make_importer()
    importer.template_tags = "tmpl=1"
    result = importer._build_tags(None)
    assert result == "tmpl=1"


def test_build_tags_returns_empty_string_when_both_empty():
    importer = _make_importer()
    importer.template_tags = ""
    result = importer._build_tags(None)
    assert result == ""


# ---------------------------------------------------------------------------
# _create_default_template
# ---------------------------------------------------------------------------


def test_create_default_template_calls_adr_and_saves():
    adr = MagicMock()
    mock_template = MagicMock()
    adr.create_template.return_value = mock_template
    importer = ServerlessReportItemImporter(adr)
    importer.template_tags = "report=x"

    importer._create_default_template("my_app")

    adr.create_template.assert_called_once()
    assert mock_template.params == '{"HTML": "<h1>my_app</h1>"}'
    mock_template.save.assert_called_once()


# ---------------------------------------------------------------------------
# _create_and_save_item
# ---------------------------------------------------------------------------


def test_create_and_save_item_calls_save_by_default():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    result = importer._create_and_save_item(MagicMock(), name="n", content="c", tags=[])

    mock_item.save.assert_called_once()
    assert result is mock_item


def test_create_and_save_item_skips_save_when_flag_is_false():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    importer._create_and_save_item(MagicMock(), name="n", content="c", tags=[], save=False)

    mock_item.save.assert_not_called()


def test_create_and_save_item_passes_normalized_tags_to_adr():
    adr = MagicMock()
    adr.create_item.return_value = _mock_adr_item()
    importer = _make_importer(adr)
    importer.template_tags = "t=1"

    importer._create_and_save_item(MagicMock(), name="n", content="c", tags=[{"i": "2"}])

    _, kwargs = adr.create_item.call_args
    assert kwargs["tags"] == "t=1 i=2"


# ---------------------------------------------------------------------------
# _save_item dispatch
# ---------------------------------------------------------------------------


def test_save_item_routes_text_item():
    importer = _make_importer()
    item = TextItemModel(name="T", tags=[], value="hello")
    with patch.object(importer, "_save_text_item", return_value=MagicMock()) as mock:
        importer._save_item(item)
    mock.assert_called_once_with(item)


def test_save_item_routes_table_item():
    importer = _make_importer()
    item = TableItemModel(name="T", tags=[], data={"columns": ["X"], "rows": [[1.0]]})
    with patch.object(importer, "_save_table_item", return_value=MagicMock()) as mock:
        importer._save_item(item)
    mock.assert_called_once_with(item)


def test_save_item_routes_image_item():
    importer = _make_importer()
    item = ImageItemModel(name="I", tags=[], src="/img.png")
    with patch.object(importer, "_save_image_item", return_value=MagicMock()) as mock:
        importer._save_item(item)
    mock.assert_called_once_with(item)


def test_save_item_routes_file_item():
    importer = _make_importer()
    item = FileItemModel(name="F", tags=[], src="/data.csv")
    with patch.object(importer, "_save_file_item", return_value=MagicMock()) as mock:
        importer._save_item(item)
    mock.assert_called_once_with(item)


def test_save_item_routes_scene_item():
    importer = _make_importer()
    item = SceneItemModel(name="S", tags=[], src="/scene.avz")
    with patch.object(importer, "_save_scene_item", return_value=MagicMock()) as mock:
        importer._save_item(item)
    mock.assert_called_once_with(item)


def test_save_item_routes_tree_item():
    importer = _make_importer()
    item = TreeItemModel(name="Tr", tags=[], data={"nodes": [{"name": "Root"}]})
    with patch.object(importer, "_save_tree_item", return_value=MagicMock()) as mock:
        importer._save_item(item)
    mock.assert_called_once_with(item)


def test_save_item_logs_warning_and_returns_none_for_unsupported_type():
    importer = _make_importer()
    unsupported = SimpleNamespace()  # not any of the known model types

    with patch.object(importer._logger, "warning") as mock_warn:
        result = importer._save_item(unsupported)

    assert result is None
    mock_warn.assert_called_once()
    assert "Unsupported" in mock_warn.call_args.args[0]


# ---------------------------------------------------------------------------
# _save_text_item
# ---------------------------------------------------------------------------


def test_save_text_item_creates_string_item_with_correct_args():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TextItemModel(name="Msg", tags=[], value="hello world")
    result = importer._save_text_item(item)

    _, kwargs = adr.create_item.call_args
    assert kwargs["name"] == "Msg"
    assert kwargs["content"] == "hello world"
    mock_item.save.assert_called_once()
    assert result is mock_item


# ---------------------------------------------------------------------------
# _save_table_item
# ---------------------------------------------------------------------------


def test_save_table_item_converts_rows_to_numpy_array():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TableItemModel(
        name="T", tags=[], data={"columns": ["X", "Y"], "rows": [[1.0, 2.0], [3.0, 4.0]]}
    )
    importer._save_table_item(item)

    _, kwargs = adr.create_item.call_args
    assert isinstance(kwargs["content"], np.ndarray)
    np.testing.assert_array_equal(kwargs["content"], [[1.0, 2.0], [3.0, 4.0]])


def test_save_table_item_sets_labels_from_string_columns():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TableItemModel(name="T", tags=[], data={"columns": ["X", "Y", "Z"], "rows": [[1, 2, 3]]})
    importer._save_table_item(item)

    assert mock_item.labels_row == ["X", "Y", "Z"]
    assert mock_item.xaxis == "X"
    assert mock_item.yaxis == ["Y", "Z"]


def test_save_table_item_sets_labels_from_object_columns():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TableItemModel(
        name="T",
        tags=[],
        data={
            "columns": [{"name": "Time", "type": "float"}, {"name": "Pressure", "type": "float"}],
            "rows": [[0.0, 101325.0]],
        },
    )
    importer._save_table_item(item)

    assert mock_item.labels_row == ["Time", "Pressure"]
    assert mock_item.xaxis == "Time"
    assert mock_item.yaxis == ["Pressure"]


def test_save_table_item_with_single_column_sets_only_xaxis():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TableItemModel(name="T", tags=[], data={"columns": ["X"], "rows": [[1.0]]})
    importer._save_table_item(item)

    assert mock_item.labels_row == ["X"]
    assert mock_item.xaxis == "X"
    # yaxis is only set when there are 2+ columns; with a single column it is never
    # assigned, so accessing the attribute returns a raw MagicMock, not a list.
    assert not isinstance(mock_item.yaxis, list)


def test_save_table_item_calls_save_at_end():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TableItemModel(name="T", tags=[], data={"columns": ["X"], "rows": [[1.0]]})
    importer._save_table_item(item)

    mock_item.save.assert_called_once()


def test_save_table_item_falls_back_to_bytes_dtype_for_string_columns():
    """Tables with non-numeric cells must be stored as a byte-string array, not skipped."""
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TableItemModel(
        name="T",
        tags=[],
        data={
            "columns": ["Label", "Value"],
            "rows": [["alpha", "1.0"], ["beta", "2.0"]],
        },
    )
    importer._save_table_item(item)

    _, kwargs = adr.create_item.call_args
    result = kwargs["content"]
    assert isinstance(result, np.ndarray)
    # TableContent accepts dtype kind "S" (byte strings) for non-numeric data
    assert result.dtype.kind == "S"
    assert result.shape == (2, 2)


# ---------------------------------------------------------------------------
# _save_image_item / _save_file_item / _save_scene_item
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_cls, src_field, importer_method",
    [
        (ImageItemModel, "/img.png", "_save_image_item"),
        (FileItemModel, "/data.csv", "_save_file_item"),
        (SceneItemModel, "/model.avz", "_save_scene_item"),
    ],
)
def test_save_src_based_item_passes_src_as_content(model_cls, src_field, importer_method):
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = model_cls(name="Item", tags=[], src=src_field)
    result = getattr(importer, importer_method)(item)

    _, kwargs = adr.create_item.call_args
    assert kwargs["name"] == "Item"
    assert kwargs["content"] == src_field
    mock_item.save.assert_called_once()
    assert result is mock_item


# ---------------------------------------------------------------------------
# _flatten_tree_node
# ---------------------------------------------------------------------------


def test_flatten_tree_node_leaf_has_correct_structure():
    importer = _make_importer()
    node = SimpleNamespace(name="Root", children=[])

    result = importer._flatten_tree_node(node, "pk", 0)

    assert result["key"] == "pk_root"
    assert result["value"] == "Root"
    assert result["name"] == "Root"
    assert result["level"] == 0
    assert result["children"] == []


def test_flatten_tree_node_normalizes_spaces_in_key():
    importer = _make_importer()
    node = SimpleNamespace(name="My Node", children=[])

    result = importer._flatten_tree_node(node, "parent key", 1)

    assert " " not in result["key"]
    assert result["key"] == "parent_key_my_node"


def test_flatten_tree_node_key_is_lowercased():
    importer = _make_importer()
    node = SimpleNamespace(name="UPPER", children=[])

    result = importer._flatten_tree_node(node, "PREFIX", 0)

    assert result["key"] == "prefix_upper"


def test_flatten_tree_node_increments_level_for_children():
    importer = _make_importer()
    grandchild = SimpleNamespace(name="GC", children=[])
    child = SimpleNamespace(name="Child", children=[grandchild])
    root = SimpleNamespace(name="Root", children=[child])

    result = importer._flatten_tree_node(root, "pk", 0)

    assert result["level"] == 0
    child_result = result["children"][0]
    assert child_result["level"] == 1
    grandchild_result = child_result["children"][0]
    assert grandchild_result["level"] == 2


def test_flatten_tree_node_preserves_multiple_children():
    importer = _make_importer()
    children = [SimpleNamespace(name=f"C{i}", children=[]) for i in range(3)]
    root = SimpleNamespace(name="Root", children=children)

    result = importer._flatten_tree_node(root, "pk", 0)

    assert len(result["children"]) == 3
    assert result["children"][0]["value"] == "C0"
    assert result["children"][2]["value"] == "C2"


# ---------------------------------------------------------------------------
# _save_tree_item
# ---------------------------------------------------------------------------


def test_save_tree_item_flattens_nodes_and_saves():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TreeItemModel(
        name="Tree",
        tags=[],
        data={"nodes": [{"name": "Root", "children": [{"name": "Leaf"}]}]},
    )
    result = importer._save_tree_item(item)

    _, kwargs = adr.create_item.call_args
    assert kwargs["name"] == "Tree"
    tree_content = kwargs["content"]
    assert isinstance(tree_content, list)
    assert len(tree_content) == 1  # one root node
    assert tree_content[0]["value"] == "Root"
    assert len(tree_content[0]["children"]) == 1
    assert tree_content[0]["children"][0]["value"] == "Leaf"
    mock_item.save.assert_called_once()
    assert result is mock_item


# ---------------------------------------------------------------------------
# _save_items
# ---------------------------------------------------------------------------


def test_save_items_calls_save_item_for_each():
    importer = _make_importer()
    items_data = MagicMock()
    items_data.items = [
        TextItemModel(name="A", tags=[], value="v1"),
        TextItemModel(name="B", tags=[], value="v2"),
    ]
    with patch.object(importer, "_save_item") as mock_save:
        importer._save_items(items_data)
    assert mock_save.call_count == 2


def test_save_items_continues_and_logs_on_item_failure():
    importer = _make_importer()
    good = TextItemModel(name="Good", tags=[], value="ok")
    bad = TextItemModel(name="Bad", tags=[], value="fail")

    def _side_effect(item):
        if item.name == "Bad":
            raise RuntimeError("boom")

    items_data = MagicMock()
    items_data.items = [good, bad, good]

    with patch.object(importer, "_save_item", side_effect=_side_effect):
        with patch.object(importer._logger, "exception") as mock_exc:
            # should not raise
            importer._save_items(items_data)

    mock_exc.assert_called_once()


# ---------------------------------------------------------------------------
# _import_json_items — end-to-end with mocked ADR
# ---------------------------------------------------------------------------


def test_import_json_items_happy_path(tmp_path):
    payload = {
        "app_id": "test-app",
        "tags": [{"report": "json_import"}],
        "items": [
            {"item_type": "text", "name": "Summary", "tags": [], "value": "All good."},
            {
                "item_type": "table",
                "name": "Results",
                "tags": [],
                "columns": ["X", "Y"],
                "rows": [[1.0, 2.0], [3.0, 4.0]],
            },
        ],
    }
    json_file = tmp_path / "report.json"
    json_file.write_text(json.dumps(payload), encoding="utf-8")

    adr = MagicMock()
    mock_template = MagicMock()
    mock_adr_item = _mock_adr_item()
    adr.create_template.return_value = mock_template
    adr.create_item.return_value = mock_adr_item

    importer = _make_importer(adr)
    result = importer._import_json_items(json_file)

    # Returns the parsed model
    assert result.app_id == "test-app"
    assert len(result.items) == 2

    # Template was created once
    adr.create_template.assert_called_once()
    mock_template.save.assert_called_once()
    assert mock_template.params == '{"HTML": "<h1>test-app</h1>"}'

    # Template tags were derived from top-level tags
    assert importer.template_tags == "report=json_import"

    # Both items were saved (text calls save once; table calls save once)
    assert adr.create_item.call_count == 2


def test_import_json_items_sets_template_tags_from_payload(tmp_path):
    payload = {
        "app_id": "app",
        "tags": [{"env": "prod", "version": "2"}],
        "items": [],
    }
    json_file = tmp_path / "r.json"
    json_file.write_text(json.dumps(payload), encoding="utf-8")

    adr = MagicMock()
    adr.create_template.return_value = MagicMock()
    importer = _make_importer(adr)
    importer._import_json_items(json_file)

    assert "env=prod" in importer.template_tags
    assert "version=2" in importer.template_tags


# ---------------------------------------------------------------------------
# _flatten_properties
# ---------------------------------------------------------------------------


def test_flatten_properties_returns_empty_dict_for_none():
    importer = _make_importer()
    assert importer._flatten_properties(None) == {}


def test_flatten_properties_returns_empty_dict_for_empty_list():
    importer = _make_importer()
    assert importer._flatten_properties([]) == {}


def test_flatten_properties_merges_list_of_single_key_dicts():
    importer = _make_importer()
    result = importer._flatten_properties([{"format": "floatdot0"}, {"ytitle": "Values"}])
    assert result == {"format": "floatdot0", "ytitle": "Values"}


def test_flatten_properties_merges_multi_key_dict_entries():
    importer = _make_importer()
    result = importer._flatten_properties([{"xaxis": "X", "yaxis": ["Y1", "Y2"]}])
    assert result == {"xaxis": "X", "yaxis": ["Y1", "Y2"]}


def test_flatten_properties_later_entries_overwrite_earlier_ones():
    importer = _make_importer()
    result = importer._flatten_properties([{"plot": "bar"}, {"plot": "line"}])
    assert result["plot"] == "line"


def test_flatten_properties_skips_non_dict_entries():
    importer = _make_importer()
    # Non-dict entries in the list should not raise and should be ignored
    result = importer._flatten_properties([{"format": "floatdot0"}, "unexpected_string"])
    assert result == {"format": "floatdot0"}


# ---------------------------------------------------------------------------
# _apply_properties
# ---------------------------------------------------------------------------


def test_apply_properties_sets_attributes_on_item():
    importer = _make_importer()
    mock_item = MagicMock()
    mock_item.name = "MyItem"

    importer._apply_properties(mock_item, [{"plot": "line"}, {"xtitle": "Time (s)"}])

    assert mock_item.plot == "line"
    assert mock_item.xtitle == "Time (s)"


def test_apply_properties_does_nothing_for_none():
    importer = _make_importer()
    mock_item = MagicMock()

    importer._apply_properties(mock_item, None)

    # No setattr calls beyond mock setup
    mock_item.assert_not_called()


def test_apply_properties_does_nothing_for_empty_list():
    importer = _make_importer()
    mock_item = MagicMock()

    importer._apply_properties(mock_item, [])

    mock_item.assert_not_called()


def test_apply_properties_sets_source_and_sequence():
    importer = _make_importer()
    mock_item = MagicMock()
    mock_item.name = "I"

    importer._apply_properties(mock_item, [{"source": "Simulation 1"}, {"sequence": 3}])

    assert mock_item.source == "Simulation 1"
    assert mock_item.sequence == 3


# ---------------------------------------------------------------------------
# _create_and_save_item — properties path
# ---------------------------------------------------------------------------


def test_create_and_save_item_applies_properties_before_save():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    importer._create_and_save_item(
        MagicMock(),
        name="n",
        content="c",
        tags=[],
        properties=[{"plot": "bar"}, {"xtitle": "Time"}],
    )

    # Properties should be set before save() is called
    assert mock_item.plot == "bar"
    assert mock_item.xtitle == "Time"
    mock_item.save.assert_called_once()


def test_create_and_save_item_with_no_properties_does_not_raise():
    adr = MagicMock()
    adr.create_item.return_value = _mock_adr_item()
    importer = _make_importer(adr)

    # Should not raise when properties is None (the default)
    importer._create_and_save_item(MagicMock(), name="n", content="c", tags=[])


# ---------------------------------------------------------------------------
# _save_table_item — properties applied (plot, xtitle, ytitle, etc.)
# ---------------------------------------------------------------------------


def test_save_table_item_applies_properties_from_model():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TableItemModel(
        name="T",
        tags=[],
        properties=[{"plot": "line"}, {"xtitle": "X Axis"}, {"ytitle": "Y Axis"}],
        data={"columns": ["X", "Y"], "rows": [[1.0, 2.0]]},
    )
    importer._save_table_item(item)

    assert mock_item.plot == "line"
    assert mock_item.xtitle == "X Axis"
    assert mock_item.ytitle == "Y Axis"
    mock_item.save.assert_called_once()


def test_save_text_item_applies_properties_from_model():
    adr = MagicMock()
    mock_item = _mock_adr_item()
    adr.create_item.return_value = mock_item
    importer = _make_importer(adr)

    item = TextItemModel(
        name="T",
        tags=[],
        properties=[{"source": "Pipeline A"}, {"sequence": 5}],
        value="hello",
    )
    importer._save_text_item(item)

    assert mock_item.source == "Pipeline A"
    assert mock_item.sequence == 5
