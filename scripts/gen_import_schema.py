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

"""Render the declarative field spec to the committed JSON Schema artifact.

Run via ``make schema``. CI regenerates and diffs the result, so the schema
and the parser cannot drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ansys.dynamicreporting.core.utils.json_import.enums import (
    FILTER_MODES,
    ITEM_TYPES,
    SORT_SELECTIONS,
    TEMPLATE_TYPES,
)
from ansys.dynamicreporting.core.utils.json_import.spec import (
    DATASET_SPEC,
    DOCUMENT_SPEC,
    ITEM_SPECS,
    SESSION_SPEC,
    TEMPLATE_SPEC,
    TREE_NODE_SPEC,
    FieldSpec,
)
from ansys.dynamicreporting.core.utils.json_import.version import SCHEMA_VERSION

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "adr_import.schema.json"

SCHEMA_ID = f"https://schemas.ansys.com/adr/import/{SCHEMA_VERSION}/adr-import.schema.json"

# Item fields carried by every type; the per-type tables extend this.
_COMMON_ITEM_NAMES = {"item_type", "name", "tags", "source", "sequence", "properties"}


def _field_schema(spec: FieldSpec) -> dict[str, Any]:
    """Render one :class:`FieldSpec` as a JSON Schema property."""
    schema: dict[str, Any] = (
        {"type": list(spec.json_type)}
        if isinstance(spec.json_type, tuple)
        else {"type": spec.json_type}
    )
    if spec.json_items is not None:
        schema["items"] = spec.json_items
    if spec.choices is not None:
        schema["enum"] = list(spec.choices)
    if spec.min_len is not None:
        schema["minLength" if spec.json_type == "string" else "minItems"] = spec.min_len
    if spec.name == "column_count":
        schema["minimum"] = 1
    if spec.name == "schema_version":
        schema["pattern"] = r"^[0-9]+\.[0-9]+$"
        schema["default"] = SCHEMA_VERSION
    if spec.description:
        schema["description"] = spec.description
    return schema


def _object_schema(
    specs: tuple[FieldSpec, ...],
    *,
    skip: set[str] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Render a field table as a JSON Schema object."""
    skip = skip or set()
    overrides = overrides or {}
    properties: dict[str, Any] = {}
    required: list[str] = []
    for spec in specs:
        if spec.name in skip:
            continue
        properties[spec.name] = overrides.get(spec.name) or _field_schema(spec)
        if spec.required:
            required.append(spec.name)
    schema: dict[str, Any] = {"type": "object", "additionalProperties": True}
    if required:
        schema["required"] = required
    schema["properties"] = properties
    return schema


def _item_variant(item_type: str) -> dict[str, Any]:
    """Render one item type as an ``allOf`` extension of the shared base."""
    specific = tuple(spec for spec in ITEM_SPECS[item_type] if spec.name not in _COMMON_ITEM_NAMES)
    extension = _object_schema(specific)
    extension["properties"]["item_type"] = {"const": item_type}
    extension.setdefault("required", [])
    extension["required"] = ["item_type", *extension.get("required", [])]
    extension.pop("additionalProperties", None)
    extension.pop("type", None)
    return {"allOf": [{"$ref": "#/$defs/itemBase"}, extension]}


def build_schema() -> dict[str, Any]:
    """Build the full JSON Schema document from the field tables."""
    document = _object_schema(DOCUMENT_SPEC)
    defs: dict[str, Any] = {
        "tagObject": {
            "type": "object",
            "minProperties": 1,
            "additionalProperties": {"type": ["string", "number", "boolean"]},
        },
        "propertyObject": {
            "type": "object",
            "minProperties": 1,
            "additionalProperties": {
                "type": ["string", "number", "boolean", "null", "array", "object"]
            },
        },
        "tableColumn": {
            "oneOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                    },
                },
            ]
        },
        "session": _object_schema(SESSION_SPEC),
        "dataset": _object_schema(DATASET_SPEC),
        "treeNode": _object_schema(TREE_NODE_SPEC),
        "template": _object_schema(TEMPLATE_SPEC),
        "itemBase": _object_schema(
            tuple(spec for spec in ITEM_SPECS["text"] if spec.name in _COMMON_ITEM_NAMES),
            overrides={"item_type": {"type": "string"}},
        ),
    }
    for item_type in ITEM_TYPES:
        defs[f"{item_type}Item"] = _item_variant(item_type)
    defs["item"] = {"oneOf": [{"$ref": f"#/$defs/{name}Item"} for name in ITEM_TYPES]}

    # Enum vocabularies are rendered from the same tables the parser uses.
    defs["template"]["properties"]["template_type"]["enum"] = list(TEMPLATE_TYPES)
    defs["template"]["properties"]["sort_selection"]["enum"] = list(SORT_SELECTIONS)
    defs["template"]["properties"]["filter_mode"]["enum"] = list(FILTER_MODES)

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "ADR Item Import Document",
        **document,
        "$defs": defs,
    }


def main() -> None:
    """Write the schema artifact to the repository root."""
    payload = build_schema()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
