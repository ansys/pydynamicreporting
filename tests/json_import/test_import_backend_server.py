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
from ansys.dynamicreporting.core.utils.json_import.enums import ITEM_TYPES
from ansys.dynamicreporting.core.utils.json_import.parser import build_document


@pytest.fixture
def service():
    """A mock Service whose create_item returns an inspectable stand-in."""
    mock = MagicMock()
    mock.logger = MagicMock()
    mock.create_item.side_effect = lambda **kwargs: MagicMock(_kwargs=kwargs)
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
