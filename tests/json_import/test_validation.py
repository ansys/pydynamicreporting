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

"""Validation of JSON item import documents."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.exceptions import (
    ImportItemValidationError,
    ImportItemVersionError,
)
from ansys.dynamicreporting.core.utils.json_item_import import build_document, load_document

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_a_valid_document_gets_defaults_and_warns_about_unknown_keys():
    logger = MagicMock()
    raw = {
        "app_id": "demo",
        "extra": 1,
        "items": [
            {"item_type": "text", "name": "t", "value": "v"},
            {"item_type": "html", "name": "h", "value": "<p>v</p>"},
            {"item_type": "image", "name": "i", "path": "plot.PNG"},
        ],
    }
    document = build_document(raw, base_dir=Path("runs"), logger=logger)
    assert document.schema_version == "1.0"
    assert document.items[0]["tags"] == ()
    assert document.items[0]["sequence"] == 0
    assert document.items[0]["base_dir"] == "runs"
    logger.warning.assert_called_once()


@pytest.mark.unit
def test_a_document_without_items_warns():
    logger = MagicMock()
    assert build_document({"app_id": "demo"}, logger=logger).items == ()
    assert "no items" in str(logger.warning.call_args)


@pytest.mark.unit
def test_every_problem_is_reported_in_one_pass():
    raw = {
        "app_id": "",
        "tags": [{}],
        "items": [
            {"item_type": "nope", "name": "n"},
            {"item_type": "text", "name": None, "value": 5, "sequence": True},
            {"item_type": "html", "name": "h", "value": "no tag", "tags": [{"a": [1]}]},
            {"item_type": "image", "name": "i", "path": "a.gif", "tags": [{"a": float("nan")}]},
            {"item_type": "image", "name": "i"},
            {"item_type": "tree", "name": "t", "nodes": ["not a node"]},
        ],
    }
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(raw)
    assert {location for location, _ in excinfo.value.problems} == {
        "app_id",
        "tags",
        "items[0].item_type",
        "items[1].name",
        "items[1].value",
        "items[1].sequence",
        "items[2].value",
        "items[2].tags",
        "items[3].path",
        "items[3].tags",
        "items[4].path",
        "items[5].nodes[0]",
    }
    assert "12 problems found" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.parametrize("raw", [[], {"app_id": "demo", "items": ["not an object"]}])
def test_a_document_and_its_items_must_be_objects(raw):
    with pytest.raises(ImportItemValidationError, match="1 problem found"):
        build_document(raw)


@pytest.mark.unit
def test_the_schema_version_must_have_the_supported_major():
    assert build_document({"schema_version": "1.9", "app_id": "demo"}).schema_version == "1.9"
    # The version is checked before any field, so app_id is not reported.
    with pytest.raises(ImportItemVersionError):
        build_document({"schema_version": "2.0"})


@pytest.mark.unit
def test_load_document_resolves_media_against_the_file_directory(tmp_path: Path):
    path = tmp_path / "report.json"
    # utf-8-sig: a byte order mark is accepted.
    path.write_text("\ufeff" + json.dumps({"app_id": "demo"}), encoding="utf-8")
    assert load_document(path).base_dir == str(tmp_path)
    assert load_document({"app_id": "demo"}).base_dir is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "write",
    [
        None,
        lambda path: path.mkdir(),
        lambda path: path.write_bytes(b"\xff"),
        lambda path: path.write_text("{", encoding="utf-8"),
    ],
    ids=["missing", "directory", "not-utf8", "invalid-json"],
)
def test_an_unreadable_document_is_a_validation_error(tmp_path: Path, write):
    path = tmp_path / "report.json"
    if write is not None:
        write(path)
    with pytest.raises(ImportItemValidationError):
        load_document(path)


@pytest.mark.unit
def test_the_committed_schema_and_sample_are_current():
    spec = importlib.util.spec_from_file_location(
        "gen_import_schema", REPO_ROOT / "scripts" / "gen_import_schema.py"
    )
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    committed = json.loads((REPO_ROOT / "adr_item_import.schema.json").read_text("utf-8"))
    assert generator.build_schema() == committed
    load_document(REPO_ROOT / "tests" / "test_data" / "adr_import" / "canonical_report.json")
