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

import pytest

from ansys.dynamicreporting.core.adr_utils import table_attr
from ansys.dynamicreporting.core.utils.json_item_import.mapping import (
    item_content,
    resolve_path,
    table_fields,
)
from tests.json_import.helpers import build_item as _model


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
    raw = {"item_type": "table", "name": "t", "array": [[0, 1, 2]]}
    return _model({**raw, **overrides})


@pytest.mark.unit
@pytest.mark.parametrize(("item_type", "value"), [("text", "v"), ("html", "<p>v</p>")])
def test_item_content_is_the_inline_value(item_type, value):
    assert item_content(_model({"item_type": item_type, "name": "n", "value": value})) == value


@pytest.mark.unit
def test_item_content_of_a_table_is_its_array_as_given():
    model = _table()
    content = item_content(model)
    # An omitted dtype stays omitted, so each backend applies its own default.
    assert content == {"array": [[0, 1, 2]]}
    assert content["array"] is model["array"]


@pytest.mark.unit
def test_item_content_of_a_table_carries_an_explicit_dtype():
    assert item_content(_table(dtype="S")) == {"array": [[0, 1, 2]], "dtype": "S"}


@pytest.mark.unit
def test_item_content_is_the_tree_as_given():
    nodes = [{"key": "k", "name": "root", "value": None}]
    model = _model({"item_type": "tree", "name": "t", "nodes": nodes})
    assert item_content(model) is model["nodes"]
    assert item_content(model) == nodes


@pytest.mark.unit
@pytest.mark.parametrize(
    ("item_type", "name"),
    [("image", "a.png"), ("animation", "a.mp4"), ("scene", "a.avz"), ("file", "a.bin")],
)
def test_item_content_resolves_media_paths(item_type, name, tmp_path: Path):
    model = _model({"item_type": item_type, "name": "n", "path": name}, str(tmp_path))
    assert item_content(model) == str(tmp_path / name)


@pytest.mark.unit
def test_table_fields_are_empty_when_none_are_given():
    assert table_fields(_table()) == {}


@pytest.mark.unit
def test_table_fields_pass_every_given_property_through_unchanged():
    given = {"labels_row": ["x"], "xaxis": "x", "line_color": ["red"], "rowlbls": ["r"]}
    assert table_fields(_table(**given)) == given


@pytest.mark.unit
def test_table_fields_cover_every_adr_table_property():
    given = {name: f"value-{name}" for name in table_attr}
    assert table_fields(_table(**given)) == given
