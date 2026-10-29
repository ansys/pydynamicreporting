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

from ansys.dynamicreporting.core.exceptions import (
    ImportItemValidationError,
    ImportItemVersionError,
)
from ansys.dynamicreporting.core.utils.json_item_import.parser import (
    MAX_TREE_DEPTH,
    build_document,
    load_document,
    read_document,
)


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


@pytest.mark.unit
def test_document_must_be_an_object():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(["not", "an", "object"])
    assert _locations(excinfo) == {"<document>"}


@pytest.mark.unit
def test_app_id_is_required():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document({"schema_version": "1.0"})
    assert "app_id" in _locations(excinfo)


@pytest.mark.unit
def test_app_id_must_be_non_empty():
    with pytest.raises(ImportItemValidationError) as excinfo:
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
    with pytest.raises(ImportItemVersionError):
        build_document({"schema_version": "9.0", "items": 5})


@pytest.mark.unit
def test_empty_document_warns():
    logger = MagicMock()
    build_document(_document(), logger=logger)
    assert any("no items" in str(call) for call in logger.warning.call_args_list)


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
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_are_rejected(literal):
    # Python's json reads these, but they are not valid JSON and the published
    # schema rejects them; the parser must not disagree with the artifact.
    raw = json.loads(
        '{"schema_version":"1.0","app_id":"demo-app","items":[{"item_type":"table",'
        f'"name":"t","columns":["a"],"rows":[[{literal}]]}}]}}'
    )
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(raw)
    assert "items[0].rows[0][0]" in _locations(excinfo)


@pytest.mark.unit
def test_null_is_the_supported_missing_number():
    doc = build_document(
        _document(items=[{"item_type": "table", "name": "t", "columns": ["a"], "rows": [[None]]}])
    )
    assert doc.items[0]["rows"] == ((None,),)


@pytest.mark.unit
def test_deeply_nested_tree_is_a_validation_error_not_a_crash():
    # The builders recurse during parsing, so an unbounded depth would abort
    # the whole document with a RecursionError before any item could be saved.
    node = {"name": "leaf"}
    for _ in range(MAX_TREE_DEPTH + 5):
        node = {"name": "n", "children": [node]}
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": [node]}]))
    assert any("nesting is deeper" in message for _, message in excinfo.value.problems)


@pytest.mark.unit
def test_tree_at_the_depth_limit_is_accepted():
    node = {"name": "leaf"}
    for _ in range(MAX_TREE_DEPTH - 1):
        node = {"name": "n", "children": [node]}
    doc = build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": [node]}]))
    assert doc.items[0]["nodes"]


@pytest.mark.unit
def test_property_shadowing_a_first_class_field_is_warned():
    logger = MagicMock()
    build_document(
        _document(
            items=[
                {
                    "item_type": "table",
                    "name": "t",
                    "columns": ["a"],
                    "rows": [[1]],
                    "plot": "line",
                    "properties": [{"plot": "bar"}],
                }
            ]
        ),
        logger=logger,
    )
    assert any("overrides the first-class" in str(c) for c in logger.warning.call_args_list)


def _table_with_properties(properties):
    return _document(
        items=[
            {
                "item_type": "table",
                "name": "t",
                "columns": ["a"],
                "rows": [[1]],
                "properties": properties,
            }
        ]
    )


@pytest.mark.unit
def test_property_overriding_the_derived_labels_row_is_warned():
    logger = MagicMock()
    build_document(_table_with_properties([{"labels_row": ["b"]}]), logger=logger)
    assert any("derived from 'columns'" in str(c) for c in logger.warning.call_args_list)


@pytest.mark.unit
def test_property_set_more_than_once_is_warned():
    logger = MagicMock()
    build_document(_table_with_properties([{"plot": "bar"}, {"plot": "line"}]), logger=logger)
    assert any("set more than once" in str(c) for c in logger.warning.call_args_list)


