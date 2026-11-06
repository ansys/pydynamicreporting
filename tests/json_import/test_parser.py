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
    doc = build_document({"app_id": "demo-app"})
    assert doc.schema_version == "1.0"


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
def test_unknown_keys_are_warned_about_and_ignored():
    logger = MagicMock()
    build_document(_document(future_field={"a": 1}), logger=logger)
    assert any("unknown key" in str(call) for call in logger.warning.call_args_list)


@pytest.mark.unit
@pytest.mark.parametrize("key", ["metadata", "sessions", "datasets"])
def test_unapplied_envelope_sections_are_unknown_keys(key):
    # Not part of v1.0; a producer that still sends them gets a warning, not an error.
    logger = MagicMock()
    build_document(_document(**{key: []}), logger=logger)
    assert any(repr(key) in str(call) for call in logger.warning.call_args_list)


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
        ("image", "no_extension"),
    ],
)
def test_unsupported_image_extensions_are_rejected(item_type, path):
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": item_type, "name": "n", "path": path}]))
    assert "items[0].path" in _locations(excinfo)
    assert any("is not supported" in message for _, message in excinfo.value.problems)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("item_type", "path"),
    [("animation", "clip.avi"), ("scene", "model.png"), ("scene", "no_extension")],
)
def test_animation_and_scene_extensions_are_left_to_the_backends(item_type, path):
    # Both backends reject these at save time; see test_backend_parity.
    doc = build_document(_document(items=[{"item_type": item_type, "name": "n", "path": path}]))
    assert doc.items[0]["path"] == path


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


@pytest.mark.unit
def test_unknown_item_keys_are_dropped():
    doc = build_document(
        _document(items=[{"item_type": "text", "name": "n", "value": "v", "typo_key": []}])
    )
    assert "typo_key" not in doc.items[0]


@pytest.mark.unit
def test_report_structure_is_not_part_of_the_contract():
    # Templates are imported by load_templates*; a 'templates' key here is just
    # an unknown key, warned about and ignored rather than interpreted.
    logger = MagicMock()
    doc = build_document(
        _document(templates=[{"template_type": "basic", "name": "root"}]), logger=logger
    )
    assert not hasattr(doc, "templates")
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


@pytest.mark.unit
def test_table_requires_an_array():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "table", "name": "t"}]))
    assert "items[0].array" in _locations(excinfo)


@pytest.mark.unit
def test_table_array_must_be_a_list():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "table", "name": "t", "array": "1,2"}]))
    assert "items[0].array" in _locations(excinfo)


@pytest.mark.unit
def test_table_array_and_properties_are_passed_through_unchanged():
    array = [[0.0, 1.0], [300.1, 320.5]]
    properties = {"labels_row": ["time", "T_max"], "xaxis": "time", "line_color": ["red"]}
    raw = {"item_type": "table", "name": "t", "array": array, "dtype": "f8", **properties}
    item = build_document(_document(items=[raw])).items[0]
    assert item["array"] is array
    assert item["dtype"] == "f8"
    assert {key: item[key] for key in properties} == properties


@pytest.mark.unit
@pytest.mark.parametrize(
    "fields",
    [
        {"array": [[1, 2], [3]]},
        {"array": [[{"a": 1}]]},
        {"array": [[float("nan")]]},
        {"array": [[1, 2]], "labels_row": ["a", "b", "c"]},
        {"array": [[1, 2]], "xaxis": "not a label"},
    ],
    ids=["ragged", "object-cell", "nan", "label-count", "unknown-axis"],
)
def test_table_contents_are_left_to_the_backend(fields):
    # The backend table validators own the array checks, so the parser does
    # not reject what they would; the item fails when it is saved instead.
    doc = build_document(_document(items=[{"item_type": "table", "name": "t", **fields}]))
    assert doc.items[0]["array"] is fields["array"]


@pytest.mark.unit
def test_tree_node_entries_must_be_objects():
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": ["nope"]}]))
    assert "items[0].nodes[0]" in _locations(excinfo)


# --------------------------------------------------------------------------
# Items - tree
# --------------------------------------------------------------------------


def _tree_nodes(nodes: list) -> list:
    doc = build_document(_document(items=[{"item_type": "tree", "name": "t", "nodes": nodes}]))
    return doc.items[0]["nodes"]


@pytest.mark.unit
def test_complete_tree_nodes_are_passed_through_unchanged():
    nodes = [
        {
            "key": "assembly",
            "name": "Assembly",
            "value": None,
            "state": "expanded",
            "header": True,
            "children": [{"key": "part", "name": "Part A", "value": [1, [2, 3]]}],
        }
    ]
    assert _tree_nodes(nodes) == nodes


@pytest.mark.unit
@pytest.mark.parametrize(
    "node",
    [
        {"name": "missing key and value"},
        {"key": "k", "name": "n", "value": {}},
        {"key": "k", "name": "n", "value": float("nan")},
        {"key": "k", "name": "n", "value": 1, "children": ["not a node"]},
    ],
    ids=["missing-fields", "object-value", "nan-value", "non-object-child"],
)
def test_tree_node_contents_are_left_to_the_backend(node):
    # The backend tree validators own node checks, so the parser does not
    # reject what they would; the item fails when it is saved instead.
    assert _tree_nodes([node])[0] is node


@pytest.mark.unit
def test_a_deep_tree_does_not_recurse_in_the_parser():
    # The parser no longer walks nodes, so depth is limited only by the backends.
    node = {"key": "k", "name": "leaf", "value": 1}
    for _ in range(500):
        node = {"key": "k", "name": "n", "value": 1, "children": [node]}
    assert _tree_nodes([node])[0] is node


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
def test_load_document_accepts_a_decoded_dict():
    document = _document(items=[{"item_type": "image", "name": "n", "path": "a.png"}])
    doc = load_document(document)
    assert doc.app_id == "demo-app"
    # Without a file there is no document directory; paths stay relative to the CWD.
    assert doc.base_dir is None


@pytest.mark.unit
def test_load_document_honors_a_base_dir_for_a_dict(tmp_path: Path):
    assert load_document(_document(), base_dir=tmp_path).base_dir == str(tmp_path)


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
    # decodes; load_document validates it afterwards.
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"surprise": 1}), encoding="utf-8")
    assert read_document(path) == {"surprise": 1}


@pytest.mark.unit
def test_read_document_reports_a_missing_file(tmp_path: Path):
    with pytest.raises(ImportItemValidationError) as excinfo:
        read_document(tmp_path / "absent.json")
    assert "does not exist" in str(excinfo.value)
