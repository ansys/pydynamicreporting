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
from unittest.mock import MagicMock

import numpy
import pytest

from ansys.dynamicreporting.core.utils.json_import.mapping import (
    apply_properties,
    column_labels,
    derive_axes,
    flatten_tree,
    resolve_path,
    rows_to_array,
)
from ansys.dynamicreporting.core.utils.json_import.models import TableColumn, TreeNode

COLUMNS = (TableColumn("time"), TableColumn("T_max"), TableColumn("T_min"))


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
def test_rows_to_array_does_not_truncate_long_labels():
    long_label = "a-really-long-cell-value-well-past-twenty-characters"
    array = rows_to_array(((long_label, "x"),))
    assert array[0][0].decode() == long_label


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
def test_column_labels_accepts_objects_and_strings():
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
    assert derive_axes((TableColumn("only"),)) == ("only", [])


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
        TreeNode(
            name="Assembly",
            value="Assembly",
            children=(
                TreeNode(name="Part A", value="Part A"),
                TreeNode(
                    name="Part B",
                    value="Part B",
                    children=(TreeNode(name="Face 1", value="Face 1"),),
                ),
            ),
        ),
    )
    flat = flatten_tree(tree)
    assert len(flat) == 1
    assert len(flat[0]["children"]) == 2
    assert flat[0]["children"][1]["children"][0]["name"] == "Face 1"


@pytest.mark.unit
def test_flatten_tree_carries_name_and_value():
    flat = flatten_tree((TreeNode(name="Alpha", value=7),))
    assert flat[0]["name"] == "Alpha"
    assert flat[0]["value"] == 7


@pytest.mark.unit
def test_flatten_tree_generates_collision_free_keys_for_duplicate_names():
    tree = (
        TreeNode(
            name="root",
            children=(TreeNode(name="same"), TreeNode(name="same")),
        ),
    )
    keys = [child["key"] for child in flatten_tree(tree)[0]["children"]]
    assert len(set(keys)) == 2


@pytest.mark.unit
def test_flatten_tree_preserves_an_explicit_key():
    flat = flatten_tree((TreeNode(name="Alpha", key="custom"),))
    assert flat[0]["key"] == "custom"


@pytest.mark.unit
def test_flatten_tree_of_nothing_is_empty():
    assert flatten_tree(()) == []


# --------------------------------------------------------------------------
# apply_properties
# --------------------------------------------------------------------------


class _Target:
    """Stand-in item exposing a method, a property, and free attributes."""

    def __init__(self):
        self.name = "target"
        self.line_width = None
        self.table_title = None
        self._private = None

    def save(self):  # pragma: no cover - only used as a shadowing target
        raise AssertionError("save must never be overwritten by a property")

    @property
    def plot(self):
        return self._plot

    @plot.setter
    def plot(self, value):
        self._plot = value


@pytest.mark.unit
def test_apply_properties_sets_public_fields():
    target = _Target()
    apply_properties(target, [{"line_width": 2}, {"table_title": "Probe"}])
    assert target.line_width == 2
    assert target.table_title == "Probe"


@pytest.mark.unit
def test_apply_properties_allows_properties():
    target = _Target()
    apply_properties(target, [{"plot": "line"}])
    assert target.plot == "line"


@pytest.mark.unit
def test_apply_properties_refuses_to_shadow_a_method():
    target = _Target()
    logger = MagicMock()
    apply_properties(target, [{"save": "oops"}], logger)
    assert callable(target.save)
    assert any("shadow a method" in str(call) for call in logger.warning.call_args_list)


@pytest.mark.unit
def test_apply_properties_skips_private_keys():
    target = _Target()
    logger = MagicMock()
    apply_properties(target, [{"_private": "oops"}], logger)
    assert target._private is None
    logger.warning.assert_called_once()


@pytest.mark.unit
def test_apply_properties_skips_non_string_keys():
    target = _Target()
    logger = MagicMock()
    apply_properties(target, [{7: "oops"}], logger)
    logger.warning.assert_called_once()


@pytest.mark.unit
def test_apply_properties_logs_by_name_not_index():
    target = _Target()
    logger = MagicMock()
    apply_properties(target, [{"save": 1}], logger)
    assert "target" in str(logger.warning.call_args)


@pytest.mark.unit
def test_apply_properties_of_nothing_is_a_noop():
    target = _Target()
    apply_properties(target, ())
    apply_properties(target, None)
    assert target.line_width is None


@pytest.mark.unit
def test_apply_properties_without_a_logger_is_silent():
    target = _Target()
    apply_properties(target, [{"save": 1}, {"_x": 2}])
    assert callable(target.save)


@pytest.mark.unit
def test_apply_properties_later_entries_win():
    target = _Target()
    apply_properties(target, [{"line_width": 1}, {"line_width": 9}])
    assert target.line_width == 9


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