@pytest.mark.unit
def test_distinct_properties_raise_no_conflict_warning():
    logger = MagicMock()
    build_document(_table_with_properties([{"line_width": 2}, {"nan_display": "-"}]), logger=logger)
    logger.warning.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize("value", [float("nan"), float("inf"), [1.0, float("-inf")]])
def test_non_finite_tree_values_are_rejected(value):
    node = {"name": "root", "value": value}
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": [node]}]))
    assert any(
        location.startswith("items[0].nodes[0].value") and "NaN and Infinity" in message
        for location, message in excinfo.value.problems
    )


@pytest.mark.unit
def test_finite_tree_values_are_accepted():
    node = {"name": "root", "value": [1.5, None, "x"]}
    doc = build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": [node]}]))
    assert doc.items[0]["nodes"][0]["value"] == [1.5, None, "x"]


@pytest.mark.unit
def test_non_finite_tag_values_are_rejected():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(tags=[{"run": float("nan")}]))
    assert "tags" in _locations(excinfo)
    assert any("NaN and Infinity" in message for _, message in excinfo.value.problems)


@pytest.mark.unit
@pytest.mark.parametrize("value", ["plain text", "a < b", "<p", ""])
def test_html_without_a_tag_is_rejected(value):
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "html", "name": "n", "value": value}]))
    assert "items[0].value" in _locations(excinfo)


@pytest.mark.unit
@pytest.mark.parametrize("value", ["<p>x</p>", "<br/>", "text then <b>bold</b>"])
def test_html_with_a_tag_is_accepted(value):
    doc = build_document(_document(items=[{"item_type": "html", "name": "n", "value": value}]))
    assert doc.items[0]["value"] == value


@pytest.mark.unit
@pytest.mark.parametrize(
    ("item_type", "path"),
    [
        ("image", "plot.jpeg"),
        ("image", "plot.bmp"),
        ("animation", "clip.avi"),
        ("scene", "model.png"),
        ("image", "no_extension"),
    ],
)
def test_unsupported_media_extensions_are_rejected(item_type, path):
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": item_type, "name": "n", "path": path}]))
    assert "items[0].path" in _locations(excinfo)
    assert any("is not supported" in message for _, message in excinfo.value.problems)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("item_type", "path"),
    [
        ("image", "plot.PNG"),
        ("image", "plot.tiff"),
        ("animation", "clip.mp4"),
        ("scene", "model.glb"),
        ("file", "notes"),
        ("file", "archive.tar.gz"),
    ],
)
def test_supported_media_extensions_are_accepted(item_type, path):
    doc = build_document(_document(items=[{"item_type": item_type, "name": "n", "path": path}]))
    assert doc.items[0]["path"] == path


# --------------------------------------------------------------------------
# Path containment (allow_external_paths)
# --------------------------------------------------------------------------


def _image_document(path):
    return _document(items=[{"item_type": "image", "name": "n", "path": path}])


@pytest.mark.unit
def test_external_paths_are_allowed_by_default(tmp_path: Path):
    outside = str(tmp_path.parent / "elsewhere.png")
    doc = build_document(_image_document(outside), base_dir=tmp_path)
    assert doc.items[0]["path"] == outside
    doc = build_document(_image_document("../up.png"), base_dir=tmp_path)
    assert doc.items[0]["path"] == "../up.png"


@pytest.mark.unit
@pytest.mark.parametrize("path", ["../up.png", "media/../../up.png"])
def test_relative_escape_is_rejected_when_external_paths_are_disallowed(path, tmp_path: Path):
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_image_document(path), base_dir=tmp_path, allow_external_paths=False)
    assert "items[0].path" in _locations(excinfo)
    assert any("resolves outside" in message for _, message in excinfo.value.problems)


@pytest.mark.unit
def test_absolute_path_outside_is_rejected_when_external_paths_are_disallowed(tmp_path: Path):
    outside = str(tmp_path.parent / "elsewhere.png")
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_image_document(outside), base_dir=tmp_path, allow_external_paths=False)
    assert "items[0].path" in _locations(excinfo)


