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

"""Declarative field specification for the ADR import schema.

This module is the single source of truth for the import contract. The
parser validates against these tables, and ``scripts/gen_import_schema.py``
renders them to the committed JSON Schema artifact, so the two cannot drift.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .enums import FILTER_MODES, ITEM_TYPES, SORT_SELECTIONS, TEMPLATE_TYPES
from .models import TableColumn
from .version import SCHEMA_VERSION

ANY = object
"""Sentinel :attr:`FieldSpec.kind` meaning 'any JSON value'."""


@dataclass(frozen=True)
class FieldSpec:
    """Declarative description of one field in the import contract.

    Parameters
    ----------
    name : str
        Canonical wire name.
    kind : type or tuple of type
        Python type(s) the value may have after ``json.load``. Use
        :data:`ANY` to accept any JSON value.
    required : bool, default: False
        Whether the field must be present and non-null.
    default : Any, optional
        Value used when the field is absent.
    default_factory : callable, optional
        Called to build the default. Takes precedence over ``default``.
    alias : str, optional
        Deprecated wire name also accepted for this field.
    choices : tuple, optional
        Closed set of accepted values.
    item_kind : type or tuple of type, optional
        Element type for list-valued fields.
    coerce : callable, optional
        Normalizes an accepted value. Raises :class:`ValueError` with a
        user-facing message when the value cannot be normalized.
    validate : callable, optional
        Returns an error message, or ``None`` when the value is acceptable.
    min_len : int, optional
        Minimum length for strings and lists.
    json_type : str or tuple of str
        JSON Schema ``type`` for this field.
    json_items : dict, optional
        JSON Schema ``items`` subschema for array fields.
    description : str
        Human-readable description emitted into the JSON Schema.
    """

    name: str
    kind: Any
    required: bool = False
    default: Any = None
    default_factory: Callable[[], Any] | None = None
    alias: str | None = None
    choices: tuple[Any, ...] | None = None
    item_kind: Any = None
    coerce: Callable[[Any], Any] | None = None
    validate: Callable[[Any], str | None] | None = None
    min_len: int | None = None
    json_type: str | tuple[str, ...] = "string"
    json_items: dict[str, Any] | None = None
    description: str = ""


# --------------------------------------------------------------------------
# Coercers
# --------------------------------------------------------------------------


def coerce_tag_list(value: Any) -> tuple[dict[str, Any], ...]:
    """Normalize tags to the canonical list-of-objects form."""
    if isinstance(value, dict):
        return (dict(value),)
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(value):
        if isinstance(entry, dict):
            out.append(dict(entry))
        elif isinstance(entry, str):
            key, sep, val = entry.partition("=")
            if not sep:
                raise ValueError(
                    f"tag [{index}] {entry!r} is not a 'key=value' string or an object"
                )
            out.append({key: val})
        else:
            raise ValueError(
                f"tag [{index}] must be an object or a 'key=value' string, "
                f"got {type(entry).__name__}"
            )
    return tuple(out)


def coerce_columns(value: Any) -> tuple[TableColumn, ...]:
    """Normalize table columns to :class:`TableColumn` objects."""
    out: list[TableColumn] = []
    for index, entry in enumerate(value):
        if isinstance(entry, str):
            out.append(TableColumn(name=entry))
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"column [{index}] requires a non-empty string 'name'")
        col_type = entry.get("type", "string")
        if not isinstance(col_type, str):
            raise ValueError(f"column [{index}] 'type' must be a string")
        out.append(TableColumn(name=name, type=col_type))
    return tuple(out)


def coerce_rows(value: Any) -> tuple[tuple[Any, ...], ...]:
    """Freeze table rows. Shape and cell types are checked by the parser."""
    return tuple(tuple(row) for row in value)


def coerce_dict_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    """Freeze a list of objects."""
    return tuple(dict(entry) for entry in value)


def coerce_str_tuple(value: Any) -> tuple[str, ...]:
    """Freeze a list of strings."""
    return tuple(value)


def coerce_number_tuple(value: Any) -> tuple[float, ...]:
    """Freeze a list of numbers as floats."""
    return tuple(float(entry) for entry in value)


def positive_int(value: Any) -> str | None:
    """Reject non-positive integers."""
    if value <= 0:
        return "must be greater than 0"
    return None


# --------------------------------------------------------------------------
# Shared field groups
# --------------------------------------------------------------------------

_TAGS = FieldSpec(
    "tags",
    (list, dict),
    default_factory=tuple,
    coerce=coerce_tag_list,
    json_type="array",
    json_items={"$ref": "#/$defs/tagObject"},
    description="Tags applied to this object.",
)

ITEM_COMMON: tuple[FieldSpec, ...] = (
    FieldSpec(
        "item_type",
        str,
        required=True,
        choices=ITEM_TYPES,
        description="Discriminator selecting the item payload type.",
    ),
    FieldSpec("name", str, required=True, min_len=1, description="Item name."),
    _TAGS,
    FieldSpec("source", str, default="", description="Producing application or component."),
    FieldSpec(
        "sequence",
        int,
        default=0,
        json_type="integer",
        description="Ordering hint within a report.",
    ),
    FieldSpec(
        "properties",
        list,
        default_factory=tuple,
        item_kind=dict,
        coerce=coerce_dict_tuple,
        json_type="array",
        json_items={"$ref": "#/$defs/propertyObject"},
        description="Escape hatch for ADR fields not promoted to first class.",
    ),
)

# Declared once and shared by all four media types. Duplicating the 'src'
# alias per type is how the contract drifts.
_PATH = FieldSpec(
    "path",
    str,
    required=True,
    min_len=1,
    alias="src",
    description="Path to the payload file, absolute or relative to the document.",
)

_VALUE = FieldSpec("value", str, required=True, description="Inline payload body.")

TABLE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "columns",
        list,
        required=True,
        item_kind=(str, dict),
        coerce=coerce_columns,
        json_type="array",
        json_items={"$ref": "#/$defs/tableColumn"},
        description="Column definitions, in wire (record) order.",
    ),
    FieldSpec(
        "rows",
        list,
        required=True,
        item_kind=list,
        coerce=coerce_rows,
        json_type="array",
        json_items={
            "type": "array",
            "items": {"type": ["string", "number", "boolean", "null"]},
        },
        description="Record-oriented rows; one inner list per record.",
    ),
    FieldSpec("plot", str, description="Plot style, for example 'line'."),
    FieldSpec("format", str, description="Cell value format."),
    FieldSpec("xaxis", str, description="Explicit x-axis label; must name a column."),
    FieldSpec(
        "yaxis",
        list,
        item_kind=str,
        coerce=coerce_str_tuple,
        json_type="array",
        json_items={"type": "string"},
        description="Explicit y-axis labels; each must name a column.",
    ),
)

ITEM_SPECS: dict[str, tuple[FieldSpec, ...]] = {
    "text": ITEM_COMMON + (_VALUE,),
    "html": ITEM_COMMON + (_VALUE,),
    "table": ITEM_COMMON + TABLE_FIELDS,
    "tree": ITEM_COMMON
    + (
        FieldSpec(
            "nodes",
            list,
            required=True,
            item_kind=dict,
            json_type="array",
            json_items={"$ref": "#/$defs/treeNode"},
            description="Root nodes of the tree.",
        ),
    ),
    "image": ITEM_COMMON + (_PATH,),
    "animation": ITEM_COMMON + (_PATH,),
    "scene": ITEM_COMMON + (_PATH,),
    "file": ITEM_COMMON + (_PATH,),
}
"""Field tables keyed by ``item_type``."""

COMMON_ITEM_NAMES: frozenset[str] = frozenset(spec.name for spec in ITEM_COMMON)
"""Names handled by :class:`~...models.ItemPayload` itself rather than ``payload``."""

TREE_NODE_SPEC: tuple[FieldSpec, ...] = (
    FieldSpec("name", str, required=True, min_len=1, description="Node label."),
    FieldSpec("key", str, description="Stable node key; generated when absent."),
    FieldSpec(
        "value",
        ANY,
        json_type=("string", "number", "boolean", "null", "array"),
        description="Node value. Defaults to the node name.",
    ),
    FieldSpec(
        "children",
        list,
        default_factory=tuple,
        item_kind=dict,
        json_type="array",
        json_items={"$ref": "#/$defs/treeNode"},
        description="Child nodes.",
    ),
)

TEMPLATE_SPEC: tuple[FieldSpec, ...] = (
    FieldSpec(
        "template_type",
        str,
        required=True,
        choices=TEMPLATE_TYPES,
        description="Discriminator selecting the ADR report type.",
    ),
    FieldSpec("name", str, required=True, min_len=1, description="Template name."),
    _TAGS,
    FieldSpec("item_filter", str, description="ADR query expression selecting items."),
    FieldSpec(
        "params",
        dict,
        default_factory=dict,
        json_type="object",
        description="Raw template parameters merged with the convenience fields.",
    ),
    FieldSpec("html", str, description="Layout HTML, stored as params['HTML']."),
    FieldSpec(
        "column_count",
        int,
        json_type="integer",
        validate=positive_int,
        description="Layout column count.",
    ),
    FieldSpec(
        "column_widths",
        list,
        item_kind=(int, float),
        coerce=coerce_number_tuple,
        json_type="array",
        json_items={"type": "number"},
        description="Layout column width factors.",
    ),
    FieldSpec(
        "sort_selection",
        str,
        choices=SORT_SELECTIONS,
        description="Which items to keep after sorting.",
    ),
    FieldSpec(
        "sort_fields",
        list,
        item_kind=str,
        coerce=coerce_str_tuple,
        json_type="array",
        json_items={"type": "string"},
        description="Fields used to sort items.",
    ),
    FieldSpec(
        "filter_mode", str, choices=FILTER_MODES, description="How the item filter is applied."
    ),
    FieldSpec(
        "children",
        list,
        default_factory=tuple,
        item_kind=dict,
        json_type="array",
        json_items={"$ref": "#/$defs/template"},
        description="Child templates, built parent-first.",
    ),
)

SESSION_SPEC: tuple[FieldSpec, ...] = (
    FieldSpec("name", str, description="Session name."),
    _TAGS,
    FieldSpec("application", str, description="Producing application."),
    FieldSpec("hostname", str, description="Host that produced the session."),
)

DATASET_SPEC: tuple[FieldSpec, ...] = (
    FieldSpec("name", str, description="Dataset name."),
    _TAGS,
    FieldSpec("filename", str, description="Source file name."),
    FieldSpec("format", str, description="Source file format."),
)

DOCUMENT_SPEC: tuple[FieldSpec, ...] = (
    FieldSpec(
        "schema_version",
        str,
        default=SCHEMA_VERSION,
        description="Import schema version, 'MAJOR.MINOR'.",
    ),
    FieldSpec(
        "app_id",
        str,
        required=True,
        min_len=1,
        description="Names the generated root report and groups imported content.",
    ),
    _TAGS,
    FieldSpec(
        "metadata",
        dict,
        default_factory=dict,
        json_type="object",
        description="Free-form producer metadata, stored on the root template params.",
    ),
    FieldSpec(
        "sessions",
        list,
        default_factory=tuple,
        item_kind=dict,
        json_type="array",
        json_items={"$ref": "#/$defs/session"},
        description="Accepted and retained in v1.0, but not applied to created items.",
    ),
    FieldSpec(
        "datasets",
        list,
        default_factory=tuple,
        item_kind=dict,
        json_type="array",
        json_items={"$ref": "#/$defs/dataset"},
        description="Accepted and retained in v1.0, but not applied to created items.",
    ),
    FieldSpec(
        "items",
        list,
        default_factory=tuple,
        item_kind=dict,
        json_type="array",
        json_items={"$ref": "#/$defs/item"},
        description="Report items to create.",
    ),
    FieldSpec(
        "templates",
        list,
        default_factory=tuple,
        item_kind=dict,
        json_type="array",
        json_items={"$ref": "#/$defs/template"},
        description="Report structure to create.",
    ),
)
