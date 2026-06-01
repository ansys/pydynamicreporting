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

import json

import pytest
from pydantic import ValidationError

from ansys.dynamicreporting.core.utils.json_importer_models import (
    ReportItemsModel,
    TableColumnModel,
    TableItemModel,
    TextItemModel,
    TreeItemModel,
)


def test_report_items_model_supports_table_rows_and_columns_at_top_level(tmp_path):
    payload = {
        "app_id": "app-1",
        "tags": [],
        "items": [
            {
                "item_type": "table",
                "name": "Table A",
                "tags": [],
                "columns": [
                    {"name": "time", "type": "float", "unit": "s"},
                    "value",
                ],
                "rows": [[0.0, 1.1], [1.0, 2.2]],
            }
        ],
    }
    data_file = tmp_path / "report_items.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    model = ReportItemsModel.from_json_file(data_file)

    assert model.app_id == "app-1"
    assert model.items[0].item_type == "table"
    assert model.items[0].data.rows == [[0.0, 1.1], [1.0, 2.2]]
    assert model.items[0].data.columns[0].name == "time"


def test_report_items_model_supports_discriminated_text_items(tmp_path):
    payload = {
        "app_id": "app-2",
        "tags": [],
        "items": [
            {
                "item_type": "text",
                "name": "Message",
                "tags": [],
                "value": "hello",
            }
        ],
    }
    data_file = tmp_path / "report_items_text.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    model = ReportItemsModel.from_json_file(data_file)

    assert model.items[0].item_type == "text"
    assert model.items[0].value == "hello"


def test_report_items_model_allows_partial_image_metadata(tmp_path):
    payload = {
        "app_id": "app-3",
        "tags": [],
        "items": [
            {
                "item_type": "image",
                "name": "Plot",
                "tags": [],
                "src": "C://tmp/plot.png",
                "data": {"format": "png"},
            }
        ],
    }
    data_file = tmp_path / "report_items_image.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    model = ReportItemsModel.from_json_file(data_file)

    assert model.items[0].item_type == "image"
    assert model.items[0].src == "C://tmp/plot.png"


def test_report_items_model_allows_scene_metadata_as_extra_payload(tmp_path):
    payload = {
        "app_id": "app-4",
        "tags": [],
        "items": [
            {
                "item_type": "scene",
                "name": "Assembly",
                "tags": [],
                "src": "C://tmp/assembly.avz",
                "data": {"format": "avz", "description": "assembly scene"},
            }
        ],
    }
    data_file = tmp_path / "report_items_scene.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    model = ReportItemsModel.from_json_file(data_file)

    assert model.items[0].item_type == "scene"
    assert model.items[0].src == "C://tmp/assembly.avz"


def test_report_items_model_validates_full_sample_payload(tmp_path):
    payload = {
        "app_id": "adr-mechanical",
        "tags": [{"report": "template_json_import"}],
        "items": [
            {
                "item_type": "text",
                "name": "Summary",
                "value": "Simulation completed successfully.",
                "tags": [{"section": "child_json_import"}],
            },
            {
                "item_type": "text",
                "name": "Formatted Report HTML",
                "value": "<h1>Report</h1><p>All results are within range.</p>",
                "tags": [{"section": "child_json_import"}],
            },
            {
                "item_type": "image",
                "name": "Result Plot",
                "src": "C://ANSYSDev/repos/adr_mechanical/assets/image.png",
                "tags": [{"section": "child_json_import"}],
            },
            {
                "item_type": "file",
                "name": "Raw Data File",
                "src": "C://ANSYSDev/repos/adr_mechanical/assets/results.csv",
                "tags": [{"section": "child_json_import"}],
            },
            {
                "item_type": "scene",
                "name": "3D Scene",
                "src": "C://ANSYSDev/repos/adr_mechanical/assets/scene.avz",
                "tags": [{"section": "child_json_import"}],
            },
            {
                "item_type": "table",
                "name": "Temperature Table One",
                "tags": [{"section": "child_json_import"}],
                "columns": [],
                "rows": [
                    [0.5, 10, 101325],
                    [0.5, 12, 101300],
                    [1, 15, 101280],
                ],
            },
            {
                "item_type": "table",
                "name": "Temperature Table One",
                "tags": [{"section": "child_json_import"}],
                "columns": ["X", "Sin", "Cos"],
                "rows": [[1, 2], [3, 4]],
                "plot": "line",
                "xaxis": "X",
                "yaxis": ["Sin", "Cos"],
                "properties": [
                    {"format": "floatdot0"},
                    {"zaxis": "Z"},
                    {"xaxis_format": "floatdot0"},
                    {"ytitle": "Values"},
                    {"ytitle": "X"},
                ],
            },
            {
                "item_type": "tree",
                "name": "Hierarchy",
                "tags": [{"section": "child_json_import"}],
                "data": {
                    "nodes": [
                        {
                            "name": "Parent-Root",
                            "children": [
                                {
                                    "name": "Child One",
                                    "children": [{"name": "Child One One"}],
                                },
                                {
                                    "name": "Child Two",
                                    "children": [
                                        {
                                            "name": "Grandchild One",
                                            "children": [{"name": "Child Two Two"}],
                                        }
                                    ],
                                },
                            ],
                        }
                    ]
                },
            },
        ],
    }
    data_file = tmp_path / "report_items_sample.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    model = ReportItemsModel.from_json_file(data_file)

    assert model.app_id == "adr-mechanical"
    assert model.tags == [{"report": "template_json_import"}]
    assert len(model.items) == 8
    assert [item.item_type for item in model.items] == [
        "text",
        "text",
        "image",
        "file",
        "scene",
        "table",
        "table",
        "tree",
    ]
    assert model.items[0].value == "Simulation completed successfully."
    assert model.items[2].src.endswith("assets/image.png")
    assert model.items[5].data.rows[2] == [1, 15, 101280]
    assert model.items[6].data.columns == ["X", "Sin", "Cos"]
    assert model.items[7].data.nodes[0].children[1].children[0].name == "Grandchild One"


