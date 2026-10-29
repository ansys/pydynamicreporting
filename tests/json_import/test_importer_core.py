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

"""Tests for the backend-agnostic ``import_items`` orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.utils.json_item_import.importer import import_items
from ansys.dynamicreporting.core.utils.json_item_import.parser import build_document


class FakeBackend:
    """Records every item the orchestration hands to the backend hook."""

    def __init__(self, *, fail_items=()):
        self.logger = MagicMock()
        self.items: list[tuple] = []
        self._fail_items = set(fail_items)

    def populate_item(self, model, doc_tags):
        if model["name"] in self._fail_items:
            raise RuntimeError(f"cannot save item {model['name']!r}")
        self.items.append((model, doc_tags))
        return model

    def run(self, document, **kwargs):
        return import_items(document, self.populate_item, logger=self.logger, **kwargs)


def _document(**overrides):
    base = {"schema_version": "1.0", "app_id": "demo-app"}
    base.update(overrides)
    return build_document(base)


def _text(name, **extra):
    return {"item_type": "text", "name": name, "value": "body", **extra}


# --------------------------------------------------------------------------
# Items and tags
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_items_are_saved_with_the_document_tag_string():
    backend = FakeBackend()
    backend.run(_document(tags=[{"report": "run42"}, {"stage": "final"}], items=[_text("a")]))

    _, doc_tags = backend.items[0]
    assert doc_tags == "report=run42 stage=final"


@pytest.mark.unit
def test_items_are_saved_in_document_order():
    backend = FakeBackend()
    result = backend.run(_document(items=[_text("a"), _text("b"), _text("c")]))

    assert result.items_saved == 3
    assert [model["name"] for model, _ in backend.items] == ["a", "b", "c"]


@pytest.mark.unit
def test_document_without_tags_passes_an_empty_tag_string():
    backend = FakeBackend()
    backend.run(_document(items=[_text("a")]))
    assert backend.items[0][1] == ""


# --------------------------------------------------------------------------
# Error policy
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_collect_records_failures_and_continues():
    backend = FakeBackend(fail_items={"bad"})
    document = _document(items=[_text("good"), _text("bad"), _text("also-good")])
    result = backend.run(document, on_error="collect")

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
    result = backend.run(_document(items=[_text("bad")]))
    assert len(result.failures) == 1


@pytest.mark.unit
def test_raise_stops_at_the_first_failure():
    backend = FakeBackend(fail_items={"bad"})
    document = _document(items=[_text("good"), _text("bad"), _text("never")])
    with pytest.raises(RuntimeError):
        backend.run(document, on_error="raise")

    assert [model["name"] for model, _ in backend.items] == ["good"]


@pytest.mark.unit
def test_item_failures_are_logged_by_name():
    backend = FakeBackend(fail_items={"bad"})
    backend.run(_document(items=[_text("bad")]))
    assert "bad" in str(backend.logger.error.call_args)


@pytest.mark.unit
def test_failures_are_collected_without_a_logger():
    backend = FakeBackend(fail_items={"bad"})
    result = import_items(_document(items=[_text("bad")]), backend.populate_item)
    assert len(result.failures) == 1


@pytest.mark.unit
def test_a_clean_import_is_ok():
    backend = FakeBackend()
    result = backend.run(_document(items=[_text("a")]))
    assert result.ok is True
    assert result.failures == []


@pytest.mark.unit
def test_unknown_on_error_strategy_is_rejected():
    backend = FakeBackend()
    with pytest.raises(ValueError) as excinfo:
        backend.run(_document(items=[_text("a")]), on_error="ignore")
    assert "on_error" in str(excinfo.value)
    assert backend.items == []


# --------------------------------------------------------------------------
# Result payload
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_result_echoes_the_document_envelope():
    backend = FakeBackend()
    result = backend.run(_document(items=[_text("a")]))
    assert result.schema_version == "1.0"
    assert result.app_id == "demo-app"


@pytest.mark.unit
def test_empty_document_is_a_successful_no_op():
    backend = FakeBackend()
    result = backend.run(_document())
    assert result.items_saved == 0
    assert backend.items == []
    assert result.ok is True
