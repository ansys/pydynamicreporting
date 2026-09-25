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

"""Tests for the serverless import backend adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.serverless.import_backend import (
    ITEM_CLASS,
    TEMPLATE_CLASS,
    ServerlessImportBackend,
)
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
from ansys.dynamicreporting.core.utils.json_import.parser import build_document


@pytest.fixture
def adr():
    """A mock ADR whose creation APIs return inspectable stand-ins."""
    mock = MagicMock()
    mock._logger = MagicMock()
    mock.create_item.side_effect = lambda item_class, **kwargs: MagicMock(
        name=f"item::{item_class.__name__}", _item_class=item_class, _kwargs=kwargs
    )
    mock.create_template.side_effect = lambda template_class, **kwargs: MagicMock(
        name=f"template::{template_class.__name__}",
        _template_class=template_class,
        _kwargs=kwargs,
    )
    return mock


@pytest.fixture
def backend(adr):
    return ServerlessImportBackend(adr)


def _item(raw, base_dir=None):
    """Build a single ItemPayload from a raw item mapping."""
    document = build_document(
        {"schema_version": "1.0", "app_id": "demo", "items": [raw]}, base_dir=base_dir
    )
    return document.items[0]


def _template(raw):
    document = build_document({"schema_version": "1.0", "app_id": "demo", "templates": [raw]})
    return document.templates[0]


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
def test_template_class_map_has_no_duplicate_classes():
    assert len(set(TEMPLATE_CLASS.values())) == len(TEMPLATE_CLASS)


@pytest.mark.unit
@pytest.mark.parametrize("item_type", sorted(ITEM_CLASS))
def test_every_item_type_dispatches_to_its_class(item_type, backend, adr, tmp_path: Path):
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
    backend.save_item(model, "")

    assert adr.create_item.call_args.args[0] is ITEM_CLASS[item_type]


# --------------------------------------------------------------------------
# Items
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_text_content_is_the_inline_value(backend, adr):
    backend.save_item(_item({"item_type": "text", "name": "n", "value": "body"}), "")
    assert adr.create_item.call_args.kwargs["content"] == "body"


@pytest.mark.unit
def test_source_and_sequence_are_forwarded(backend, adr):
    model = _item({"item_type": "text", "name": "n", "value": "v", "source": "mech", "sequence": 7})
    backend.save_item(model, "")
    kwargs = adr.create_item.call_args.kwargs
    assert kwargs["source"] == "mech"
    assert kwargs["sequence"] == 7


@pytest.mark.unit
def test_document_and_item_tags_are_merged(backend, adr):
    model = _item({"item_type": "text", "name": "n", "value": "v", "tags": [{"section": "intro"}]})
    backend.save_item(model, "report=run42")
    assert adr.create_item.call_args.kwargs["tags"] == "report=run42 section=intro"


@pytest.mark.unit
def test_media_paths_resolve_against_the_document_directory(backend, adr, tmp_path: Path):
    model = _item({"item_type": "image", "name": "n", "path": "plot.png"}, str(tmp_path))
    backend.save_item(model, "")
    assert adr.create_item.call_args.kwargs["content"] == str(tmp_path / "plot.png")


@pytest.mark.unit
def test_absolute_media_paths_are_left_alone(backend, adr, tmp_path: Path):
    absolute = str(tmp_path / "plot.png")
    model = _item({"item_type": "image", "name": "n", "path": absolute}, str(tmp_path / "other"))
    backend.save_item(model, "")
    assert adr.create_item.call_args.kwargs["content"] == absolute


@pytest.mark.unit
def test_tree_content_is_flattened_recursively(backend, adr):
    model = _item(
        {
            "item_type": "tree",
            "name": "t",
            "nodes": [{"name": "root", "children": [{"name": "child"}]}],
        }
    )
    backend.save_item(model, "")
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
def test_table_content_is_transposed_to_series_per_row(backend, adr):
    backend.save_item(_table_model(), "")
    array = adr.create_item.call_args.kwargs["content"]
    assert array.shape == (3, 2)


@pytest.mark.unit
def test_table_labels_row_matches_the_array_rows(backend, adr):
    item = backend.save_item(_table_model(), "")
    array = adr.create_item.call_args.kwargs["content"]
    assert item.labels_row == ["time", "T_max", "T_min"]
    assert len(item.labels_row) == array.shape[0]


@pytest.mark.unit
def test_table_axes_are_derived_from_the_columns(backend):
    item = backend.save_item(_table_model(), "")
    assert item.xaxis == "time"
    assert item.yaxis == ["T_max", "T_min"]


@pytest.mark.unit
def test_table_explicit_axes_win(backend):
    item = backend.save_item(_table_model(xaxis="T_max", yaxis=["T_min"]), "")
    assert item.xaxis == "T_max"
    assert item.yaxis == ["T_min"]


@pytest.mark.unit
def test_table_display_fields_are_applied(backend):
    item = backend.save_item(_table_model(plot="line", format="floatdot1"), "")
    assert item.plot == "line"
    assert item.format == "floatdot1"


@pytest.mark.unit
def test_table_is_saved_once_after_its_metadata(backend):
    item = backend.save_item(_table_model(), "")
    item.save.assert_called_once()


@pytest.mark.unit
def test_simple_item_is_not_saved_a_second_time(backend):
    item = backend.save_item(_item({"item_type": "text", "name": "n", "value": "v"}), "")
    item.save.assert_not_called()


@pytest.mark.unit
def test_item_with_properties_is_saved_once(backend):
    model = _item(
        {"item_type": "text", "name": "n", "value": "v", "properties": [{"text_color": "red"}]}
    )
    item = backend.save_item(model, "")
    item.save.assert_called_once()


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_template_dispatches_to_its_class(backend, adr):
    backend.create_template(_template({"template_type": "panel", "name": "p"}))
    assert adr.create_template.call_args.args[0] is TEMPLATE_CLASS["panel"]


@pytest.mark.unit
def test_template_name_parent_and_tags_are_forwarded(backend, adr):
    parent = object()
    backend.create_template(
        _template({"template_type": "basic", "name": "r", "tags": [{"k": "v"}]}), parent
    )
    kwargs = adr.create_template.call_args.kwargs
    assert kwargs["name"] == "r"
    assert kwargs["parent"] is parent
    assert kwargs["tags"] == "k=v"


@pytest.mark.unit
def test_template_params_are_set_through_the_public_api(backend):
    template = backend.create_template(
        _template({"template_type": "basic", "name": "r", "params": {"custom": 1}})
    )
    template.set_params.assert_called_once_with({"custom": 1})


@pytest.mark.unit
def test_template_html_is_merged_into_params(backend):
    template = backend.create_template(
        _template({"template_type": "basic", "name": "r", "html": "<h1>Hi</h1>"})
    )
    template.set_params.assert_called_once_with({"HTML": "<h1>Hi</h1>"})


@pytest.mark.unit
def test_template_html_containing_quotes_survives_intact(backend):
    html = "<div class=\"wide\" data-x='1'>A \\ B</div>"
    template = backend.create_template(
        _template({"template_type": "basic", "name": "r", "html": html})
    )
    # Params go through set_params (json.dumps) rather than string formatting,
    # so quotes and backslashes cannot corrupt the payload.
    assert template.set_params.call_args.args[0]["HTML"] == html


@pytest.mark.unit
def test_template_layout_fields_use_the_layout_setters(backend):
    template = backend.create_template(
        _template(
            {
                "template_type": "basic",
                "name": "r",
                "column_count": 3,
                "column_widths": [1.0, 2.0],
            }
        )
    )
    template.set_column_count.assert_called_once_with(3)
    template.set_column_widths.assert_called_once_with([1.0, 2.0])


@pytest.mark.unit
def test_template_filter_and_sort_fields_are_applied(backend):
    template = backend.create_template(
        _template(
            {
                "template_type": "basic",
                "name": "r",
                "item_filter": "A|i_tags|cont|section=results;",
                "sort_selection": "first",
                "sort_fields": ["name"],
                "filter_mode": "items",
            }
        )
    )
    template.set_filter.assert_called_once_with(filter_str="A|i_tags|cont|section=results;")
    template.set_sort_selection.assert_called_once_with("first")
    template.set_sort_fields.assert_called_once_with(["name"])
    template.set_filter_mode.assert_called_once_with("items")


@pytest.mark.unit
def test_template_optional_setters_are_skipped_when_absent(backend):
    template = backend.create_template(_template({"template_type": "basic", "name": "r"}))
    template.set_column_count.assert_not_called()
    template.set_column_widths.assert_not_called()
    template.set_filter.assert_not_called()
    template.set_sort_selection.assert_not_called()
    template.set_filter_mode.assert_not_called()


@pytest.mark.unit
def test_template_is_saved(backend):
    template = backend.create_template(_template({"template_type": "basic", "name": "r"}))
    template.save.assert_called_once()


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_ensure_ready_delegates_to_adr(backend, adr):
    backend.ensure_ready()
    adr.ensure_setup.assert_called_once()


@pytest.mark.unit
def test_backend_reuses_the_adr_logger(adr):
    assert ServerlessImportBackend(adr).logger is adr._logger


@pytest.mark.unit
def test_backend_falls_back_to_a_module_logger():
    bare = MagicMock()
    bare._logger = None
    assert ServerlessImportBackend(bare).logger is not None