@pytest.mark.unit
def test_paths_inside_base_dir_are_accepted_when_external_paths_are_disallowed(tmp_path: Path):
    inside_absolute = str(tmp_path / "media" / "a.png")
    for path in ("media/a.png", "media/../b.png", inside_absolute):
        doc = build_document(_image_document(path), base_dir=tmp_path, allow_external_paths=False)
        assert doc.items[0]["path"] == path


@pytest.mark.unit
def test_inline_items_ignore_the_containment_check(tmp_path: Path):
    doc = build_document(
        _document(items=[{"item_type": "text", "name": "n", "value": "../not/a/path"}]),
        base_dir=tmp_path,
        allow_external_paths=False,
    )
    assert doc.items[0]["value"] == "../not/a/path"


@pytest.mark.unit
def test_load_document_forwards_allow_external_paths(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_image_document("../up.png")), encoding="utf-8")
    assert load_document(path).items[0]["path"] == "../up.png"
    with pytest.raises(ImportItemValidationError):
        load_document(path, allow_external_paths=False)


@pytest.mark.unit
def test_unknown_keys_are_errors_in_strict_mode():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(future_field=1), strict_keys=True)
    assert any("unknown key" in message for _, message in excinfo.value.problems)


@pytest.mark.unit
def test_unknown_item_keys_are_retained():
    doc = build_document(
        _document(items=[{"item_type": "text", "name": "n", "value": "v", "typo_key": []}])
    )
    assert doc.items[0]["extra"] == {"typo_key": []}


@pytest.mark.unit
def test_report_structure_is_not_part_of_the_contract():
    # Templates are imported by load_templates*; a 'templates' key here is just
    # an unknown key, retained and warned about rather than interpreted.
    logger = MagicMock()
    doc = build_document(
        _document(templates=[{"template_type": "basic", "name": "root"}]), logger=logger
    )
    assert not hasattr(doc, "templates")
    assert "templates" in doc.extra
    assert any("unknown key" in str(call) for call in logger.warning.call_args_list)


# --------------------------------------------------------------------------
# Multi-error accumulation
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_every_problem_is_reported_in_one_pass():
    with pytest.raises(ImportItemValidationError) as excinfo:
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
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document({"items": [{"item_type": "text", "name": "a"}]})
    text = str(excinfo.value)
    assert "problems found" in text
    assert "items[0]" in text


@pytest.mark.unit
def test_single_problem_is_rendered_in_the_singular():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document({"schema_version": "1.0"})
    assert "1 problem found" in str(excinfo.value)


# --------------------------------------------------------------------------
# Items - common fields
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_item_must_be_an_object():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=["nope"]))
    assert "items[0]" in _locations(excinfo)


@pytest.mark.unit
def test_unknown_item_type_is_rejected():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "spreadsheet", "name": "x"}]))
    assert "items[0].item_type" in _locations(excinfo)


@pytest.mark.unit
def test_item_common_defaults():
    doc = build_document(_document(items=[{"item_type": "text", "name": "n", "value": "v"}]))
    item = doc.items[0]
    assert item["tags"] == ()
    assert item["source"] == ""
    assert item["sequence"] == 0
    assert item["properties"] == ()


@pytest.mark.unit
def test_item_sequence_rejects_a_boolean():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(
            _document(items=[{"item_type": "text", "name": "n", "value": "v", "sequence": True}])
        )
    assert "items[0].sequence" in _locations(excinfo)


@pytest.mark.unit
def test_item_tags_accept_objects():
    doc = build_document(
        _document(
            items=[
                {
                    "item_type": "text",
                    "name": "n",
                    "value": "v",
                    "tags": [{"section": "intro"}, {"dp": 1}],
                }
            ]
        )
    )
    assert doc.items[0]["tags"] == ({"section": "intro"}, {"dp": 1})


