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

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.exceptions import (
    ImportItemValidationError,
    ImportItemVersionError,
)
from ansys.dynamicreporting.core.utils.json_item_import import (
    ITEM_TYPES,
    build_document,
    load_document,
)

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
def test_a_null_optional_field_counts_as_omitted():
    nulls = {"tags": None, "source": None, "sequence": None}
    document = build_document(
        {
            "schema_version": None,
            "app_id": "demo",
            "tags": None,
            "items": [
                {"item_type": "text", "name": "t", "value": "v", **nulls},
                {"item_type": "table", "name": "a", "array": [[1.0]], "dtype": None},
            ],
        }
    )
    assert (document.schema_version, document.tags) == ("1.0", ())
    assert [document.items[0][key] for key in nulls] == [(), "", 0]
    assert document.items[1]["dtype"] is None
    assert build_document({"app_id": "demo", "items": None}).items == ()


@pytest.mark.unit
def test_document_tags_are_checked_once_into_text_pairs():
    tags = [{"run": 0, "flag": False}, {"draft": "", "section": "a b"}]
    document = build_document({"app_id": "demo", "tags": tags})
    # Values become text so add_tag keeps 0 and False instead of storing a bare key.
    assert document.tags == (("run", "0"), ("flag", "False"), ("draft", ""), ("section", "a b"))


@pytest.mark.unit
def test_every_problem_is_reported_in_one_pass():
    raw = {
        "app_id": "",
        # Document tags apply to every item, so they are a document problem.
        "tags": [{}],
        "items": [
            {"item_type": "nope", "name": "n"},
            {"item_type": "text", "name": None, "value": 5, "sequence": True},
            {"item_type": "html", "name": "h", "value": "no tag"},
            # Required here because REST silently substitutes [[1]] for a missing array.
            {"item_type": "table", "name": "t"},
        ],
    }
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(raw)
    assert {location for location, _ in excinfo.value.problems} == {
        "app_id",
        "tags",
        "items[0].item_type",
        "items[1].name",
        "items[1].sequence",
        "items[3].array",
    }
    assert "6 problems found" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.parametrize("raw", [[], {"app_id": "demo", "items": ["not an object"]}])
def test_a_document_and_its_items_must_be_objects(raw):
    with pytest.raises(ImportItemValidationError, match="1 problem found"):
        build_document(raw)


@pytest.mark.unit
def test_a_null_required_field_is_reported_like_a_missing_one():
    raw = {"app_id": None, "items": [{"item_type": "text", "value": "v"}]}
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(raw)
    assert excinfo.value.problems == (
        ("app_id", "is required"),
        ("items[0].name", "is required"),
    )


@pytest.mark.unit
def test_an_item_that_is_not_an_object_does_not_hide_other_item_problems():
    raw = {
        "app_id": "demo",
        "items": [3, {"item_type": "text", "name": "t", "value": "v", "sequence": True}],
    }
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(raw)
    assert [location for location, _ in excinfo.value.problems] == [
        "items[0]",
        "items[1].sequence",
    ]


@pytest.mark.unit
@pytest.mark.parametrize("item_type", [["text"], {"kind": "text"}, None])
def test_an_item_type_that_is_not_a_string_is_a_validation_error(item_type):
    # A list or object is unhashable, so it must not reach the item spec lookup.
    raw = {"app_id": "demo", "items": [{"item_type": item_type, "name": "n"}]}
    with pytest.raises(ImportItemValidationError) as excinfo:
        build_document(raw)
    assert [location for location, _ in excinfo.value.problems] == ["items[0].item_type"]


@pytest.mark.unit
def test_the_schema_version_must_have_the_supported_major():
    assert build_document({"schema_version": "1.9", "app_id": "demo"}).schema_version == "1.9"
    # The version is checked before any field, so app_id is not reported.
    with pytest.raises(ImportItemVersionError):
        build_document({"schema_version": "2.0"})


@pytest.mark.unit
def test_load_document_resolves_media_against_the_file_directory(tmp_path: Path):
    path = tmp_path / "report.json"
    raw = {"app_id": "demo", "items": [{"item_type": "image", "name": "i", "path": "a.png"}]}
    # utf-8-sig: a byte order mark is accepted.
    path.write_text("\ufeff" + json.dumps(raw), encoding="utf-8")
    assert load_document(path).items[0]["base_dir"] == str(tmp_path)
    # A dict has no file, so relative paths resolve against the working directory.
    assert load_document(raw).items[0]["base_dir"] is None


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
    with pytest.raises(ImportItemValidationError) as excinfo:
        load_document(path)
    [(location, message)] = excinfo.value.problems
    assert location == str(path) and message


@pytest.mark.unit
def test_the_canonical_sample_document_is_valid():
    document = load_document(
        REPO_ROOT / "tests" / "test_data" / "adr_import" / "canonical_report.json"
    )
    assert {item["item_type"] for item in document.items} == set(ITEM_TYPES)
