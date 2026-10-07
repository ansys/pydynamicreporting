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

"""Tests for the backend-agnostic importer core."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.utils.json_item_import.importer import JSONItemImporter
from ansys.dynamicreporting.core.utils.json_item_import.parser import build_document


class FakeBackend:
    """Records every call the importer makes."""

    def __init__(self, *, fail_items=()):
        self.logger = MagicMock()
        self.ready = False
        self.items: list[tuple] = []
        self._fail_items = set(fail_items)

    def ensure_ready(self):
        self.ready = True

    def save_item(self, model, doc_tags):
        if model.name in self._fail_items:
            raise RuntimeError(f"cannot save item {model.name!r}")
        self.items.append((model, doc_tags))
        return model


def _document(**overrides):
    base = {"schema_version": "1.0", "app_id": "demo-app"}
    base.update(overrides)
    return build_document(base)


def _text(name, **extra):
    return {"item_type": "text", "name": name, "value": "body", **extra}


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_backend_is_made_ready_first():
    backend = FakeBackend()
    JSONItemImporter(backend).import_document(_document(items=[_text("a")]))
    assert backend.ready is True


@pytest.mark.unit
def test_importer_creates_no_report_structure():
    # Report structure is imported by load_templates*; this contract is
    # items-only, so the backend seam exposes no template entry point.
    backend = FakeBackend()
    JSONItemImporter(backend).import_document(_document(items=[_text("a")]))
    assert not hasattr(backend, "create_template")


# --------------------------------------------------------------------------
# Items and tags
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_items_are_saved_with_the_document_tag_string():
    backend = FakeBackend()
    document = _document(tags=[{"report": "run42"}, {"stage": "final"}], items=[_text("a")])
    JSONItemImporter(backend).import_document(document)

    _, doc_tags = backend.items[0]
    assert doc_tags == "report=run42 stage=final"


@pytest.mark.unit
def test_items_are_saved_in_document_order():
    backend = FakeBackend()
    document = _document(items=[_text("a"), _text("b"), _text("c")])
    result = JSONItemImporter(backend).import_document(document)

    assert result.items_saved == 3
    assert [model.name for model, _ in backend.items] == ["a", "b", "c"]


@pytest.mark.unit
def test_document_without_tags_passes_an_empty_tag_string():
    backend = FakeBackend()
    JSONItemImporter(backend).import_document(_document(items=[_text("a")]))
    assert backend.items[0][1] == ""


# --------------------------------------------------------------------------
# Error policy
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_collect_records_failures_and_continues():
    backend = FakeBackend(fail_items={"bad"})
    document = _document(items=[_text("good"), _text("bad"), _text("also-good")])
    result = JSONItemImporter(backend).import_document(document, on_error="collect")

    assert result.items_saved == 2
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.index == 1
    assert failure.name == "bad"
    assert failure.item_type == "text"
    assert "cannot save item" in failure.error
    assert result.ok is False


@pytest.mark.unit
def test_collect_is_the_default_strategy():
    backend = FakeBackend(fail_items={"bad"})
    result = JSONItemImporter(backend).import_document(_document(items=[_text("bad")]))
    assert len(result.failures) == 1


@pytest.mark.unit
def test_raise_stops_at_the_first_failure():
    backend = FakeBackend(fail_items={"bad"})
    document = _document(items=[_text("good"), _text("bad"), _text("never")])
    with pytest.raises(RuntimeError):
        JSONItemImporter(backend).import_document(document, on_error="raise")

    assert [model.name for model, _ in backend.items] == ["good"]


@pytest.mark.unit
def test_item_failures_are_logged_by_name():
    backend = FakeBackend(fail_items={"bad"})
    JSONItemImporter(backend).import_document(_document(items=[_text("bad")]))
    assert "bad" in str(backend.logger.error.call_args)


@pytest.mark.unit
def test_a_clean_import_is_ok():
    backend = FakeBackend()
    result = JSONItemImporter(backend).import_document(_document(items=[_text("a")]))
    assert result.ok is True
    assert result.failures == []


@pytest.mark.unit
def test_unknown_on_error_strategy_is_rejected():
    backend = FakeBackend()
    with pytest.raises(ValueError) as excinfo:
        JSONItemImporter(backend).import_document(_document(), on_error="ignore")
    assert "on_error" in str(excinfo.value)


# --------------------------------------------------------------------------
# Result payload
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_result_echoes_the_document_envelope():
    backend = FakeBackend()
    result = JSONItemImporter(backend).import_document(_document(items=[_text("a")]))
    assert result.schema_version == "1.0"
    assert result.app_id == "demo-app"


@pytest.mark.unit
def test_empty_document_is_a_successful_no_op():
    backend = FakeBackend()
    result = JSONItemImporter(backend).import_document(_document())
    assert result.items_saved == 0
    assert backend.items == []
    assert result.ok is True


# --------------------------------------------------------------------------
# import_file
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_import_file_reads_validates_and_imports(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps({"schema_version": "1.0", "app_id": "demo-app", "items": [_text("a")]}),
        encoding="utf-8",
    )
    backend = FakeBackend()
    result = JSONItemImporter(backend).import_file(path)

    assert result.items_saved == 1
    assert result.app_id == "demo-app"


@pytest.mark.unit
def test_import_file_defaults_base_dir_to_the_document_directory(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "app_id": "demo-app",
                "items": [{"item_type": "image", "name": "i", "path": "a.png"}],
            }
        ),
        encoding="utf-8",
    )
    backend = FakeBackend()
    JSONItemImporter(backend).import_file(path)
    assert backend.items[0][0].base_dir == str(tmp_path)


@pytest.mark.unit
def test_import_file_forwards_base_dir_and_strict_keys(tmp_path: Path):
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps({"schema_version": "1.0", "app_id": "demo-app", "surprise": 1}),
        encoding="utf-8",
    )
    backend = FakeBackend()
    with pytest.raises(Exception) as excinfo:
        JSONItemImporter(backend).import_file(path, strict_keys=True)
    assert "unknown key" in str(excinfo.value)