@pytest.mark.unit
def test_item_tags_reject_a_bare_string_entry():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(
            _document(items=[{"item_type": "text", "name": "n", "value": "v", "tags": ["a=1"]}])
        )
    assert "items[0].tags[0]" in _locations(excinfo)


@pytest.mark.unit
def test_item_tags_reject_a_single_mapping():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(
            _document(
                items=[
                    {"item_type": "text", "name": "n", "value": "v", "tags": {"section": "intro"}}
                ]
            )
        )
    assert "items[0].tags" in _locations(excinfo)


@pytest.mark.unit
@pytest.mark.parametrize("tag", [{}, {"k": {"x": 1}}, {"k": [1]}, {"k": None}])
def test_item_tags_reject_what_the_schema_rejects(tag):
    # Mirrors the schema's tagObject: at least one key, scalar values only.
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(
            _document(items=[{"item_type": "text", "name": "n", "value": "v", "tags": [tag]}])
        )
    assert "items[0].tags" in _locations(excinfo)


@pytest.mark.unit
def test_item_properties_must_be_objects():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(
            _document(
                items=[{"item_type": "text", "name": "n", "value": "v", "properties": ["nope"]}]
            )
        )
    assert "items[0].properties[0]" in _locations(excinfo)


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw",
    [
        {"item_type": "text", "name": "n", "value": "v"},
        {"item_type": "image", "name": "n", "path": "a.png"},
        {"item_type": "tree", "name": "n", "nodes": [{"name": "root"}]},
    ],
    ids=lambda raw: raw["item_type"],
)
def test_properties_on_a_non_table_item_are_warned_and_dropped(raw):
    # Only tables persist properties, so keeping them would let both backends
    # discard them without a trace.
    logger = MagicMock()
    doc = build_document(
        _document(items=[{**raw, "properties": [{"line_width": 2}, {"plot_title": "t"}]}]),
        logger=logger,
    )
    assert doc.items[0]["properties"] == ()
    messages = [str(c) for c in logger.warning.call_args_list]
    assert sum("only table items accept properties" in m for m in messages) == 2
    assert any("line_width" in m for m in messages)


@pytest.mark.unit
def test_properties_on_a_table_item_are_kept():
    logger = MagicMock()
    doc = build_document(
        _document(
            items=[
                {
                    "item_type": "table",
                    "name": "t",
                    "columns": ["a"],
                    "rows": [[1]],
                    "properties": [{"line_width": 2}],
                }
            ]
        ),
        logger=logger,
    )
    assert doc.items[0]["properties"] == ({"line_width": 2},)
    assert not any(
        "only table items accept properties" in str(c) for c in logger.warning.call_args_list
    )


# --------------------------------------------------------------------------
# Items - text / html
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("item_type", ["text", "html"])
def test_inline_items_require_a_value(item_type):
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": item_type, "name": "n"}]))
    assert "items[0].value" in _locations(excinfo)


@pytest.mark.unit
@pytest.mark.parametrize(("item_type", "value"), [("text", "body"), ("html", "<p>body</p>")])
def test_inline_items_carry_their_value(item_type, value):
    doc = build_document(_document(items=[{"item_type": item_type, "name": "n", "value": value}]))
    assert doc.items[0]["value"] == value
    assert doc.items[0]["item_type"] == item_type


@pytest.mark.unit
def test_value_must_be_a_string():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "text", "name": "n", "value": 5}]))
    assert "items[0].value" in _locations(excinfo)


# --------------------------------------------------------------------------
# Items - media
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("item_type", ["image", "animation", "scene", "file"])
def test_media_items_require_a_path(item_type):
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": item_type, "name": "n"}]))
    assert "items[0].path" in _locations(excinfo)


@pytest.mark.unit
def test_src_is_not_an_alias_for_path():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "image", "name": "n", "src": "a.png"}]))
    assert "items[0].path" in _locations(excinfo)


