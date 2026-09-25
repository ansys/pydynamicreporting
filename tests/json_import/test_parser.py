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

"""Tests for the declarative spec parser."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.utils.json_import.errors import (
    ImportValidationError,
    ImportVersionError,
)
from ansys.dynamicreporting.core.utils.json_import.models import TableColumn, TreeNode
from ansys.dynamicreporting.core.utils.json_import.parser import build_document, load_document


def _document(**overrides):
    """Build a minimal valid document, applying ``overrides``."""
    base = {"schema_version": "1.0", "app_id": "demo-app"}
    base.update(overrides)
    return base


def _locations(excinfo):
    """Return the set of problem locations from a validation error."""
    return {location for location, _ in excinfo.value.problems}


# --------------------------------------------------------------------------
# Envelope
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_minimal_document_is_valid():
    doc = build_document(_document())
    assert doc.app_id == "demo-app"
    assert doc.schema_version == "1.0"
    assert doc.items == ()
    assert doc.templates == ()


@pytest.mark.unit
def test_document_must_be_an_object():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(["not", "an", "object"])
    assert _locations(excinfo) == {"<document>"}


@pytest.mark.unit
def test_app_id_is_required():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document({"schema_version": "1.0"})
    assert "app_id" in _locations(excinfo)


@pytest.mark.unit
def test_app_id_must_be_non_empty():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(app_id=""))
    assert "app_id" in _locations(excinfo)


@pytest.mark.unit
def test_schema_version_defaults_when_absent():
    logger = MagicMock()
    doc = build_document({"app_id": "demo-app"}, logger=logger)
    assert doc.schema_version == "1.0"
    logger.warning.assert_called()


@pytest.mark.unit
def test_newer_major_is_rejected_before_field_validation():
    # The envelope fails fast even though 'items' is also malformed.
    with pytest.raises(ImportVersionError):
        build_document({"schema_version": "9.0", "items": 5})


@pytest.mark.unit
def test_empty_document_warns():
    logger = MagicMock()
    build_document(_document(), logger=logger)
    assert any("no items and no templates" in str(call) for call in logger.warning.call_args_list)


# --------------------------------------------------------------------------
# Unknown keys
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_unknown_keys_are_retained_and_warned():
    logger = MagicMock()
    doc = build_document(_document(future_field={"a": 1}), logger=logger)
    assert doc.extra == {"future_field": {"a": 1}}
    assert any("unknown key" in str(call) for call in logger.warning.call_args_list)


@pytest.mark.unit
def test_unknown_keys_are_errors_in_strict_mode():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(future_field=1), strict_keys=True)
    assert any("unknown key" in message for _, message in excinfo.value.problems)


@pytest.mark.unit
def test_unknown_item_keys_are_retained():
    doc = build_document(
        _document(items=[{"item_type": "text", "name": "n", "value": "v", "typo_key": []}])
    )
    assert doc.items[0].extra == {"typo_key": []}


# --------------------------------------------------------------------------
# Multi-error accumulation
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_every_problem_is_reported_in_one_pass():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            {
                "schema_version": "1.0",
                "items": [
                    {"item_type": "text", "name": "ok"},
                    {"item_type": "image", "name": ""},
                    {"item_type": "nope", "name": "x"},
                ],
            }
        )
    locations = _locations(excinfo)
    # app_id, items[0].value, items[1].name, items[1].path, items[2].item_type
    assert len(excinfo.value.problems) >= 5
    assert "items[0].value" in locations
    assert "items[1].name" in locations
    assert "items[1].path" in locations
    assert "items[2].item_type" in locations


@pytest.mark.unit
def test_validation_error_message_lists_every_problem():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document({"items": [{"item_type": "text", "name": "a"}]})
    text = str(excinfo.value)
    assert "problems found" in text
    assert "items[0]" in text


@pytest.mark.unit
def test_single_problem_is_rendered_in_the_singular():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document({"schema_version": "1.0"})
    assert "1 problem found" in str(excinfo.value)


# --------------------------------------------------------------------------
# Items - common fields
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_item_must_be_an_object():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=["nope"]))
    assert "items[0]" in _locations(excinfo)


@pytest.mark.unit
def test_unknown_item_type_is_rejected():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "spreadsheet", "name": "x"}]))
    assert "items[0].item_type" in _locations(excinfo)


@pytest.mark.unit
def test_item_common_defaults():
    doc = build_document(_document(items=[{"item_type": "text", "name": "n", "value": "v"}]))
    item = doc.items[0]
    assert item.tags == ()
    assert item.source == ""
    assert item.sequence == 0
    assert item.properties == ()


@pytest.mark.unit
def test_item_sequence_rejects_a_boolean():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(items=[{"item_type": "text", "name": "n", "value": "v", "sequence": True}])
        )
    assert "items[0].sequence" in _locations(excinfo)


@pytest.mark.unit
def test_item_tags_accept_objects_and_key_value_strings():
    doc = build_document(
        _document(
            items=[
                {
                    "item_type": "text",
                    "name": "n",
                    "value": "v",
                    "tags": [{"section": "intro"}, "dp=1"],
                }
            ]
        )
    )
    assert doc.items[0].tags == ({"section": "intro"}, {"dp": "1"})


@pytest.mark.unit
def test_item_tags_reject_a_bare_string_entry():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(items=[{"item_type": "text", "name": "n", "value": "v", "tags": ["oops"]}])
        )
    assert "items[0].tags" in _locations(excinfo)


@pytest.mark.unit
def test_item_tags_accept_a_single_mapping():
    doc = build_document(
        _document(
            items=[{"item_type": "text", "name": "n", "value": "v", "tags": {"section": "intro"}}]
        )
    )
    assert doc.items[0].tags == ({"section": "intro"},)


@pytest.mark.unit
def test_item_properties_must_be_objects():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(
                items=[{"item_type": "text", "name": "n", "value": "v", "properties": ["nope"]}]
            )
        )
    assert "items[0].properties[0]" in _locations(excinfo)


# --------------------------------------------------------------------------
# Items - text / html
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("item_type", ["text", "html"])
def test_inline_items_require_a_value(item_type):
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[{"item_type": item_type, "name": "n"}]))
    assert "items[0].value" in _locations(excinfo)


@pytest.mark.unit
@pytest.mark.parametrize("item_type", ["text", "html"])
def test_inline_items_carry_their_value(item_type):
    doc = build_document(_document(items=[{"item_type": item_type, "name": "n", "value": "body"}]))
    assert doc.items[0].value == "body"
    assert doc.items[0].item_type == item_type


@pytest.mark.unit
def test_value_must_be_a_string():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "text", "name": "n", "value": 5}]))
    assert "items[0].value" in _locations(excinfo)


# --------------------------------------------------------------------------
# Items - media
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("item_type", ["image", "animation", "scene", "file"])
def test_media_items_require_a_path(item_type):
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[{"item_type": item_type, "name": "n"}]))
    assert "items[0].path" in _locations(excinfo)


@pytest.mark.unit
@pytest.mark.parametrize("item_type", ["image", "animation", "scene", "file"])
def test_media_items_accept_the_legacy_src_alias(item_type):
    logger = MagicMock()
    doc = build_document(
        _document(items=[{"item_type": item_type, "name": "n", "src": "payload.bin"}]),
        logger=logger,
    )
    assert doc.items[0].path == "payload.bin"
    assert any("deprecated" in str(call) for call in logger.warning.call_args_list)


@pytest.mark.unit
def test_path_wins_when_both_path_and_src_are_present():
    logger = MagicMock()
    doc = build_document(
        _document(items=[{"item_type": "image", "name": "n", "path": "new.png", "src": "old.png"}]),
        logger=logger,
    )
    assert doc.items[0].path == "new.png"
    assert any("both" in str(call) for call in logger.warning.call_args_list)


@pytest.mark.unit
def test_src_is_not_reported_as_an_unknown_key():
    doc = build_document(_document(items=[{"item_type": "image", "name": "n", "src": "a.png"}]))
    assert doc.items[0].extra == {}


@pytest.mark.unit
def test_base_dir_is_attached_to_items():
    doc = build_document(
        _document(items=[{"item_type": "image", "name": "n", "path": "a.png"}]),
        base_dir="/runs/42",
    )
    assert doc.items[0].base_dir == "/runs/42"


# --------------------------------------------------------------------------
# Items - table
# --------------------------------------------------------------------------


def _table(**overrides):
    base = {
        "item_type": "table",
        "name": "t",
        "columns": ["time", "T_max", "T_min"],
        "rows": [[0.0, 300.1, 290.0], [1.0, 320.5, 295.2]],
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_table_columns_are_normalized():
    doc = build_document(_document(items=[_table()]))
    assert doc.items[0].columns == (
        TableColumn("time"),
        TableColumn("T_max"),
        TableColumn("T_min"),
    )


@pytest.mark.unit
def test_table_columns_accept_objects():
    doc = build_document(
        _document(items=[_table(columns=[{"name": "time", "type": "float"}, "T_max", "T_min"])])
    )
    assert doc.items[0].columns[0] == TableColumn("time", "float")


@pytest.mark.unit
def test_table_column_object_requires_a_name():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[_table(columns=[{"type": "float"}, "b", "c"])]))
    assert "items[0].columns" in _locations(excinfo)


@pytest.mark.unit
def test_table_rows_must_be_rectangular():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[_table(rows=[[1, 2, 3], [4, 5]])]))
    assert "items[0].rows[1]" in _locations(excinfo)


@pytest.mark.unit
def test_table_rows_must_match_the_column_count():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[_table(rows=[[1, 2], [3, 4]])]))
    assert "items[0].rows[0]" in _locations(excinfo)


@pytest.mark.unit
def test_table_cells_must_be_scalars():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[_table(rows=[[1, 2, {"a": 1}], [4, 5, 6]])]))
    assert "items[0].rows[0][2]" in _locations(excinfo)


@pytest.mark.unit
def test_table_requires_columns_and_rows():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "table", "name": "t"}]))
    locations = _locations(excinfo)
    assert "items[0].columns" in locations
    assert "items[0].rows" in locations


@pytest.mark.unit
def test_table_axes_must_name_columns():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[_table(xaxis="nope", yaxis=["T_max", "missing"])]))
    locations = _locations(excinfo)
    assert "items[0].xaxis" in locations
    assert "items[0].yaxis[1]" in locations


@pytest.mark.unit
def test_table_accepts_explicit_axes_that_name_columns():
    doc = build_document(_document(items=[_table(xaxis="time", yaxis=["T_max"], plot="line")]))
    item = doc.items[0]
    assert item.xaxis == "time"
    assert item.yaxis == ("T_max",)
    assert item.plot == "line"


@pytest.mark.unit
def test_table_data_wrapper_is_accepted():
    doc = build_document(
        _document(
            items=[
                {
                    "item_type": "table",
                    "name": "t",
                    "data": {"columns": ["a", "b"], "rows": [[1, 2]]},
                }
            ]
        )
    )
    item = doc.items[0]
    assert item.columns == (TableColumn("a"), TableColumn("b"))
    assert item.rows == ((1, 2),)
    assert "data" not in item.payload


@pytest.mark.unit
def test_table_top_level_wins_over_the_data_wrapper():
    logger = MagicMock()
    doc = build_document(
        _document(items=[_table(data={"columns": ["x"], "rows": [[9]]})]), logger=logger
    )
    assert doc.items[0].columns[0].name == "time"


@pytest.mark.unit
def test_table_data_wrapper_must_be_an_object():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "table", "name": "t", "data": "nope"}]))
    assert "items[0].data" in _locations(excinfo)


@pytest.mark.unit
def test_tree_node_entries_must_be_objects():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": ["nope"]}]))
    assert "items[0].nodes[0]" in _locations(excinfo)


@pytest.mark.unit
def test_tree_child_entries_must_be_objects():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(
                items=[
                    {
                        "item_type": "tree",
                        "name": "t",
                        "nodes": [{"name": "a", "children": ["nope"]}],
                    }
                ]
            )
        )
    assert "items[0].nodes[0].children[0]" in _locations(excinfo)


@pytest.mark.unit
def test_template_entries_must_be_objects():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(templates=["nope"]))
    assert "templates[0]" in _locations(excinfo)


@pytest.mark.unit
def test_template_child_entries_must_be_objects():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(templates=[{"template_type": "basic", "name": "r", "children": ["nope"]}])
        )
    assert "templates[0].children[0]" in _locations(excinfo)


# --------------------------------------------------------------------------
# Items - tree
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_tree_nodes_recurse():
    doc = build_document(
        _document(
            items=[
                {
                    "item_type": "tree",
                    "name": "mesh",
                    "nodes": [
                        {
                            "name": "Assembly",
                            "children": [
                                {"name": "Part A"},
                                {"name": "Part B", "children": [{"name": "Face 1"}]},
                            ],
                        }
                    ],
                }
            ]
        )
    )
    root = doc.items[0].nodes[0]
    assert isinstance(root, TreeNode)
    assert root.name == "Assembly"
    assert len(root.children) == 2
    assert root.children[1].children[0].name == "Face 1"


@pytest.mark.unit
def test_tree_node_value_defaults_to_the_name():
    doc = build_document(
        _document(items=[{"item_type": "tree", "name": "t", "nodes": [{"name": "Alpha"}]}])
    )
    assert doc.items[0].nodes[0].value == "Alpha"


@pytest.mark.unit
def test_tree_node_keeps_an_explicit_value_and_key():
    doc = build_document(
        _document(
            items=[
                {
                    "item_type": "tree",
                    "name": "t",
                    "nodes": [{"name": "Alpha", "value": [1, 2], "key": "alpha"}],
                }
            ]
        )
    )
    node = doc.items[0].nodes[0]
    assert node.value == [1, 2]
    assert node.key == "alpha"


@pytest.mark.unit
def test_tree_node_requires_a_name():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": [{}]}]))
    assert "items[0].nodes[0].name" in _locations(excinfo)


@pytest.mark.unit
def test_tree_node_value_rejects_a_nested_object():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(
                items=[{"item_type": "tree", "name": "t", "nodes": [{"name": "a", "value": {}}]}]
            )
        )
    assert "items[0].nodes[0].value" in _locations(excinfo)


@pytest.mark.unit
def test_tree_node_value_rejects_a_list_of_objects():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(
                items=[{"item_type": "tree", "name": "t", "nodes": [{"name": "a", "value": [{}]}]}]
            )
        )
    assert "items[0].nodes[0].value[0]" in _locations(excinfo)


@pytest.mark.unit
def test_nested_tree_problems_report_their_full_location():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(
                items=[
                    {
                        "item_type": "tree",
                        "name": "t",
                        "nodes": [{"name": "a", "children": [{"name": 5}]}],
                    }
                ]
            )
        )
    assert "items[0].nodes[0].children[0].name" in _locations(excinfo)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_templates_recurse():
    doc = build_document(
        _document(
            templates=[
                {
                    "template_type": "basic",
                    "name": "root",
                    "children": [
                        {
                            "template_type": "panel",
                            "name": "mid",
                            "children": [{"template_type": "box", "name": "leaf"}],
                        }
                    ],
                }
            ]
        )
    )
    root = doc.templates[0]
    assert root.children[0].children[0].name == "leaf"


@pytest.mark.unit
def test_unknown_template_type_is_rejected():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(templates=[{"template_type": "nope", "name": "x"}]))
    assert "templates[0].template_type" in _locations(excinfo)


@pytest.mark.unit
def test_template_convenience_fields_are_parsed():
    doc = build_document(
        _document(
            templates=[
                {
                    "template_type": "basic",
                    "name": "root",
                    "html": "<h1>Hi</h1>",
                    "column_count": 2,
                    "column_widths": [1, 2.5],
                    "sort_selection": "first",
                    "sort_fields": ["name"],
                    "filter_mode": "items",
                    "params": {"custom": 1},
                }
            ]
        )
    )
    template = doc.templates[0]
    assert template.html == "<h1>Hi</h1>"
    assert template.column_count == 2
    assert template.column_widths == (1.0, 2.5)
    assert template.sort_selection == "first"
    assert template.sort_fields == ("name",)
    assert template.filter_mode == "items"
    assert template.params == {"custom": 1}


@pytest.mark.unit
def test_template_column_count_must_be_positive():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(templates=[{"template_type": "basic", "name": "r", "column_count": 0}])
        )
    assert "templates[0].column_count" in _locations(excinfo)


@pytest.mark.unit
@pytest.mark.parametrize("field", ["column_count", "column_widths"])
def test_generators_reject_layout_only_fields(field):
    value = 2 if field == "column_count" else [1.0]
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(templates=[{"template_type": "tablemerge", "name": "g", field: value}])
        )
    assert f"templates[0].{field}" in _locations(excinfo)


@pytest.mark.unit
def test_layouts_accept_layout_only_fields():
    doc = build_document(
        _document(templates=[{"template_type": "panel", "name": "p", "column_count": 3}])
    )
    assert doc.templates[0].column_count == 3


@pytest.mark.unit
def test_template_sort_selection_is_a_closed_set():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(templates=[{"template_type": "basic", "name": "r", "sort_selection": "any"}])
        )
    assert "templates[0].sort_selection" in _locations(excinfo)


@pytest.mark.unit
def test_template_item_filter_is_validated():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(templates=[{"template_type": "basic", "name": "r", "item_filter": "bogus"}])
        )
    assert "templates[0].item_filter" in _locations(excinfo)


@pytest.mark.unit
def test_template_accepts_a_valid_item_filter():
    doc = build_document(
        _document(
            templates=[
                {
                    "template_type": "basic",
                    "name": "r",
                    "item_filter": "A|i_tags|cont|section=results;",
                }
            ]
        )
    )
    assert doc.templates[0].item_filter == "A|i_tags|cont|section=results;"


@pytest.mark.unit
def test_nested_template_problems_report_their_full_location():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(
            _document(
                templates=[
                    {
                        "template_type": "basic",
                        "name": "r",
                        "children": [{"template_type": "panel", "name": ""}],
                    }
                ]
            )
        )
    assert "templates[0].children[0].name" in _locations(excinfo)


@pytest.mark.unit
def test_iterator_binds_to_the_layout_and_the_generator_has_its_own_name():
    doc = build_document(
        _document(
            templates=[
                {"template_type": "iterator", "name": "a"},
                {"template_type": "iterator_generator", "name": "b"},
            ]
        )
    )
    assert doc.templates[0].template_type == "iterator"
    assert doc.templates[1].template_type == "iterator_generator"


# --------------------------------------------------------------------------
# Sessions and datasets
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_sessions_and_datasets_are_parsed_and_noted():
    logger = MagicMock()
    doc = build_document(
        _document(
            sessions=[{"name": "run", "application": "mechanical"}],
            datasets=[{"name": "ds", "format": "csv"}],
        ),
        logger=logger,
    )
    assert doc.sessions[0].application == "mechanical"
    assert doc.datasets[0].format == "csv"
    assert any("not applied" in str(call) for call in logger.info.call_args_list)


@pytest.mark.unit
def test_session_entries_must_be_objects():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(sessions=["nope"]))
    assert "sessions[0]" in _locations(excinfo)


@pytest.mark.unit
def test_dataset_entries_must_be_objects():
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_document(datasets=[1]))
    assert "datasets[0]" in _locations(excinfo)


# --------------------------------------------------------------------------
# load_document
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_load_document_reads_a_file_and_defaults_base_dir(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(_document(items=[{"item_type": "image", "name": "n", "path": "a.png"}])),
        encoding="utf-8",
    )
    doc = load_document(path)
    assert doc.app_id == "demo-app"
    assert doc.base_dir == str(tmp_path)
    assert doc.items[0].base_dir == str(tmp_path)


@pytest.mark.unit
def test_load_document_honors_an_explicit_base_dir(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_document()), encoding="utf-8")
    assert load_document(path, base_dir="/elsewhere").base_dir == "/elsewhere"


@pytest.mark.unit
def test_load_document_reports_a_missing_file(tmp_path: Path):
    with pytest.raises(ImportValidationError) as excinfo:
        load_document(tmp_path / "absent.json")
    assert "does not exist" in str(excinfo.value)


@pytest.mark.unit
def test_load_document_reports_invalid_json(tmp_path: Path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ImportValidationError) as excinfo:
        load_document(path)
    assert "invalid JSON" in str(excinfo.value)
