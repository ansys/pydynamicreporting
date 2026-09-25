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

"""Tests for the server (REST) import backend adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.import_backend_server import (
    ITEM_ATTRIBUTE,
    ServerImportBackend,
)
from ansys.dynamicreporting.core.utils.json_import.enums import (
    ITEM_TYPES,
    TEMPLATE_REPORT_TYPE,
)
from ansys.dynamicreporting.core.utils.json_import.parser import build_document


@pytest.fixture
def service():
    """A mock Service whose create_item returns an inspectable stand-in."""
    mock = MagicMock()
    mock.logger = MagicMock()
    mock.create_item.side_effect = lambda **kwargs: MagicMock(_kwargs=kwargs)
    mock.serverobj.create_template.side_effect = lambda **kwargs: MagicMock(_kwargs=kwargs)
    return mock


@pytest.fixture
def backend(service):
    return ServerImportBackend(service)


def _item(raw, base_dir=None):
    document = build_document(
        {"schema_version": "1.0", "app_id": "demo", "items": [raw]}, base_dir=base_dir
    )
    return document.items[0]


def _template(raw):
    document = build_document({"schema_version": "1.0", "app_id": "demo", "templates": [raw]})
    return document.templates[0]


_PAYLOADS = {
    "text": {"value": "body"},
    "html": {"value": "<p>body</p>"},
    "table": {"columns": ["a", "b"], "rows": [[1, 2]]},
    "tree": {"nodes": [{"name": "root"}]},
    "image": {"path": "a.png"},
    "animation": {"path": "a.mp4"},
    "scene": {"path": "a.avz"},
    "file": {"path": "a.txt"},
}


# --------------------------------------------------------------------------
# Attribute dispatch
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_attribute_map_covers_every_item_type():
    assert set(ITEM_ATTRIBUTE) == set(ITEM_TYPES)


@pytest.mark.unit
@pytest.mark.parametrize("item_type", sorted(ITEM_TYPES))
def test_every_item_type_sets_its_attribute(item_type, backend, tmp_path: Path):
    model = _item({"item_type": item_type, "name": "n", **_PAYLOADS[item_type]}, str(tmp_path))
    item = backend.save_item(model, "")
    assert getattr(item, ITEM_ATTRIBUTE[item_type]) is not None


@pytest.mark.unit
def test_text_and_html_share_the_text_attribute(backend):
    assert ITEM_ATTRIBUTE["text"] == ITEM_ATTRIBUTE["html"] == "item_text"


@pytest.mark.unit
def test_item_name_and_source_are_forwarded(backend, service):
    backend.save_item(_item({"item_type": "text", "name": "n", "value": "v", "source": "mech"}), "")
    assert service.create_item.call_args.kwargs == {"obj_name": "n", "source": "mech"}


@pytest.mark.unit
def test_item_source_defaults_to_adr(backend, service):
    backend.save_item(_item({"item_type": "text", "name": "n", "value": "v"}), "")
    assert service.create_item.call_args.kwargs["source"] == "ADR"


@pytest.mark.unit
def test_sequence_is_set_before_the_payload(backend):
    model = _item({"item_type": "text", "name": "n", "value": "v", "sequence": 4})
    item = backend.save_item(model, "")
    assert item.item.sequence == 4


@pytest.mark.unit
def test_media_paths_resolve_against_the_document_directory(backend, tmp_path: Path):
    model = _item({"item_type": "image", "name": "n", "path": "plot.png"}, str(tmp_path))
    item = backend.save_item(model, "")
    assert item.item_image == str(tmp_path / "plot.png")


# --------------------------------------------------------------------------
# Tags
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_set_tags_is_called_exactly_once(backend):
    model = _item({"item_type": "text", "name": "n", "value": "v", "tags": [{"a": "1"}]})
    item = backend.save_item(model, "doc=1")
    item.set_tags.assert_called_once_with("doc=1 a=1")


@pytest.mark.unit
def test_document_tags_are_not_applied_twice(backend):
    item = backend.save_item(_item({"item_type": "text", "name": "n", "value": "v"}), "doc=1")
    assert item.set_tags.call_args.args[0] == "doc=1"


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
def test_table_is_transposed_to_series_per_row(backend):
    item = backend.save_item(_table_model(), "")
    assert item.item_table.shape == (3, 2)


@pytest.mark.unit
def test_table_labels_row_matches_the_array_rows(backend):
    item = backend.save_item(_table_model(), "")
    assert item.labels_row == ["time", "T_max", "T_min"]
    assert len(item.labels_row) == item.item_table.shape[0]


@pytest.mark.unit
def test_table_axes_and_display_fields(backend):
    item = backend.save_item(_table_model(plot="line", format="floatdot1"), "")
    assert item.xaxis == "time"
    assert item.yaxis == ["T_max", "T_min"]
    assert item.plot == "line"
    assert item.format == "floatdot1"


@pytest.mark.unit
def test_table_meta_is_applied_after_the_array(backend):
    # labels only reach table_dict once the array has set the item type.
    model = _table_model()
    item = backend.save_item(model, "")
    assert item.item_table is not None
    assert item.labels_row is not None


# --------------------------------------------------------------------------
# Trees
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_tree_children_are_not_dropped(backend):
    model = _item(
        {
            "item_type": "tree",
            "name": "t",
            "nodes": [{"name": "root", "children": [{"name": "child"}]}],
        }
    )
    item = backend.save_item(model, "")
    assert item.item_tree[0]["children"][0]["name"] == "child"


# --------------------------------------------------------------------------
# Properties
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_properties_are_applied(backend):
    model = _item(
        {"item_type": "text", "name": "n", "value": "v", "properties": [{"text_color": "red"}]}
    )
    item = backend.save_item(model, "")
    assert item.text_color == "red"


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_template_uses_the_mapped_report_type(backend, service):
    backend.create_template(_template({"template_type": "panel", "name": "p"}))
    kwargs = service.serverobj.create_template.call_args.kwargs
    assert kwargs["report_type"] == TEMPLATE_REPORT_TYPE["panel"] == "Layout:panel"
    assert kwargs["name"] == "p"


@pytest.mark.unit
def test_root_template_is_pushed(backend, service):
    template = backend.create_template(_template({"template_type": "basic", "name": "r"}))
    service.serverobj.put_objects.assert_called_once_with([template])


@pytest.mark.unit
def test_child_template_pushes_the_parent_too(backend, service):
    parent = MagicMock()
    child = backend.create_template(_template({"template_type": "panel", "name": "c"}), parent)
    # The parent's children list changed, so it must be pushed again.
    service.serverobj.put_objects.assert_called_once_with([parent, child])


@pytest.mark.unit
def test_template_params_include_html(backend):
    template = backend.create_template(
        _template({"template_type": "basic", "name": "r", "html": '<p class="a">x</p>'})
    )
    assert template.set_params.call_args.args[0]["HTML"] == '<p class="a">x</p>'


@pytest.mark.unit
def test_template_layout_fields_use_the_layout_setters(backend):
    template = backend.create_template(
        _template(
            {
                "template_type": "basic",
                "name": "r",
                "column_count": 2,
                "column_widths": [1.0, 3.0],
            }
        )
    )
    template.set_column_count.assert_called_once_with(2)
    template.set_column_widths.assert_called_once_with([1.0, 3.0])


@pytest.mark.unit
def test_template_filter_is_passed_by_keyword(backend):
    # tablevaluefilterREST overrides set_filter with a different first
    # parameter, so a positional call would bind to the wrong argument.
    template = backend.create_template(
        _template(
            {
                "template_type": "tablemergevaluefilter",
                "name": "g",
                "item_filter": "A|i_tags|cont|x=1;",
            }
        )
    )
    template.set_filter.assert_called_once_with(filter_str="A|i_tags|cont|x=1;")


@pytest.mark.unit
def test_template_sort_and_filter_mode_are_applied(backend):
    template = backend.create_template(
        _template(
            {
                "template_type": "basic",
                "name": "r",
                "sort_selection": "last",
                "sort_fields": ["name"],
                "filter_mode": "root_append",
            }
        )
    )
    template.set_sort_selection.assert_called_once_with("last")
    template.set_sort_fields.assert_called_once_with(["name"])
    template.set_filter_mode.assert_called_once_with("root_append")


@pytest.mark.unit
def test_template_tags_are_set_when_present(backend):
    template = backend.create_template(
        _template({"template_type": "basic", "name": "r", "tags": [{"k": "v"}]})
    )
    template.set_tags.assert_called_once_with("k=v")


@pytest.mark.unit
def test_template_tags_are_skipped_when_absent(backend):
    template = backend.create_template(_template({"template_type": "basic", "name": "r"}))
    template.set_tags.assert_not_called()


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_ensure_ready_requires_a_connection():
    disconnected = MagicMock()
    disconnected.serverobj = None
    with pytest.raises(RuntimeError) as excinfo:
        ServerImportBackend(disconnected).ensure_ready()
    assert "not connected" in str(excinfo.value)


@pytest.mark.unit
def test_ensure_ready_passes_when_connected(backend):
    backend.ensure_ready()


@pytest.mark.unit
def test_backend_uses_the_service_logger(service):
    assert ServerImportBackend(service).logger is service.logger
