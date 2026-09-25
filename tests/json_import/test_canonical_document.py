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

"""The canonical sample document from the import schema specification.

``CANONICAL_DOCUMENT`` is a verbatim transcription of section 7 of
``ADR_IMPORT_SCHEMA.md``. The happy-path tests assert every claim the
specification makes about it, including the worked table result. The
unhappy-path tests mutate one thing at a time and assert the document is
rejected at the documented location.

If the specification changes, these tests are the first thing that should
fail.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.serverless.import_backend import (
    ITEM_CLASS,
    ServerlessImportBackend,
)
from ansys.dynamicreporting.core.utils.json_import.errors import (
    ImportValidationError,
    ImportVersionError,
)
from ansys.dynamicreporting.core.utils.json_import.importer import JSONImporter
from ansys.dynamicreporting.core.utils.json_import.models import TableColumn
from ansys.dynamicreporting.core.utils.json_import.parser import build_document, load_document

CANONICAL_DOCUMENT: dict[str, Any] = {
    "schema_version": "1.0",
    "app_id": "adr-mechanical",
    "tags": [{"report": "thermal_run_42"}],
    "metadata": {"producer": "adr-mechanical", "producer_version": "2026R1"},
    "templates": [
        {
            "template_type": "basic",
            "name": "Thermal Summary",
            "html": "<h1>Thermal Summary</h1>",
            "children": [
                {
                    "template_type": "panel",
                    "name": "Results",
                    "item_filter": "A|i_tags|cont|section=results;",
                }
            ],
        }
    ],
    "items": [
        {
            "item_type": "text",
            "name": "Summary",
            "tags": [{"section": "intro"}],
            "value": "Simulation completed successfully.",
        },
        {
            "item_type": "html",
            "name": "Notes",
            "tags": [{"section": "intro"}],
            "value": "<p>All results within range.</p>",
        },
        {
            "item_type": "image",
            "name": "Contour",
            "tags": [{"section": "results"}],
            "path": "contour.png",
        },
        {
            "item_type": "table",
            "name": "Probe Table",
            "tags": [{"section": "results"}],
            "columns": ["time", "T_max", "T_min"],
            "rows": [[0.0, 300.1, 290.0], [1.0, 320.5, 295.2]],
            "plot": "line",
            "xaxis": "time",
            "yaxis": ["T_max", "T_min"],
            "properties": [{"line_width": 2}, {"table_title": "Probe temperatures"}],
        },
        {
            "item_type": "tree",
            "name": "Mesh",
            "tags": [{"section": "results"}],
            "nodes": [
                {"name": "Assembly", "children": [{"name": "Part A"}, {"name": "Part B"}]}
            ],
        },
    ],
}

# Positions of the five items in the canonical document.
TEXT, HTML_ITEM, IMAGE, TABLE, TREE = range(5)


def _mutated(mutate) -> dict[str, Any]:
    """Return a deep copy of the canonical document with ``mutate`` applied."""
    document = copy.deepcopy(CANONICAL_DOCUMENT)
    mutate(document)
    return document


def _locations(excinfo) -> set[str]:
    return {location for location, _ in excinfo.value.problems}


@pytest.fixture
def canonical():
    """A parsed copy of the canonical document."""
    return build_document(copy.deepcopy(CANONICAL_DOCUMENT))


# --------------------------------------------------------------------------
# Happy path - the envelope
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_canonical_document_is_valid(canonical):
    assert canonical.schema_version == "1.0"
    assert canonical.app_id == "adr-mechanical"
    assert len(canonical.items) == 5
    assert len(canonical.templates) == 1


@pytest.mark.unit
def test_canonical_document_keeps_its_tags_and_metadata(canonical):
    assert canonical.tags == ({"report": "thermal_run_42"},)
    assert canonical.metadata == {
        "producer": "adr-mechanical",
        "producer_version": "2026R1",
    }


@pytest.mark.unit
def test_canonical_document_has_no_unknown_keys(canonical):
    assert canonical.extra == {}
    assert all(item.extra == {} for item in canonical.items)


@pytest.mark.unit
def test_canonical_document_is_accepted_in_strict_mode():
    # Nothing in the specification sample is an unknown key.
    build_document(copy.deepcopy(CANONICAL_DOCUMENT), strict_keys=True)


@pytest.mark.unit
def test_canonical_document_round_trips_through_a_file(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(CANONICAL_DOCUMENT), encoding="utf-8")
    document = load_document(path)
    assert document.app_id == "adr-mechanical"
    assert len(document.items) == 5
    # Relative media paths resolve against the directory holding the document.
    assert document.items[IMAGE].base_dir == str(tmp_path)


# --------------------------------------------------------------------------
# Happy path - the template tree
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_canonical_template_tree(canonical):
    root = canonical.templates[0]
    assert root.template_type == "basic"
    assert root.name == "Thermal Summary"
    assert root.html == "<h1>Thermal Summary</h1>"

    child = root.children[0]
    assert child.template_type == "panel"
    assert child.name == "Results"
    assert child.item_filter == "A|i_tags|cont|section=results;"
    assert child.children == ()


# --------------------------------------------------------------------------
# Happy path - the items
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_canonical_item_types_and_names(canonical):
    assert [(item.item_type, item.name) for item in canonical.items] == [
        ("text", "Summary"),
        ("html", "Notes"),
        ("image", "Contour"),
        ("table", "Probe Table"),
        ("tree", "Mesh"),
    ]


@pytest.mark.unit
def test_canonical_inline_items(canonical):
    assert canonical.items[TEXT].value == "Simulation completed successfully."
    assert canonical.items[HTML_ITEM].value == "<p>All results within range.</p>"


@pytest.mark.unit
def test_canonical_image_path(canonical):
    assert canonical.items[IMAGE].path == "contour.png"


@pytest.mark.unit
def test_canonical_tree_keeps_both_children(canonical):
    root = canonical.items[TREE].nodes[0]
    assert root.name == "Assembly"
    assert [child.name for child in root.children] == ["Part A", "Part B"]
    # An omitted value defaults to the node name.
    assert root.value == "Assembly"


@pytest.mark.unit
def test_canonical_table_is_parsed(canonical):
    table = canonical.items[TABLE]
    assert table.columns == (
        TableColumn("time"),
        TableColumn("T_max"),
        TableColumn("T_min"),
    )
    assert table.rows == ((0.0, 300.1, 290.0), (1.0, 320.5, 295.2))
    assert table.plot == "line"
    assert table.xaxis == "time"
    assert table.yaxis == ("T_max", "T_min")
    assert table.properties == ({"line_width": 2}, {"table_title": "Probe temperatures"})


# --------------------------------------------------------------------------
# Happy path - the worked result from the specification
# --------------------------------------------------------------------------


@pytest.fixture
def imported(tmp_path: Path):
    """Drive the canonical document through the serverless adapter."""
    adr = MagicMock()
    adr._logger = MagicMock()
    created: dict[str, Any] = {}

    def create_item(item_class, **kwargs):
        item = MagicMock()
        item.imported_class = item_class
        item.imported_content = kwargs["content"]
        item.imported_tags = kwargs["tags"]
        created[kwargs["name"]] = item
        return item

    adr.create_item.side_effect = create_item
    adr.create_template.side_effect = lambda template_class, **kwargs: MagicMock()

    document = build_document(copy.deepcopy(CANONICAL_DOCUMENT), base_dir=str(tmp_path))
    result = JSONImporter(ServerlessImportBackend(adr)).import_document(document)
    return result, created


@pytest.mark.unit
def test_canonical_import_reports_what_it_created(imported):
    result, _ = imported
    assert result.ok
    assert result.app_id == "adr-mechanical"
    assert result.items_saved == 5
    # Both the root and its panel child, not just the root.
    assert result.templates_created == 2


@pytest.mark.unit
def test_canonical_table_is_stored_transposed(imported):
    _, created = imported
    array = created["Probe Table"].imported_content
    # The specification's worked result: 2x3 on the wire, 3x2 once stored.
    assert array.shape == (3, 2)


@pytest.mark.unit
def test_canonical_table_labels_and_axes(imported):
    _, created = imported
    table = created["Probe Table"]
    assert table.labels_row == ["time", "T_max", "T_min"]
    assert len(table.labels_row) == table.imported_content.shape[0]
    assert table.xaxis == "time"
    assert table.yaxis == ["T_max", "T_min"]
    assert table.plot == "line"


@pytest.mark.unit
def test_canonical_table_properties_are_applied(imported):
    _, created = imported
    table = created["Probe Table"]
    assert table.line_width == 2
    assert table.table_title == "Probe temperatures"


@pytest.mark.unit
def test_canonical_items_bind_to_their_own_classes(imported):
    _, created = imported
    assert created["Summary"].imported_class is ITEM_CLASS["text"]
    assert created["Notes"].imported_class is ITEM_CLASS["html"]
    assert created["Contour"].imported_class is ITEM_CLASS["image"]
    assert created["Probe Table"].imported_class is ITEM_CLASS["table"]
    assert created["Mesh"].imported_class is ITEM_CLASS["tree"]


@pytest.mark.unit
def test_canonical_document_tags_merge_into_every_item(imported):
    _, created = imported
    assert created["Summary"].imported_tags == "report=thermal_run_42 section=intro"
    assert created["Contour"].imported_tags == "report=thermal_run_42 section=results"


@pytest.mark.unit
def test_canonical_image_path_resolves_against_the_document(imported, tmp_path: Path):
    _, created = imported
    assert created["Contour"].imported_content == str(tmp_path / "contour.png")


# --------------------------------------------------------------------------
# Unhappy path - one mutation at a time
# --------------------------------------------------------------------------


def _drop_app_id(document):
    del document["app_id"]


def _blank_app_id(document):
    document["app_id"] = ""


def _unknown_item_type(document):
    document["items"][TEXT]["item_type"] = "spreadsheet"


def _drop_text_value(document):
    del document["items"][TEXT]["value"]


def _drop_image_path(document):
    del document["items"][IMAGE]["path"]


def _ragged_rows(document):
    document["items"][TABLE]["rows"][1] = [1.0, 320.5]


def _row_width_mismatches_columns(document):
    document["items"][TABLE]["columns"] = ["time", "T_max"]


def _xaxis_is_not_a_column(document):
    document["items"][TABLE]["xaxis"] = "pressure"


def _yaxis_is_not_a_column(document):
    document["items"][TABLE]["yaxis"] = ["T_max", "pressure"]


def _non_scalar_cell(document):
    document["items"][TABLE]["rows"][0][2] = {"value": 290.0}


def _nested_tree_node_without_a_name(document):
    document["items"][TREE]["nodes"][0]["children"][1] = {"value": "Part B"}


def _invalid_item_filter(document):
    document["templates"][0]["children"][0]["item_filter"] = "section=results"


def _unknown_template_type(document):
    document["templates"][0]["template_type"] = "supergrid"


def _layout_field_on_a_generator(document):
    document["templates"][0]["template_type"] = "tablemerge"
    document["templates"][0]["column_count"] = 2


def _non_positive_column_count(document):
    document["templates"][0]["column_count"] = 0


def _bad_sort_selection(document):
    document["templates"][0]["sort_selection"] = "middle"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("mutate", "location"),
    [
        (_drop_app_id, "app_id"),
        (_blank_app_id, "app_id"),
        (_unknown_item_type, f"items[{TEXT}].item_type"),
        (_drop_text_value, f"items[{TEXT}].value"),
        (_drop_image_path, f"items[{IMAGE}].path"),
        (_ragged_rows, f"items[{TABLE}].rows[1]"),
        (_row_width_mismatches_columns, f"items[{TABLE}].rows[0]"),
        (_xaxis_is_not_a_column, f"items[{TABLE}].xaxis"),
        (_yaxis_is_not_a_column, f"items[{TABLE}].yaxis[1]"),
        (_non_scalar_cell, f"items[{TABLE}].rows[0][2]"),
        (_nested_tree_node_without_a_name, f"items[{TREE}].nodes[0].children[1].name"),
        (_invalid_item_filter, "templates[0].children[0].item_filter"),
        (_unknown_template_type, "templates[0].template_type"),
        (_layout_field_on_a_generator, "templates[0].column_count"),
        (_non_positive_column_count, "templates[0].column_count"),
        (_bad_sort_selection, "templates[0].sort_selection"),
    ],
    ids=lambda value: value.__name__.lstrip("_") if callable(value) else value,
)
def test_canonical_document_rejects_a_single_break(mutate, location):
    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_mutated(mutate))
    assert location in _locations(excinfo)


# --------------------------------------------------------------------------
# Unhappy path - versioning
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("version", ["2.0", "9.4"])
def test_canonical_document_rejects_a_newer_major(version):
    def mutate(document):
        document["schema_version"] = version

    with pytest.raises(ImportVersionError):
        build_document(_mutated(mutate))


@pytest.mark.unit
@pytest.mark.parametrize("version", ["1", "1.0.0", "one.zero"])
def test_canonical_document_rejects_a_malformed_version(version):
    def mutate(document):
        document["schema_version"] = version

    with pytest.raises(ImportVersionError):
        build_document(_mutated(mutate))


@pytest.mark.unit
def test_canonical_document_accepts_a_newer_minor():
    def mutate(document):
        document["schema_version"] = "1.9"

    assert build_document(_mutated(mutate)).schema_version == "1.9"


# --------------------------------------------------------------------------
# Unhappy path - unknown keys and multiple breaks
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_an_unknown_key_is_retained_by_default_and_rejected_when_strict():
    def mutate(document):
        document["items"][TEXT]["unexpected"] = 1

    document = _mutated(mutate)
    assert build_document(copy.deepcopy(document)).items[TEXT].extra == {"unexpected": 1}

    with pytest.raises(ImportValidationError) as excinfo:
        build_document(document, strict_keys=True)
    assert f"items[{TEXT}]" in _locations(excinfo)


@pytest.mark.unit
def test_every_break_is_reported_in_one_pass():
    def mutate(document):
        del document["app_id"]
        del document["items"][TEXT]["value"]
        document["items"][TABLE]["xaxis"] = "pressure"
        document["templates"][0]["children"][0]["item_filter"] = "nope"

    with pytest.raises(ImportValidationError) as excinfo:
        build_document(_mutated(mutate))

    locations = _locations(excinfo)
    assert {
        "app_id",
        f"items[{TEXT}].value",
        f"items[{TABLE}].xaxis",
        "templates[0].children[0].item_filter",
    } <= locations


@pytest.mark.unit
def test_a_broken_document_never_reaches_the_backend():
    def mutate(document):
        del document["items"][IMAGE]["path"]

    adr = MagicMock()
    adr._logger = MagicMock()
    importer = JSONImporter(ServerlessImportBackend(adr))

    with pytest.raises(ImportValidationError):
        importer.import_document(build_document(_mutated(mutate)))

    adr.create_item.assert_not_called()
    adr.create_template.assert_not_called()
