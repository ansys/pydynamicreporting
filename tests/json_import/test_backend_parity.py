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

"""Cross-backend parity.

The same document is driven through ``report_remote_server.Server`` and the
serverless ``ADR`` and the outcomes are compared. This is the gate that keeps
the two backends from drifting; it catches divergence that neither backend's
own unit tests can see.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import numpy
import pytest
import requests

from ansys.dynamicreporting.core.constants import ANIMATION_EXTENSIONS, SCENE_EXTENSIONS
from ansys.dynamicreporting.core.serverless import ADR
from ansys.dynamicreporting.core.serverless.item import (
    AnimContent,
    Item,
    SceneContent,
    TableContent,
    TreeContent,
)
from ansys.dynamicreporting.core.utils.json_item_import.importer import import_items
from ansys.dynamicreporting.core.utils.json_item_import.parser import build_document
from ansys.dynamicreporting.core.utils.json_item_import.spec import (
    ITEM_TYPE_TO_ADR_TYPE,
    ITEM_TYPES,
)
from ansys.dynamicreporting.core.utils.report_objects import ItemREST
from ansys.dynamicreporting.core.utils.report_remote_server import Server

DOCUMENT = {
    "schema_version": "1.0",
    "app_id": "parity-app",
    "tags": [{"report": "parity"}],
    "items": [
        {"item_type": "text", "name": "txt", "tags": [{"section": "intro"}], "value": "body"},
        {"item_type": "html", "name": "htm", "value": "<p>body</p>"},
        {
            "item_type": "table",
            "name": "tbl",
            "array": [[0.0, 1.0], [300.1, 320.5], [290.0, 295.2]],
            "labels_row": ["time", "T_max", "T_min"],
            "xaxis": "time",
            "yaxis": ["T_max", "T_min"],
            "plot": "line",
        },
        {
            "item_type": "tree",
            "name": "mesh",
            "nodes": [
                {
                    "key": "assembly",
                    "name": "Assembly",
                    "value": None,
                    "children": [{"key": "part", "name": "Part A", "value": 1}],
                }
            ],
        },
        {"item_type": "file", "name": "notes", "path": "notes.txt"},
    ],
}


@dataclass
class Run:
    """Everything one backend produced for the shared document."""

    result: Any
    contents: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    table_fields: dict[str, Any] = field(default_factory=dict)
    item_order: list[str] = field(default_factory=list)


def _run_serverless(base_dir: str) -> Run:
    adr = object.__new__(ADR)
    adr._logger = MagicMock()
    run = Run(result=None)
    created: dict[str, Any] = {}

    def create_item(item_class, **kwargs):
        name = kwargs["name"]
        run.item_order.append(name)
        run.contents[name] = kwargs["content"]
        run.tags[name] = kwargs["tags"]
        run.sources[name] = kwargs["source"]
        created[name] = MagicMock()
        return created[name]

    adr.create_item = create_item

    document = build_document(DOCUMENT, base_dir=base_dir)
    run.result = import_items(document, adr._populate_item)
    table = created["tbl"]
    run.table_fields = {
        key: getattr(table, key) for key in ("labels_row", "xaxis", "yaxis", "plot")
    }
    return run


def _run_server(base_dir: str) -> Run:
    server = Server()
    server._api_version = 1.0
    run = Run(result=None)

    def put_objects(objects):
        (item,) = objects
        payload = item.payloaddata if item.type != "file" else item.fileurl
        run.item_order.append(item.name)
        run.contents[item.name] = payload["array"] if item.type == "table" else payload
        run.tags[item.name] = item.get_tags()
        run.sources[item.name] = item.source
        if item.type == "table":
            run.table_fields = {
                key: payload[key] for key in ("labels_row", "xaxis", "yaxis", "plot")
            }
        return requests.codes.ok

    server.put_objects = put_objects

    document = build_document(DOCUMENT, base_dir=base_dir)
    run.result = import_items(document, server._populate_item)
    return run


@pytest.fixture
def serverless_run(tmp_path: Path) -> Run:
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
    return _run_serverless(str(tmp_path))


@pytest.fixture
def server_run(tmp_path: Path) -> Run:
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")
    return _run_server(str(tmp_path))


# --------------------------------------------------------------------------
# Static map parity
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_both_backends_cover_every_item_type():
    # The registry lookup raises KeyError for a type the serverless side lacks.
    assert all(Item._type_registry[ITEM_TYPE_TO_ADR_TYPE[item_type]] for item_type in ITEM_TYPES)
    assert set(Server._IMPORT_PAYLOAD_SETTERS) == set(ITEM_TYPE_TO_ADR_TYPE.values())


# The import leaves these extensions to the backends, so both must enforce the
# shared lists themselves.
_BACKEND_CHECKED_EXTENSIONS = {
    "animation": (ANIMATION_EXTENSIONS, AnimContent),
    "scene": (SCENE_EXTENSIONS, SceneContent),
}


def _outcome(check: Callable[[], object]) -> str:
    """Run one backend check and summarize it, keeping unexpected errors visible."""
    try:
        check()
    except ValueError as exc:
        return "rejected" if "not supported" in str(exc) else f"error: {exc}"
    return "accepted"


def _backend_outcomes(item_type: str, path: Path) -> tuple[str, str]:
    """Return how the REST setter and the serverless validator treat ``path``."""
    setter = Server._IMPORT_PAYLOAD_SETTERS[ITEM_TYPE_TO_ADR_TYPE[item_type]]
    validator = _BACKEND_CHECKED_EXTENSIONS[item_type][1]()
    item = ItemREST()
    try:
        rest = _outcome(lambda: setter(item, str(path)))
    finally:
        # The REST file setters open the payload and never close it.
        if item.fileobj is not None:
            item.fileobj.close()
    serverless = _outcome(lambda: validator.process(str(path), SimpleNamespace()))
    return rest, serverless


@pytest.mark.unit
@pytest.mark.parametrize(
    ("item_type", "name"),
    [("animation", "clip.avi"), ("animation", "clip"), ("scene", "model.png")],
)
def test_both_backends_reject_media_extensions_the_import_does_not_check(
    item_type, name, tmp_path: Path
):
    path = tmp_path / name
    path.write_bytes(b"payload")
    assert _backend_outcomes(item_type, path) == ("rejected", "rejected")


@pytest.mark.unit
@pytest.mark.parametrize("item_type", sorted(_BACKEND_CHECKED_EXTENSIONS))
def test_both_backends_accept_every_listed_media_extension(item_type, tmp_path: Path):
    extensions = _BACKEND_CHECKED_EXTENSIONS[item_type][0]
    for extension in extensions:
        path = tmp_path / f"payload.{extension.upper()}"
        path.write_bytes(b"payload")
        assert _backend_outcomes(item_type, path) == ("accepted", "accepted"), extension


def _tree_document(value: Any) -> dict[str, Any]:
    tree = {
        "item_type": "tree",
        "name": "t",
        "nodes": [{"key": "k", "name": "n", "value": value}],
    }
    return {"schema_version": "1.0", "app_id": "parity-app", "items": [tree]}


def _tree_outcomes(value: Any) -> tuple[str, str]:
    """Return how the REST and serverless tree validators treat one node ``value``."""
    tree = build_document(_tree_document(value)).items[0]["nodes"]

    def outcome(check: Callable[[], object]) -> str:
        try:
            check()
        except ValueError:
            return "rejected"
        return "accepted"

    return (
        outcome(lambda: ItemREST().set_payload_tree(tree)),
        outcome(lambda: TreeContent().process(tree, SimpleNamespace())),
    )


# The import leaves tree value types to the backends, so they must agree.
@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("text", "accepted"),
        ([1, "a", None, True], "accepted"),
        ([[1, 2], [3, [4]]], "accepted"),
        (float("nan"), "accepted"),
        ({}, "rejected"),
        ([{}], "rejected"),
        ([[{"a": 1}]], "rejected"),
    ],
    ids=["scalar", "list", "nested-lists", "nan", "object", "list-of-objects", "nested-object"],
)
def test_both_backends_agree_on_tree_values(value, expected):
    assert _tree_outcomes(value) == (expected, expected)


@pytest.mark.unit
def test_both_backends_store_the_same_source(serverless_run: Run, server_run: Run):
    # A backend-local default would make the same document produce different
    # queryable metadata on the two backends.
    assert serverless_run.sources == server_run.sources


# --------------------------------------------------------------------------
# Run-level parity
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_both_backends_report_the_same_result(serverless_run: Run, server_run: Run):
    assert serverless_run.result.items_saved == server_run.result.items_saved == 5
    assert serverless_run.result.app_id == server_run.result.app_id
    assert serverless_run.result.schema_version == server_run.result.schema_version
    assert serverless_run.result.ok and server_run.result.ok


@pytest.mark.unit
def test_both_backends_create_the_same_items_in_order(serverless_run: Run, server_run: Run):
    expected = ["txt", "htm", "tbl", "mesh", "notes"]
    assert serverless_run.item_order == server_run.item_order == expected


@pytest.mark.unit
def test_both_backends_produce_the_same_table_array(serverless_run: Run, server_run: Run):
    # The serverless create_item is mocked, so run its table validator here.
    serverless_array = TableContent().process(serverless_run.contents["tbl"], SimpleNamespace())
    server_array = server_run.contents["tbl"]
    assert serverless_array.shape == server_array.shape == (3, 2)
    assert numpy.array_equal(serverless_array, server_array)


@pytest.mark.unit
def test_both_backends_label_the_table_identically(serverless_run: Run, server_run: Run):
    assert serverless_run.table_fields == server_run.table_fields
    assert server_run.table_fields == {
        "labels_row": ["time", "T_max", "T_min"],
        "xaxis": "time",
        "yaxis": ["T_max", "T_min"],
        "plot": "line",
    }


@pytest.mark.unit
def test_both_backends_receive_the_tree_unchanged(serverless_run: Run, server_run: Run):
    expected = next(item for item in DOCUMENT["items"] if item["name"] == "mesh")["nodes"]
    assert serverless_run.contents["mesh"] == server_run.contents["mesh"] == expected


@pytest.mark.unit
def test_both_backends_merge_tags_identically(serverless_run: Run, server_run: Run):
    assert serverless_run.tags["txt"] == server_run.tags["txt"] == "report=parity section=intro"


@pytest.mark.unit
def test_both_backends_resolve_media_paths_identically(
    serverless_run: Run, server_run: Run, tmp_path: Path
):
    expected = str(tmp_path / "notes.txt")
    assert serverless_run.contents["notes"] == server_run.contents["notes"] == expected


@pytest.mark.unit
def test_both_backends_carry_the_same_inline_values(serverless_run: Run, server_run: Run):
    assert serverless_run.contents["txt"] == server_run.contents["txt"] == "body"
    assert serverless_run.contents["htm"] == server_run.contents["htm"] == "<p>body</p>"