def test_report_items_model_raises_for_unknown_item_type(tmp_path):
    payload = {
        "app_id": "adr-mechanical",
        "items": [{"item_type": "unknown", "name": "Bad"}],
    }
    data_file = tmp_path / "report_items_invalid.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        ReportItemsModel.from_json_file(data_file)


# ---------------------------------------------------------------------------
# from_json_file — error handling
# ---------------------------------------------------------------------------


def test_from_json_file_raises_for_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError):
        ReportItemsModel.from_json_file(missing)


def test_from_json_file_raises_for_malformed_json(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        ReportItemsModel.from_json_file(bad_file)


# ---------------------------------------------------------------------------
# TableColumnModel
# ---------------------------------------------------------------------------


def test_table_column_model_stores_name_and_type():
    col = TableColumnModel(name="Velocity", type="float")
    assert col.name == "Velocity"
    assert col.type == "float"


def test_table_column_model_missing_name_raises():
    with pytest.raises(ValidationError):
        TableColumnModel(type="float")


def test_table_column_model_missing_type_raises():
    with pytest.raises(ValidationError):
        TableColumnModel(name="X")


# ---------------------------------------------------------------------------
# TableItemModel — model validator
# ---------------------------------------------------------------------------


def test_table_item_model_wraps_columns_and_rows_into_data():
    item = TableItemModel(
        name="T",
        tags=[],
        columns=["A", "B"],
        rows=[[1.0, 2.0]],
    )
    assert item.data.columns == ["A", "B"]
    assert item.data.rows == [[1.0, 2.0]]


def test_table_item_model_does_not_overwrite_explicit_data():
    # When 'data' is already provided, the validator should leave it untouched
    # even if top-level 'columns'/'rows' are also present.
    item = TableItemModel(
        name="T",
        tags=[],
        data={"columns": ["X"], "rows": [[9.0]]},
        columns=["should", "be", "ignored"],
        rows=[[0.0, 0.0, 0.0]],
    )
    assert item.data.columns == ["X"]
    assert item.data.rows == [[9.0]]


# ---------------------------------------------------------------------------
# TextItemModel
# ---------------------------------------------------------------------------


def test_text_item_model_missing_value_raises():
    with pytest.raises(ValidationError):
        TextItemModel(name="T", tags=[])


# ---------------------------------------------------------------------------
# TreeItemModel — leaf nodes
# ---------------------------------------------------------------------------


def test_tree_node_leaf_has_empty_children_by_default(tmp_path):
    payload = {
        "app_id": "app",
        "tags": [],
        "items": [
            {
                "item_type": "tree",
                "name": "T",
                "tags": [],
                "data": {"nodes": [{"name": "LeafNode"}]},
            }
        ],
    }
    data_file = tmp_path / "tree_leaf.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    model = ReportItemsModel.from_json_file(data_file)
    leaf = model.items[0].data.nodes[0]

    assert leaf.name == "LeafNode"
    assert leaf.children == []


# ---------------------------------------------------------------------------
# ReportItemsModel — edge cases
# ---------------------------------------------------------------------------


def test_report_items_model_with_empty_items_list(tmp_path):
    payload = {"app_id": "empty-app", "tags": [], "items": []}
    data_file = tmp_path / "empty.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    model = ReportItemsModel.from_json_file(data_file)

    assert model.app_id == "empty-app"
    assert model.items == []


def test_report_items_model_allows_extra_top_level_fields(tmp_path):
    payload = {
        "app_id": "app",
        "tags": [],
        "items": [],
        "custom_field": "extra",
        "version": 42,
    }
    data_file = tmp_path / "extra.json"
    data_file.write_text(json.dumps(payload), encoding="utf-8")

    # Should not raise; extra fields are allowed by the model config
    model = ReportItemsModel.from_json_file(data_file)
    assert model.app_id == "app"