@pytest.mark.unit
def test_base_dir_is_attached_to_items():
    doc = build_document(
        _document(items=[{"item_type": "image", "name": "n", "path": "a.png"}]),
        base_dir="/runs/42",
    )
    assert doc.items[0]["base_dir"] == "/runs/42"


@pytest.mark.unit
def test_base_dir_accepts_a_path(tmp_path: Path):
    doc = build_document(
        _document(items=[{"item_type": "image", "name": "n", "path": "a.png"}]),
        base_dir=tmp_path,
    )
    assert doc.base_dir == str(tmp_path)
    assert doc.items[0]["base_dir"] == str(tmp_path)


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
    assert doc.items[0]["columns"] == (
        {"name": "time", "type": "string"},
        {"name": "T_max", "type": "string"},
        {"name": "T_min", "type": "string"},
    )


@pytest.mark.unit
def test_table_columns_accept_objects():
    doc = build_document(
        _document(items=[_table(columns=[{"name": "time", "type": "float"}, "T_max", "T_min"])])
    )
    assert doc.items[0]["columns"][0] == {"name": "time", "type": "float"}


@pytest.mark.unit
def test_table_column_object_requires_a_name():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[_table(columns=[{"type": "float"}, "b", "c"])]))
    assert "items[0].columns" in _locations(excinfo)


@pytest.mark.unit
def test_table_rows_must_be_rectangular():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[_table(rows=[[1, 2, 3], [4, 5]])]))
    assert "items[0].rows[1]" in _locations(excinfo)


@pytest.mark.unit
def test_table_rows_must_match_the_column_count():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[_table(rows=[[1, 2], [3, 4]])]))
    assert "items[0].rows[0]" in _locations(excinfo)


@pytest.mark.unit
def test_table_cells_must_be_scalars():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[_table(rows=[[1, 2, {"a": 1}], [4, 5, 6]])]))
    assert "items[0].rows[0][2]" in _locations(excinfo)


@pytest.mark.unit
def test_table_requires_columns_and_rows():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "table", "name": "t"}]))
    locations = _locations(excinfo)
    assert "items[0].columns" in locations
    assert "items[0].rows" in locations


@pytest.mark.unit
def test_table_axes_must_name_columns():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[_table(xaxis="nope", yaxis=["T_max", "missing"])]))
    locations = _locations(excinfo)
    assert "items[0].xaxis" in locations
    assert "items[0].yaxis[1]" in locations


@pytest.mark.unit
def test_table_accepts_explicit_axes_that_name_columns():
    doc = build_document(_document(items=[_table(xaxis="time", yaxis=["T_max"], plot="line")]))
    item = doc.items[0]
    assert item["xaxis"] == "time"
    assert item["yaxis"] == ("T_max",)
    assert item["plot"] == "line"


