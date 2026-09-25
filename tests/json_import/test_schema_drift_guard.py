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

"""Drift guard.

Keeps the import contract provably a subset of the ADR data model, and keeps
the two adapters honest about sharing one mapping layer.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from ansys.dynamicreporting.core.adr_utils import table_attr
from ansys.dynamicreporting.core.import_backend_server import ITEM_ATTRIBUTE
from ansys.dynamicreporting.core.serverless import (
    HTML,
    Animation,
    File,
    Image,
    Scene,
    String,
    Table,
    Tree,
)
from ansys.dynamicreporting.core.serverless.import_backend import ITEM_CLASS, TEMPLATE_CLASS
from ansys.dynamicreporting.core.serverless.item import ItemType
from ansys.dynamicreporting.core.serverless.template import Template
from ansys.dynamicreporting.core.utils.json_import import mapping
from ansys.dynamicreporting.core.utils.json_import.enums import (
    ITEM_TYPE_TO_ADR_TYPE,
    ITEM_TYPES,
    TEMPLATE_REPORT_TYPE,
    TEMPLATE_TYPES,
)
from ansys.dynamicreporting.core.utils.json_import.spec import (
    DOCUMENT_SPEC,
    ITEM_SPECS,
    TABLE_FIELDS,
    TEMPLATE_SPEC,
    TREE_NODE_SPEC,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "adr_import.schema.json"
GENERATOR = REPO_ROOT / "scripts" / "gen_import_schema.py"

# Display fields promoted to first class; 'columns'/'rows' describe the wire
# shape rather than an ADR field, so they are not in this set.
FIRST_CLASS_TABLE_FIELDS = {"plot", "format", "xaxis", "yaxis"}

ADAPTER_SOURCES = (
    REPO_ROOT / "src" / "ansys" / "dynamicreporting" / "core" / "serverless" / "import_backend.py",
    REPO_ROOT / "src" / "ansys" / "dynamicreporting" / "core" / "import_backend_server.py",
)


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_import_schema", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Schema is a subset of the ADR data model
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_first_class_table_fields_exist_in_table_attr():
    assert FIRST_CLASS_TABLE_FIELDS <= set(table_attr)


@pytest.mark.unit
def test_table_spec_promotes_only_known_fields():
    promoted = {spec.name for spec in TABLE_FIELDS} - {"columns", "rows"}
    assert promoted == FIRST_CLASS_TABLE_FIELDS
    assert promoted <= set(table_attr)


@pytest.mark.unit
def test_labels_row_is_a_real_table_attribute():
    # The adapters write column names to labels_row.
    assert "labels_row" in table_attr


# --------------------------------------------------------------------------
# Item type maps
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_item_class_map_is_a_bijection_onto_the_backend_classes():
    expected = {String, HTML, Table, Tree, Image, Animation, Scene, File}
    assert set(ITEM_CLASS.values()) == expected
    assert len(set(ITEM_CLASS.values())) == len(ITEM_CLASS)


@pytest.mark.unit
def test_item_types_cover_every_non_none_backend_item_type():
    backend_types = {member.value for member in ItemType} - {ItemType.NONE.value}
    assert set(ITEM_TYPE_TO_ADR_TYPE.values()) == backend_types


@pytest.mark.unit
def test_item_type_translation_is_total_and_injective():
    assert set(ITEM_TYPE_TO_ADR_TYPE) == set(ITEM_TYPES)
    assert len(set(ITEM_TYPE_TO_ADR_TYPE.values())) == len(ITEM_TYPES)


@pytest.mark.unit
@pytest.mark.parametrize("item_type", sorted(ITEM_TYPES))
def test_each_item_class_declares_the_mapped_type(item_type):
    assert ITEM_CLASS[item_type].type == ITEM_TYPE_TO_ADR_TYPE[item_type]


@pytest.mark.unit
def test_both_adapters_declare_every_item_type():
    assert set(ITEM_CLASS) == set(ITEM_ATTRIBUTE) == set(ITEM_TYPES)


# --------------------------------------------------------------------------
# Template type maps
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_every_template_type_resolves_to_a_registered_report_type():
    registry = Template._type_registry
    for template_type, report_type in TEMPLATE_REPORT_TYPE.items():
        assert report_type in registry, template_type


@pytest.mark.unit
def test_template_report_types_are_unique():
    assert len(set(TEMPLATE_REPORT_TYPE.values())) == len(TEMPLATE_REPORT_TYPE)


@pytest.mark.unit
def test_template_map_covers_every_registered_layout_and_generator():
    registered = {report_type for report_type in Template._type_registry if report_type}
    assert set(TEMPLATE_REPORT_TYPE.values()) == registered


@pytest.mark.unit
@pytest.mark.parametrize("template_type", sorted(TEMPLATE_TYPES))
def test_template_class_matches_the_report_type_map(template_type):
    assert TEMPLATE_CLASS[template_type].report_type == TEMPLATE_REPORT_TYPE[template_type]


# --------------------------------------------------------------------------
# Aliases
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_every_alias_resolves_to_a_declared_field():
    tables = [DOCUMENT_SPEC, TEMPLATE_SPEC, TREE_NODE_SPEC, *ITEM_SPECS.values()]
    for specs in tables:
        names = {spec.name for spec in specs}
        for spec in specs:
            if spec.alias is not None:
                assert spec.name in names
                assert spec.alias not in names, spec.alias


# --------------------------------------------------------------------------
# Shared mapping layer
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("helper", sorted(mapping.__all__))
def test_every_shared_helper_is_used_by_both_adapters(helper):
    for source in ADAPTER_SOURCES:
        text = source.read_text(encoding="utf-8")
        assert helper in text, f"{helper} is unused in {source.name}"


@pytest.mark.unit
@pytest.mark.parametrize("source", ADAPTER_SOURCES, ids=lambda p: p.name)
def test_adapters_do_not_render_tags_locally(source: Path):
    # Tag rendering lives in json_import.tags; an inline f-string join here is
    # how the two adapters drift apart.
    text = source.read_text(encoding="utf-8")
    assert 'f"{key}={value}"' not in text
    assert "combine_tags" in text


# --------------------------------------------------------------------------
# Committed artifact
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_committed_schema_artifact_exists():
    assert ARTIFACT.is_file()


@pytest.mark.unit
def test_committed_schema_matches_regeneration():
    generated = _load_generator().build_schema()
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert generated == committed


@pytest.mark.unit
def test_schema_declares_every_item_type():
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    variants = committed["$defs"]["item"]["oneOf"]
    assert len(variants) == len(ITEM_TYPES)
    for item_type in ITEM_TYPES:
        assert {"$ref": f"#/$defs/{item_type}Item"} in variants


@pytest.mark.unit
def test_schema_requires_app_id():
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert committed["required"] == ["app_id"]


@pytest.mark.unit
def test_schema_template_enum_matches_the_wire_vocabulary():
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    enum = committed["$defs"]["template"]["properties"]["template_type"]["enum"]
    assert enum == list(TEMPLATE_TYPES)
