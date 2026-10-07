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

from ansys.dynamicreporting.core.adr_item import Item
from ansys.dynamicreporting.core.import_item_backend_server import (
    ITEM_ATTRIBUTE,
    ServerImportBackend,
)
from ansys.dynamicreporting.core.utils.json_item_import.enums import ITEM_TYPES
from ansys.dynamicreporting.core.utils.json_item_import.parser import build_document


@pytest.fixture
def service():
    """A mock Service whose create_item returns a real Item on a mocked server.

    A real Item is used so the adapter exercises ``adr_item.Item.__setattr__``
    push semantics; a bare MagicMock accepts any attribute and would hide both
    dropped metadata and redundant round trips.
    """
    mock = MagicMock()
    mock.logger = MagicMock()
    mock.serverobj.get_URL.return_value = None
    mock.create_item.side_effect = lambda obj_name=None, source=None: Item(
        service=mock, obj_name=obj_name, source=source
    )
    return mock


@pytest.fixture
def backend(service):
    return ServerImportBackend(service)


def _item(raw, base_dir=None):
    document = build_document(
        {"schema_version": "1.0", "app_id": "demo", "items": [raw]}, base_dir=base_dir
    )
    return document.items[0]


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
def test_item_source_is_forwarded_unchanged(backend, service):
    # Both backends must store the document value verbatim; an adapter-local
    # default here would diverge from the serverless adapter.
    backend.save_item(_item({"item_type": "text", "name": "n", "value": "v"}), "")
    assert service.create_item.call_args.kwargs["source"] == ""


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
    item.item.set_tags.assert_called_once_with("doc=1 a=1")


@pytest.mark.unit
def test_document_tags_are_not_applied_twice(backend):
    item = backend.save_item(_item({"item_type": "text", "name": "n", "value": "v"}), "doc=1")
    assert item.item.set_tags.call_args.args[0] == "doc=1"


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
def test_table_meta_reaches_the_pushed_payload(backend):
    # Metadata is staged after the array so that Item.__setattr__ routes it
    # into table_dict, which is what set_payload_table actually uploads.
    item = backend.save_item(_table_model(plot="line", format="floatdot1"), "")
    assert set(item.table_dict) >= {"array", "labels_row", "xaxis", "yaxis", "plot", "format"}


@pytest.mark.unit
def test_table_item_is_pushed_a_bounded_number_of_times(backend, service):
    # Item.__setattr__ re-uploads the whole table on every table_attr write
    # once the array is set. Staging the metadata, and letting sequence and
    # tags ride the payload push, keeps a table at payload + metadata.
    backend.save_item(_table_model(plot="line", format="floatdot1"), "doc=1")
    assert service.serverobj.put_objects.call_count == 2


@pytest.mark.unit
@pytest.mark.parametrize("item_type", ["text", "html", "tree"])
def test_simple_item_is_pushed_once(backend, service, item_type):
    payload = {"value": "v"} if item_type != "tree" else {"nodes": [{"name": "r"}]}
    backend.save_item(_item({"item_type": item_type, "name": "n", **payload}), "doc=1")
    assert service.serverobj.put_objects.call_count == 1


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
    model = _table_model(properties=[{"line_width": 2}])
    item = backend.save_item(model, "")
    assert item.table_dict["line_width"] == 2


@pytest.mark.unit
def test_unknown_property_is_reported_and_not_applied(backend, service):
    model = _table_model(properties=[{"not_an_adr_field": 1}])
    item = backend.save_item(model, "")
    assert "not_an_adr_field" not in item.table_dict
    assert any("not a known ADR field" in str(c) for c in service.logger.warning.call_args_list)


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_backend_exposes_no_template_entry_point(backend):
    # Report structure is imported by Service.load_templates.
    assert not hasattr(backend, "create_template")


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
