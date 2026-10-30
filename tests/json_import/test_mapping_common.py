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

"""Tests for the shared mapping helpers."""

from __future__ import annotations

import os
from pathlib import Path

import numpy
import pytest

from ansys.dynamicreporting.core.utils.json_item_import.mapping import (
    column_labels,
    derive_axes,
    flatten_tree,
    item_content,
    resolve_path,
    rows_to_array,
    table_fields,
)
from tests.json_import.helpers import build_item as _model

COLUMNS = ({"name": "time"}, {"name": "T_max"}, {"name": "T_min"})


# --------------------------------------------------------------------------
# rows_to_array - orientation is the critical behaviour
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_rows_to_array_transposes_to_series_per_row():
    # Wire: 2 records x 3 columns. ADR stores 3 series x 2 samples.
    rows = ((0.0, 300.1, 290.0), (1.0, 320.5, 295.2))
    array = rows_to_array(rows)
    assert array.shape == (3, 2)
    assert array.shape[0] == len(COLUMNS)
    assert list(array[0]) == [0.0, 1.0]


@pytest.mark.unit
@pytest.mark.parametrize(("n_rows", "n_columns"), [(1, 5), (5, 1), (2, 3), (3, 2), (7, 4), (4, 7)])
def test_rows_to_array_shape_is_columns_by_rows(n_rows, n_columns):
    rows = tuple(tuple(float(r * n_columns + c) for c in range(n_columns)) for r in range(n_rows))
    assert rows_to_array(rows).shape == (n_columns, n_rows)


@pytest.mark.unit
def test_rows_to_array_uses_float_for_numeric_data():
    assert rows_to_array(((1, 2), (3, 4))).dtype.kind == "f"


@pytest.mark.unit
def test_rows_to_array_falls_back_to_bytes_for_text():
    array = rows_to_array((("alpha", 1), ("beta", 2)))
    assert array.dtype.kind == "S"
    assert array.shape == (2, 2)


@pytest.mark.unit
def test_rows_to_array_keeps_numeric_looking_strings_as_text():
    # JSON strings stay text even when NumPy could parse them as numbers;
    # otherwise identifiers such as "001" would silently become 1.0.
    array = rows_to_array((("001", "90210"), ("007", "10001")))
    assert array.dtype.kind == "S"
    assert [cell.decode() for cell in array[0]] == ["001", "007"]
    assert [cell.decode() for cell in array[1]] == ["90210", "10001"]


@pytest.mark.unit
def test_rows_to_array_treats_booleans_and_nulls_as_numeric():
    array = rows_to_array(((True, None), (False, 2)))
    assert array.dtype.kind == "f"
    assert list(array[0]) == [1.0, 0.0]
    assert numpy.isnan(array[1][0])
    assert array[1][1] == 2.0


@pytest.mark.unit
def test_rows_to_array_does_not_truncate_long_labels():
    long_label = "a-really-long-cell-value-well-past-twenty-characters"
    array = rows_to_array(((long_label, "x"),))
    assert array[0][0].decode() == long_label


@pytest.mark.unit
def test_rows_to_array_accepts_non_ascii_text():
    # NumPy encodes str -> bytes as ASCII, so cells are encoded explicitly;
    # without that, a degree sign raises UnicodeEncodeError.
    array = rows_to_array((("25 °C", "naïve"),))
    assert array.dtype.kind == "S"
    assert array[0][0].decode("utf-8") == "25 °C"
    assert array[1][0].decode("utf-8") == "naïve"


@pytest.mark.unit
def test_rows_to_array_renders_none_as_empty_text():
    array = rows_to_array((("alpha", None),))
    assert array[1][0] == b""


@pytest.mark.unit
def test_rows_to_array_handles_no_rows():
    array = rows_to_array((), column_count=3)
    assert array.shape == (3, 0)


@pytest.mark.unit
def test_rows_to_array_handles_no_rows_and_no_columns():
    assert rows_to_array(()).shape == (0, 0)


# --------------------------------------------------------------------------
# column_labels / derive_axes
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_column_labels_accepts_mappings_and_strings():
    assert column_labels(COLUMNS) == ["time", "T_max", "T_min"]
    assert column_labels(["a", "b"]) == ["a", "b"]


@pytest.mark.unit
def test_derive_axes_defaults_to_first_column_then_the_rest():
    assert derive_axes(COLUMNS) == ("time", ["T_max", "T_min"])


@pytest.mark.unit
def test_derive_axes_explicit_values_win():
    assert derive_axes(COLUMNS, "T_max", ["T_min"]) == ("T_max", ["T_min"])


@pytest.mark.unit
def test_derive_axes_with_a_single_column():
    assert derive_axes(({"name": "only"},)) == ("only", [])


@pytest.mark.unit
def test_derive_axes_with_no_columns():
    assert derive_axes(()) == (None, [])


@pytest.mark.unit
def test_derive_axes_accepts_an_explicit_empty_yaxis():
    assert derive_axes(COLUMNS, None, []) == ("time", [])


