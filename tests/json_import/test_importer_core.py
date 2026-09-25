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

import itertools
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.utils.json_import.importer import JSONImporter
from ansys.dynamicreporting.core.utils.json_import.models import TemplatePayload
from ansys.dynamicreporting.core.utils.json_import.parser import build_document


class FakeTemplate:
    """Minimal stand-in for a created backend template."""

    _guids = itertools.count(1)

    def __init__(self, model, parent):
        self.model = model
        self.parent = parent
        self.guid = f"guid-{next(FakeTemplate._guids)}"


class FakeBackend:
    """Records every call the importer makes."""

    def __init__(self, *, fail_items=(), fail_templates=()):
        self.logger = MagicMock()
        self.ready = False
        self.templates: list[FakeTemplate] = []
        self.items: list[tuple] = []
        self._fail_items = set(fail_items)
        self._fail_templates = set(fail_templates)

    def ensure_ready(self):
        self.ready = True

    def create_template(self, model, parent):
        if model.name in self._fail_templates:
            raise RuntimeError(f"cannot create template {model.name!r}")
        template = FakeTemplate(model, parent)
        self.templates.append(template)
        return template

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
# Lifecycle and defaults
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_backend_is_made_ready_first():
    backend = FakeBackend()
    JSONImporter(backend).import_document(_document(items=[_text("a")]))
    assert backend.ready is True


@pytest.mark.unit
def test_items_only_document_gets_a_real_default_root():
    backend = FakeBackend()
    document = _document(items=[_text("a")], metadata={"producer": "demo"})
    result = JSONImporter(backend).import_document(document)

    assert result.templates_created == 1
    root = backend.templates[0].model
    # A real payload object, not a fabricated stand-in: every field an adapter
    # reads must be present.
    assert isinstance(root, TemplatePayload)
    assert root.template_type == "basic"
    assert root.name == "demo-app"
    assert root.params == {"producer": "demo"}
    assert root.html is None
    assert root.column_count is None
    assert root.sort_selection is None
    assert root.children == ()


@pytest.mark.unit
def test_default_root_exposes_every_template_field():
    backend = FakeBackend()
    JSONImporter(backend).import_document(_document(items=[_text("a")]))
    root = backend.templates[0].model
    for name in (
        "template_type",
        "name",
        "tags",
        "item_filter",
        "params",
        "html",
        "column_count",
        "column_widths",
        "sort_selection",
        "sort_fields",
        "filter_mode",
        "children",
        "extra",
    ):
        assert hasattr(root, name), name


@pytest.mark.unit
def test_document_tags_reach_the_default_root():
    backend = FakeBackend()
    JSONImporter(backend).import_document(_document(tags=[{"report": "run42"}], items=[_text("a")]))
    assert backend.templates[0].model.tags == ({"report": "run42"},)


# --------------------------------------------------------------------------
# Template recursion
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_nested_templates_are_created_to_full_depth():
    backend = FakeBackend()
    document = _document(
        templates=[
            {
                "template_type": "basic",
                "name": "root",
                "children": [
                    {
                        "template_type": "panel",
                        "name": "mid",
                        "children": [{"template_type": "box", "name": "leaf"}],
                    }
                ],
            }
        ]
    )
    result = JSONImporter(backend).import_document(document)

    assert result.templates_created == 3
    assert [t.model.name for t in backend.templates] == ["root", "mid", "leaf"]


@pytest.mark.unit
def test_nested_templates_are_created_parent_first():
    backend = FakeBackend()
    document = _document(
        templates=[
            {
                "template_type": "basic",
                "name": "root",
                "children": [{"template_type": "panel", "name": "child"}],
            }
        ]
    )
    JSONImporter(backend).import_document(document)

    root, child = backend.templates
    assert root.parent is None
    assert child.parent is root


@pytest.mark.unit
def test_multiple_roots_are_all_created():
    backend = FakeBackend()
    document = _document(
        templates=[
            {"template_type": "basic", "name": "one"},
            {
                "template_type": "basic",
                "name": "two",
                "children": [{"template_type": "panel", "name": "two-child"}],
            },
        ]
    )
    result = JSONImporter(backend).import_document(document)
    assert result.templates_created == 3
    assert len(result.root_guids) == 2


@pytest.mark.unit
def test_root_guids_are_populated():
    backend = FakeBackend()
    result = JSONImporter(backend).import_document(_document(items=[_text("a")]))
    assert result.root_guids == [backend.templates[0].guid]


