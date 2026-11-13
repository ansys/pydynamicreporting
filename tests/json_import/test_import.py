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

"""Item creation by the JSON item import on both backends."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.exceptions import ADRItemImportError, ImportItemValidationError
from ansys.dynamicreporting.core.serverless.item import Item
from ansys.dynamicreporting.core.utils.exceptions import PermissionDenied
from ansys.dynamicreporting.core.utils.json_item_import import build_document
from ansys.dynamicreporting.core.utils.json_item_import.mapping import payload_from_json
from ansys.dynamicreporting.core.utils.json_item_import.spec import ITEM_TYPE_TO_ADR_TYPE

TEST_DATA = Path(__file__).parents[1] / "test_data"

TABLE = {
    "item_type": "table",
    "name": "table",
    "array": [[0.0, 1.0], [2.0, 3.0]],
    "labels_row": ["x", "y"],
    "plot": "line",
}


def _document(*items: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    return {"schema_version": "1.0", "app_id": "demo", "items": list(items), **overrides}


def _item(raw: dict[str, Any]) -> dict[str, Any]:
    return build_document(_document(raw)).items[0]


def _every_item_type(directory: Path) -> list[dict[str, Any]]:
    """Write one payload per media type to ``directory`` and return one item per type."""
    shutil.copy(TEST_DATA / "aa_00_0_alpha1.png", directory / "a.png")
    shutil.copy(TEST_DATA / "car_crash.jpg", directory / "b.jpg")
    for name in ("a.mp4", "a.avz", "a.txt"):
        (directory / name).write_bytes(b"payload")
    return [
        {
            "item_type": "text",
            "name": "text",
            "value": "v",
            "tags": [{"section": "intro x", "report": "x"}],
        },
        {"item_type": "html", "name": "html", "value": "<p>v</p>"},
        TABLE,
        {"item_type": "tree", "name": "tree", "nodes": [{"key": "k", "name": "n", "value": 1}]},
        {"item_type": "image", "name": "png", "path": "a.png"},
        {"item_type": "image", "name": "jpg", "path": "b.jpg"},
        {"item_type": "animation", "name": "animation", "path": "a.mp4"},
        {"item_type": "scene", "name": "scene", "path": "a.avz"},
        {"item_type": "file", "name": "file", "path": "a.txt"},
    ]


def _create_with_content(item_class, **kwargs):
    """Build a serverless item without a database, so only its content validator runs."""
    item = object.__new__(item_class)
    item.content = kwargs["content"]
    return item


@pytest.mark.unit
def test_media_paths_resolve_against_the_document_directory(tmp_path: Path):
    absolute = str(tmp_path / "elsewhere" / "b.png")
    raw = _document(
        {"item_type": "image", "name": "relative", "path": "a.png"},
        {"item_type": "image", "name": "absolute", "path": absolute},
        {"item_type": "image", "name": "not-a-string", "path": 5},
    )
    relative, absolute_item, not_a_string = build_document(raw, base_dir=tmp_path).items
    assert payload_from_json(relative) == str(tmp_path / "a.png")
    assert payload_from_json(absolute_item) == absolute
    # Left for the backend file validator to report.
    assert payload_from_json(not_a_string) == 5
    # A dict document has no directory, so the path is passed as given.
    assert payload_from_json(_item({"item_type": "image", "name": "n", "path": "a.png"})) == "a.png"


@pytest.mark.unit
@pytest.mark.parametrize("item_type", ["text", "html"])
@pytest.mark.parametrize("backend", ["rest", "serverless"])
def test_string_payloads_are_checked_by_the_backend(
    rest_server, serverless_adr, item_type, backend
):
    serverless_adr.ensure_setup = MagicMock()
    serverless_adr.create_item.side_effect = _create_with_content
    server = rest_server if backend == "rest" else serverless_adr
    values = [{}, *({"value": value} for value in (None, 5, True, [], {}, "", "plain", "<p>v</p>"))]
    items = [
        {"item_type": item_type, "name": str(index), **value} for index, value in enumerate(values)
    ]
    result = server.import_items_from_json(_document(*items))
    invalid = 8 if backend == "serverless" and item_type == "html" else 6
    assert [failure.name for failure in result.failures] == [str(i) for i in range(invalid)]
    assert result.items_saved == len(items) - invalid


@pytest.mark.unit
@pytest.mark.parametrize("backend", ["rest", "serverless"])
def test_tree_table_and_image_payloads_are_checked_by_the_backend(
    rest_server, serverless_adr, backend, tmp_path: Path
):
    serverless_adr.ensure_setup = MagicMock()
    serverless_adr.create_item.side_effect = _create_with_content
    server = rest_server if backend == "rest" else serverless_adr
    gif = tmp_path / "a.gif"
    shutil.copy(TEST_DATA / "aa_00_0_alpha1.png", gif)
    items = [
        {"item_type": "tree", "name": "0"},
        {"item_type": "tree", "name": "1", "nodes": ["x"]},
        {"item_type": "table", "name": "2", "array": "x"},
        {"item_type": "table", "name": "3", "array": [[1.0]], "dtype": 5},
        {"item_type": "image", "name": "4"},
        {"item_type": "image", "name": "5", "path": str(gif)},
    ]
    result = server.import_items_from_json(_document(*items))
    assert [failure.name for failure in result.failures] == ["0", "1", "2", "3", "4", "5"]
    assert "not supported" in result.failures[-1].error


@pytest.mark.unit
@pytest.mark.parametrize("backend", ["rest", "serverless"])
def test_tags_are_checked_by_the_backend(rest_server, serverless_adr, backend):
    serverless_adr.ensure_setup = MagicMock()
    server = rest_server if backend == "rest" else serverless_adr
    invalid = (
        "a=1",
        [1],
        [{}],
        [{"a": [1]}],
        [{"a": float("nan")}],
        # Keys and values that add_tag cannot store unchanged.
        [{"": "v"}],
        [{"a=b": "v"}],
        [{"a": "x=y"}],
        [{"a": "it's"}],
        [{"a": 'say"hi'}],
        [{"a": "C:\\data"}],
        [{"a": "x\ty"}],
        [{"a": "x\ny"}],
    )
    items = [
        {"item_type": "text", "name": str(index), "value": "v", "tags": tags}
        for index, tags in enumerate((*invalid, None))
    ]
    result = server.import_items_from_json(_document(*items))
    assert [failure.name for failure in result.failures] == [str(i) for i in range(len(invalid))]
    assert result.items_saved == 1
    # An invalid document tag fails validation before any item is created.
    create = server.put_objects if backend == "rest" else server.create_item
    create.reset_mock()
    with pytest.raises(ImportItemValidationError, match="document tags"):
        server.import_items_from_json(_document(items[-1], tags=[{"k": "x=y"}]))
    create.assert_not_called()


def _create_untagged(item_class, **kwargs):
    """Build a serverless item with real tag handling and no database."""
    item = _create_with_content(item_class, **kwargs)
    item.tags = ""
    item.save = MagicMock()
    return item


@pytest.mark.unit
@pytest.mark.parametrize("backend", ["rest", "serverless"])
def test_falsy_and_boolean_tag_values_keep_their_value(rest_server, serverless_adr, backend):
    # Regression: add_tag stores a falsy value as a bare key, which dropped 0 and False.
    serverless_adr.create_item.side_effect = _create_untagged
    server = rest_server if backend == "rest" else serverless_adr
    tags = [{"rev": 0, "ratio": 0.0, "flag": False, "ok": True, "draft": "", "section": "a b"}]
    item = server._populate_item(
        _item({"item_type": "text", "name": "t", "value": "v", "tags": tags}), (("run", "0"),)
    )
    assert item.get_tags() == "run=0 rev=0 ratio=0.0 flag=False ok=True draft section='a b'"


# --------------------------------------------------------------------------
# REST server
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_rest_import_pushes_every_item_type(rest_server, tmp_path: Path):
    items = _every_item_type(tmp_path)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_document(*items, tags=[{"report": "r"}])), encoding="utf-8")

    result = rest_server.import_items_from_json(path)

    assert result.ok and result.items_saved == len(items)
    pushed = {
        call.args[0][0].name: call.args[0][0] for call in rest_server.put_objects.call_args_list
    }
    assert {name: item.type for name, item in pushed.items()} == {
        item["name"]: ITEM_TYPE_TO_ADR_TYPE[item["item_type"]] for item in items
    }
    # add_tag quotes values with spaces, and an item tag overrides a document tag.
    assert pushed["text"].get_tags() == "section='intro x' report=x"
    assert pushed["table"].payloaddata["labels_row"] == ["x", "y"]
    assert pushed["animation"].fileobj.closed


@pytest.mark.unit
def test_rest_import_collects_a_failed_item_and_continues(rest_server):
    logger = MagicMock()
    document = _document(
        {"item_type": "file", "name": "bad"}, {"item_type": "text", "name": "good", "value": "v"}
    )
    result = rest_server.import_items_from_json(document, logger=logger)
    assert result.items_saved == 1
    assert [failure.name for failure in result.failures] == ["bad"]
    logger.error.assert_called_once()


@pytest.mark.unit
def test_rest_import_on_error_strategies(rest_server):
    document = _document({"item_type": "file", "name": "bad"})
    with pytest.raises(TypeError):
        rest_server.import_items_from_json(document, on_error="raise")
    with pytest.raises(ValueError, match="on_error"):
        rest_server.import_items_from_json(document, on_error="skip")


def _mock(outcome: Any) -> MagicMock:
    if isinstance(outcome, Exception):
        return MagicMock(side_effect=outcome)
    return MagicMock(return_value=outcome)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("push", "delete", "cleanup_warns"),
    [
        (500, 200, False),
        (PermissionDenied("denied"), 404, False),
        (500, RuntimeError("down"), True),
        (500, 500, True),
    ],
    ids=["rejected", "raised", "cleanup-raises", "cleanup-rejected"],
)
def test_rest_failed_push_removes_the_partial_item(rest_server, push, delete, cleanup_warns):
    rest_server.put_objects = _mock(push)
    rest_server.del_objects = _mock(delete)
    logger = MagicMock()
    with pytest.raises((ADRItemImportError, PermissionDenied)):
        rest_server._populate_item(_item(TABLE), (), logger=logger)
    rest_server.del_objects.assert_called_once()
    assert logger.warning.called is cleanup_warns


# --------------------------------------------------------------------------
# Serverless
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_serverless_import_creates_every_item_type(serverless_adr, tmp_path: Path):
    serverless_adr.ensure_setup = MagicMock()
    items = _every_item_type(tmp_path)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_document(*items)), encoding="utf-8")

    # Relative media paths resolve against the directory holding the document.
    result = serverless_adr.import_items_from_json(path)

    assert result.ok and result.items_saved == len(items)
    created = {
        call.kwargs["name"]: call.args[0] for call in serverless_adr.create_item.call_args_list
    }
    assert created == {
        item["name"]: Item._type_registry[ITEM_TYPE_TO_ADR_TYPE[item["item_type"]]]
        for item in items
    }
    contents = {
        call.kwargs["name"]: call.kwargs["content"]
        for call in serverless_adr.create_item.call_args_list
    }
    assert contents["png"] == str(tmp_path / "a.png")
    assert contents["file"] == str(tmp_path / "a.txt")


@pytest.mark.unit
def test_serverless_table_properties_are_saved(serverless_adr):
    table = serverless_adr._populate_item(_item(TABLE), ())
    assert table.labels_row == ["x", "y"]
    table.save.assert_called_once()


@pytest.mark.unit
def test_serverless_failed_table_save_removes_the_table(serverless_adr):
    table = MagicMock()
    table.save.side_effect = RuntimeError("db down")
    serverless_adr.create_item = MagicMock(return_value=table)
    with pytest.raises(RuntimeError, match="db down"):
        serverless_adr._populate_item(_item(TABLE), ())
    table.delete.assert_called_once()