@pytest.mark.unit
def test_table_data_wrapper_is_not_accepted():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(
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
    assert {"items[0].columns", "items[0].rows"} <= _locations(excinfo)


@pytest.mark.unit
def test_tree_node_entries_must_be_objects():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": ["nope"]}]))
    assert "items[0].nodes[0]" in _locations(excinfo)


@pytest.mark.unit
def test_tree_child_entries_must_be_objects():
    with pytest.raises(ImportItemValidationError) as excinfo:
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
    root = doc.items[0]["nodes"][0]
    assert root["name"] == "Assembly"
    assert len(root["children"]) == 2
    assert root["children"][1]["children"][0]["name"] == "Face 1"


@pytest.mark.unit
def test_tree_node_value_defaults_to_the_name():
    doc = build_document(
        _document(items=[{"item_type": "tree", "name": "t", "nodes": [{"name": "Alpha"}]}])
    )
    assert doc.items[0]["nodes"][0]["value"] == "Alpha"


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
    node = doc.items[0]["nodes"][0]
    assert node["value"] == [1, 2]
    assert node["key"] == "alpha"


@pytest.mark.unit
def test_tree_node_requires_a_name():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": [{}]}]))
    assert "items[0].nodes[0].name" in _locations(excinfo)


@pytest.mark.unit
def test_tree_node_value_rejects_a_nested_object():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(
            _document(
                items=[{"item_type": "tree", "name": "t", "nodes": [{"name": "a", "value": {}}]}]
            )
        )
    assert "items[0].nodes[0].value" in _locations(excinfo)


@pytest.mark.unit
def test_tree_node_value_rejects_a_list_of_objects():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(
            _document(
                items=[{"item_type": "tree", "name": "t", "nodes": [{"name": "a", "value": [{}]}]}]
            )
        )
    assert "items[0].nodes[0].value[0]" in _locations(excinfo)


@pytest.mark.unit
def test_nested_tree_problems_report_their_full_location():
    with pytest.raises(ImportItemValidationError) as excinfo:
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
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(sessions=["nope"]))
    assert "sessions[0]" in _locations(excinfo)


@pytest.mark.unit
def test_dataset_entries_must_be_objects():
    with pytest.raises(ImportItemValidationError) as excinfo:
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
    assert doc.items[0]["base_dir"] == str(tmp_path)


@pytest.mark.unit
def test_load_document_honors_an_explicit_base_dir(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_document()), encoding="utf-8")
    assert load_document(path, base_dir="/elsewhere").base_dir == "/elsewhere"


@pytest.mark.unit
def test_load_document_reports_a_missing_file(tmp_path: Path):
    with pytest.raises(ImportItemValidationError) as excinfo:
        load_document(tmp_path / "absent.json")
    assert "does not exist" in str(excinfo.value)


@pytest.mark.unit
def test_load_document_reports_invalid_json(tmp_path: Path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ImportItemValidationError) as excinfo:
        load_document(path)
    assert "invalid JSON" in str(excinfo.value)


@pytest.mark.unit
def test_load_document_reports_a_non_utf8_file(tmp_path: Path):
    path = tmp_path / "not_utf8.json"
    path.write_bytes(b'{"app_id": "demo\xff"}')
    with pytest.raises(ImportItemValidationError) as excinfo:
        load_document(path)
    assert "not valid UTF-8" in str(excinfo.value)


@pytest.mark.unit
def test_load_document_reports_an_unreadable_path(tmp_path: Path):
    # A directory cannot be opened as a file on any platform; the OS error
    # differs (IsADirectoryError vs PermissionError) but is wrapped the same.
    with pytest.raises(ImportItemValidationError) as excinfo:
        load_document(tmp_path)
    assert "cannot be read" in str(excinfo.value)


@pytest.mark.unit
def test_load_document_accepts_a_path_base_dir(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_document()), encoding="utf-8")
    assert load_document(path, base_dir=tmp_path / "media").base_dir == str(tmp_path / "media")


@pytest.mark.unit
def test_load_document_accepts_a_utf8_bom(tmp_path: Path):
    # Several Windows editors and writers prepend a BOM; plain utf-8 decoding
    # would reject the file as invalid JSON.
    path = tmp_path / "bom.json"
    path.write_text(json.dumps(_document(items=[])), encoding="utf-8-sig")
    assert load_document(path).app_id == "demo-app"


# --------------------------------------------------------------------------
# read_document
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_read_document_decodes_without_validating(tmp_path: Path):
    # Validation belongs to build_document, so a contract violation still
    # decodes; the dict entry points validate it afterwards.
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"surprise": 1}), encoding="utf-8")
    assert read_document(path) == {"surprise": 1}


@pytest.mark.unit
def test_read_document_reports_a_missing_file(tmp_path: Path):
    with pytest.raises(ImportItemValidationError) as excinfo:
        read_document(tmp_path / "absent.json")
    assert "does not exist" in str(excinfo.value)