@pytest.mark.unit
def test_deep_template_tree_counts_every_node():
    backend = FakeBackend()
    node = {"template_type": "box", "name": "d4"}
    for name in ("d3", "d2", "d1"):
        node = {"template_type": "panel", "name": name, "children": [node]}
    document = _document(templates=[{"template_type": "basic", "name": "d0", "children": [node]}])

    result = JSONImporter(backend).import_document(document)
    assert result.templates_created == 5


# --------------------------------------------------------------------------
# Items and tags
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_items_are_saved_with_the_document_tag_string():
    backend = FakeBackend()
    document = _document(tags=[{"report": "run42"}, {"stage": "final"}], items=[_text("a")])
    JSONImporter(backend).import_document(document)

    _, doc_tags = backend.items[0]
    assert doc_tags == "report=run42 stage=final"


@pytest.mark.unit
def test_items_are_saved_in_document_order():
    backend = FakeBackend()
    document = _document(items=[_text("a"), _text("b"), _text("c")])
    result = JSONImporter(backend).import_document(document)

    assert result.items_saved == 3
    assert [model.name for model, _ in backend.items] == ["a", "b", "c"]


@pytest.mark.unit
def test_document_without_tags_passes_an_empty_tag_string():
    backend = FakeBackend()
    JSONImporter(backend).import_document(_document(items=[_text("a")]))
    assert backend.items[0][1] == ""


# --------------------------------------------------------------------------
# Error policy
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_collect_records_failures_and_continues():
    backend = FakeBackend(fail_items={"bad"})
    document = _document(items=[_text("good"), _text("bad"), _text("also-good")])
    result = JSONImporter(backend).import_document(document, on_error="collect")

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
    result = JSONImporter(backend).import_document(_document(items=[_text("bad")]))
    assert len(result.failures) == 1


@pytest.mark.unit
def test_raise_stops_at_the_first_failure():
    backend = FakeBackend(fail_items={"bad"})
    document = _document(items=[_text("good"), _text("bad"), _text("never")])
    with pytest.raises(RuntimeError):
        JSONImporter(backend).import_document(document, on_error="raise")

    assert [model.name for model, _ in backend.items] == ["good"]


@pytest.mark.unit
def test_item_failures_are_logged_by_name():
    backend = FakeBackend(fail_items={"bad"})
    JSONImporter(backend).import_document(_document(items=[_text("bad")]))
    assert "bad" in str(backend.logger.error.call_args)


@pytest.mark.unit
def test_a_clean_import_is_ok():
    backend = FakeBackend()
    result = JSONImporter(backend).import_document(_document(items=[_text("a")]))
    assert result.ok is True
    assert result.failures == []


@pytest.mark.unit
def test_unknown_on_error_strategy_is_rejected():
    backend = FakeBackend()
    with pytest.raises(ValueError) as excinfo:
        JSONImporter(backend).import_document(_document(), on_error="ignore")
    assert "on_error" in str(excinfo.value)


@pytest.mark.unit
def test_template_failures_are_fatal_even_when_collecting():
    backend = FakeBackend(fail_templates={"root"})
    document = _document(templates=[{"template_type": "basic", "name": "root"}], items=[_text("a")])
    with pytest.raises(RuntimeError):
        JSONImporter(backend).import_document(document, on_error="collect")

    assert backend.items == []


@pytest.mark.unit
def test_a_nested_template_failure_is_also_fatal():
    backend = FakeBackend(fail_templates={"child"})
    document = _document(
        templates=[
            {
                "template_type": "basic",
                "name": "root",
                "children": [{"template_type": "panel", "name": "child"}],
            }
        ]
    )
    with pytest.raises(RuntimeError):
        JSONImporter(backend).import_document(document)


# --------------------------------------------------------------------------
# Result payload
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_result_echoes_the_document_envelope():
    backend = FakeBackend()
    result = JSONImporter(backend).import_document(_document(items=[_text("a")]))
    assert result.schema_version == "1.0"
    assert result.app_id == "demo-app"


@pytest.mark.unit
def test_empty_document_creates_only_the_default_root():
    backend = FakeBackend()
    result = JSONImporter(backend).import_document(_document())
    assert result.templates_created == 1
    assert result.items_saved == 0
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
    result = JSONImporter(backend).import_file(path)

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
    JSONImporter(backend).import_file(path)
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
        JSONImporter(backend).import_file(path, strict_keys=True)
    assert "unknown key" in str(excinfo.value)
