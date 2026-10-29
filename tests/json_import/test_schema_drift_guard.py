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
the two backends honest about sharing one mapping layer.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import re

import pytest

from ansys.dynamicreporting.core.adr_utils import table_attr
from ansys.dynamicreporting.core.serverless import (
    ADR,
    HTML,
    Animation,
    File,
    Image,
    Scene,
    String,
    Table,
    Tree,
)
from ansys.dynamicreporting.core.serverless.item import (
    AnimContent,
    FileContent,
    HTMLParser,
    ImageContent,
    ItemType,
    SceneContent,
)
from ansys.dynamicreporting.core.utils.json_item_import.parser import load_document
from ansys.dynamicreporting.core.utils.json_item_import.spec import (
    ITEM_TYPE_TO_ADR_TYPE,
    ITEM_TYPES,
    MEDIA_EXTENSIONS,
    SCHEMA_VERSION,
    TABLE_FIELDS,
    validate_html,
)
from ansys.dynamicreporting.core.utils.report_objects import ItemREST
from ansys.dynamicreporting.core.utils.report_remote_server import Server

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "adr_item_import.schema.json"
GENERATOR = REPO_ROOT / "scripts" / "gen_import_schema.py"
SAMPLE = REPO_ROOT / "tests" / "test_data" / "adr_import" / "canonical_report.json"

# Display fields promoted to first class; 'columns'/'rows' describe the wire
# shape rather than an ADR field, so they are not in this set.
FIRST_CLASS_TABLE_FIELDS = {"plot", "format", "xaxis", "yaxis"}

ITEM_CLASS = {item_type: ADR._import_item_class(item_type) for item_type in ITEM_TYPES}

# The per-item hooks each backend hands to import_items, like the
# create_template_func each backend hands to populate_template.
POPULATE_HOOKS = (Server._populate_item, ADR._populate_item)

# The mapping helpers both hooks must call instead of inlining their own copy.
SHARED_HELPERS = ("item_content", "table_fields", "apply_properties", "combine_tags")


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
def test_both_backends_declare_every_item_type():
    assert set(ITEM_CLASS) == set(Server._IMPORT_PAYLOAD_SETTERS) == set(ITEM_TYPES)


# --------------------------------------------------------------------------
# Validation mirrors the serverless content validators
# --------------------------------------------------------------------------

SERVERLESS_MEDIA_VALIDATORS = {
    "image": ImageContent,
    "animation": AnimContent,
    "scene": SceneContent,
    "file": FileContent,
}


@pytest.mark.unit
def test_media_extensions_cover_exactly_the_media_item_types():
    assert set(MEDIA_EXTENSIONS) == set(SERVERLESS_MEDIA_VALIDATORS)


@pytest.mark.unit
@pytest.mark.parametrize("item_type", sorted(SERVERLESS_MEDIA_VALIDATORS))
def test_media_extensions_match_the_serverless_validators(item_type):
    assert MEDIA_EXTENSIONS[item_type] == SERVERLESS_MEDIA_VALIDATORS[item_type].ALLOWED_EXT


@pytest.mark.unit
@pytest.mark.parametrize(
    ("setter", "item_type"),
    [("set_payload_animation", "animation"), ("set_payload_scene", "scene")],
)
def test_media_extensions_match_the_rest_payload_setters(setter, item_type, tmp_path: Path):
    bad = tmp_path / "payload.unsupported"
    bad.write_bytes(b"payload")
    allowed = list(MEDIA_EXTENSIONS[item_type])
    with pytest.raises(ValueError, match=re.escape(f"Allowed types: {allowed}")):
        getattr(ItemREST(), setter)(str(bad))


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    ["<p>x</p>", "<br/>", "text <b>bold</b>", "plain text", "a < b", "<p", "", "</p>"],
)
def test_html_validation_agrees_with_the_serverless_parser(value):
    assert (validate_html(value) is None) is HTMLParser().validate(value)


# --------------------------------------------------------------------------
# Shared mapping layer
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("helper", SHARED_HELPERS)
@pytest.mark.parametrize("hook", POPULATE_HOOKS, ids=lambda f: f.__qualname__)
def test_every_shared_helper_is_used_by_both_backends(hook, helper):
    assert helper in inspect.getsource(hook), f"{helper} is unused in {hook.__qualname__}"


@pytest.mark.unit
@pytest.mark.parametrize("hook", POPULATE_HOOKS, ids=lambda f: f.__qualname__)
def test_backends_do_not_render_tags_locally(hook):
    # Tag rendering lives in json_item_import.mapping; an inline f-string join here is
    # how the two backends drift apart.
    assert 'f"{key}={value}"' not in inspect.getsource(hook)


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
def test_schema_declares_no_report_structure():
    # Report structure is imported by load_templates*, not by this contract.
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert "template" not in committed["$defs"]
    assert "templates" not in committed["properties"]


# --------------------------------------------------------------------------
# Committed sample document
#
# The sample is validated against the committed schema by the check-jsonschema
# pre-commit hook. These tests cover the other half: that the parser accepts
# it, and that it stays a complete example.
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_sample_document_exists():
    assert SAMPLE.is_file()


@pytest.mark.unit
def test_parser_accepts_the_sample_document():
    document = load_document(SAMPLE)
    assert document.app_id
    assert document.schema_version == SCHEMA_VERSION


@pytest.mark.unit
def test_sample_document_demonstrates_every_item_type():
    document = load_document(SAMPLE)
    assert {item["item_type"] for item in document.items} == set(ITEM_TYPES)


@pytest.mark.unit
def test_sample_document_has_no_unknown_keys():
    # An unknown key here would still validate, but it would be teaching a
    # misspelling to anyone who copies the sample.
    document = load_document(SAMPLE)
    assert document.extra == {}
    assert all(item["extra"] == {} for item in document.items)