# --------------------------------------------------------------------------
# flatten_tree
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_flatten_tree_recurses_to_full_depth():
    tree = (
        {
            "name": "Assembly",
            "value": "Assembly",
            "key": None,
            "children": (
                {"name": "Part A", "value": "Part A", "key": None, "children": ()},
                {
                    "name": "Part B",
                    "value": "Part B",
                    "key": None,
                    "children": (
                        {"name": "Face 1", "value": "Face 1", "key": None, "children": ()},
                    ),
                },
            ),
        },
    )
    flat = flatten_tree(tree)
    assert len(flat) == 1
    assert len(flat[0]["children"]) == 2
    assert flat[0]["children"][1]["children"][0]["name"] == "Face 1"


@pytest.mark.unit
def test_flatten_tree_carries_name_and_value():
    flat = flatten_tree(({"name": "Alpha", "value": 7, "key": None, "children": ()},))
    assert flat[0]["name"] == "Alpha"
    assert flat[0]["value"] == 7


@pytest.mark.unit
def test_flatten_tree_generates_collision_free_keys_for_duplicate_names():
    tree = (
        {
            "name": "root",
            "value": None,
            "key": None,
            "children": (
                {"name": "same", "value": None, "key": None, "children": ()},
                {"name": "same", "value": None, "key": None, "children": ()},
            ),
        },
    )
    keys = [child["key"] for child in flatten_tree(tree)[0]["children"]]
    assert len(set(keys)) == 2


@pytest.mark.unit
def test_flatten_tree_preserves_an_explicit_key():
    flat = flatten_tree(({"name": "Alpha", "value": None, "key": "custom", "children": ()},))
    assert flat[0]["key"] == "custom"


@pytest.mark.unit
def test_flatten_tree_of_nothing_is_empty():
    assert flatten_tree(()) == []


# --------------------------------------------------------------------------
# resolve_path
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_resolve_path_joins_a_relative_path_to_the_base_dir(tmp_path: Path):
    assert resolve_path("plot.png", str(tmp_path)) == str(tmp_path / "plot.png")


@pytest.mark.unit
def test_resolve_path_leaves_an_absolute_path_alone(tmp_path: Path):
    absolute = str(tmp_path / "plot.png")
    assert resolve_path(absolute, str(tmp_path / "elsewhere")) == absolute


@pytest.mark.unit
def test_resolve_path_without_a_base_dir_is_unchanged():
    assert resolve_path("plot.png") == str(Path("plot.png"))


@pytest.mark.unit
def test_resolve_path_handles_a_nested_relative_path(tmp_path: Path):
    resolved = resolve_path(os.path.join("media", "plot.png"), str(tmp_path))
    assert resolved == str(tmp_path / "media" / "plot.png")


# --------------------------------------------------------------------------
# item_content / table_fields - the values both backends feed their models
# --------------------------------------------------------------------------


def _table(**overrides):
    raw = {"item_type": "table", "name": "t", "columns": ["x", "y", "z"], "rows": [[0, 1, 2]]}
    return _model({**raw, **overrides})


@pytest.mark.unit
@pytest.mark.parametrize(("item_type", "value"), [("text", "v"), ("html", "<p>v</p>")])
def test_item_content_is_the_inline_value(item_type, value):
    assert item_content(_model({"item_type": item_type, "name": "n", "value": value})) == value


@pytest.mark.unit
def test_item_content_transposes_a_table():
    assert item_content(_table()).shape == (3, 1)


@pytest.mark.unit
def test_item_content_flattens_a_tree():
    model = _model({"item_type": "tree", "name": "t", "nodes": [{"name": "root"}]})
    assert item_content(model)[0]["name"] == "root"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("item_type", "name"),
    [("image", "a.png"), ("animation", "a.mp4"), ("scene", "a.avz"), ("file", "a.bin")],
)
def test_item_content_resolves_media_paths(item_type, name, tmp_path: Path):
    model = _model({"item_type": item_type, "name": "n", "path": name}, str(tmp_path))
    assert item_content(model) == str(tmp_path / name)


@pytest.mark.unit
def test_table_fields_derive_labels_and_axes():
    assert table_fields(_table()) == {
        "labels_row": ["x", "y", "z"],
        "xaxis": "x",
        "yaxis": ["y", "z"],
    }


@pytest.mark.unit
def test_table_fields_include_explicit_display_fields():
    fields = table_fields(_table(xaxis="y", yaxis=["z"], plot="line", format="floatdot1"))
    assert fields["xaxis"] == "y"
    assert fields["yaxis"] == ["z"]
    assert fields["plot"] == "line"
    assert fields["format"] == "floatdot1"


@pytest.mark.unit
def test_table_fields_omit_an_empty_y_axis():
    model = _model({"item_type": "table", "name": "t", "columns": ["x"], "rows": [[0]]})
    assert table_fields(model) == {"labels_row": ["x"], "xaxis": "x"}
