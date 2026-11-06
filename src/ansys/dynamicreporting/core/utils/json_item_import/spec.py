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

"""Declarative field specification for the ADR import item schema.

This module is the single source of truth for the item import contract. The
parser validates against these tables, and ``scripts/gen_import_schema.py``
renders them to the committed JSON Schema artifact. Table and tree payloads are
passed to the backend unchanged and checked by its validators when the item is
saved.

It also holds the closed wire vocabularies and the schema version helpers. It
delegates text and HTML payload validation to the existing backend validators.
Tags are passed through unchanged too; :func:`check_tags` is the check each
backend runs before it creates an item. The drift guard asserts the
vocabularies stay in sync with the backend registries.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
import re
from typing import Any

from ...adr_utils import table_attr
from ...constants import ANIMATION_EXTENSIONS, IMAGE_EXTENSIONS, SCENE_EXTENSIONS
from ...exceptions import ImportItemVersionError

# --------------------------------------------------------------------------
# Wire vocabularies
# --------------------------------------------------------------------------

ITEM_TYPE_TO_ADR_TYPE: dict[str, str] = {
    "text": "string",
    "html": "html",
    "table": "table",
    "tree": "tree",
    "image": "image",
    "animation": "anim",
    "scene": "scene",
    "file": "file",
}
"""Wire ``item_type`` to the canonical ``serverless.item.ItemType`` value.

The wire vocabulary is deliberately more readable than the stored one
(``text`` rather than ``string``, ``animation`` rather than ``anim``). This
table is the only place that translation is allowed to live; the serverless
backend resolves its :class:`Item` subclass through it.
"""

ITEM_TYPES: tuple[str, ...] = tuple(ITEM_TYPE_TO_ADR_TYPE)
"""Closed set of ``item_type`` discriminator values."""

MEDIA_EXTENSIONS: dict[str, tuple[str, ...] | None] = {
    "image": IMAGE_EXTENSIONS,
    "animation": ANIMATION_EXTENSIONS,
    "scene": SCENE_EXTENSIONS,
    "file": None,
}
"""Accepted lowercase file extensions per media ``item_type``; ``None`` accepts any.

The tuples are the ones both backends validate against when the item is saved
(``ItemREST.validate_file`` and the serverless ``FileValidator``). They are
published in the schema descriptions only.
"""

# --------------------------------------------------------------------------
# Schema version
# --------------------------------------------------------------------------

SCHEMA_VERSION = "1.0"
"""Schema version emitted and fully understood by this importer."""

SUPPORTED_MAJOR = 1
"""The only document major version this importer accepts."""

VERSION_PATTERN = rf"{SUPPORTED_MAJOR}\.[0-9]+"
"""Accepted ``schema_version`` values, shared with the JSON Schema artifact.

The format is deliberately 'MAJOR.MINOR' and not semver: a third component
would have no defined meaning for this contract.
"""


def check_version(version: Any) -> str:
    """Validate a document schema version against this importer.

    Parameters
    ----------
    version : Any
        Version declared by the document. ``None`` means :data:`SCHEMA_VERSION`.

    Returns
    -------
    str
        The resolved version string.

    Raises
    ------
    ImportItemVersionError
        If the version is not ``"<SUPPORTED_MAJOR>.<minor>"``.
    """
    if version is None:
        return SCHEMA_VERSION
    if isinstance(version, str) and re.fullmatch(VERSION_PATTERN, version):
        return version
    raise ImportItemVersionError(
        f"{version!r} is not a supported schema version; expected "
        f"'{SUPPORTED_MAJOR}.<minor>', for example '{SCHEMA_VERSION}'"
    )


# --------------------------------------------------------------------------
# Field specification
# --------------------------------------------------------------------------

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
    choices : tuple, optional
        Closed set of accepted values.
    item_kind : type or tuple of type, optional
        Element type for list-valued fields.
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
    choices: tuple[Any, ...] | None = None
    item_kind: Any = None
    min_len: int | None = None
    json_type: str | tuple[str, ...] = "string"
    json_items: dict[str, Any] | None = None
    description: str = ""

    def default_value(self) -> Any:
        """Value used when the field is absent, invalid, or an optional null."""
        return self.default_factory() if self.default_factory else self.default


# --------------------------------------------------------------------------
# Validators
# --------------------------------------------------------------------------


NON_FINITE_MESSAGE = "NaN and Infinity are not valid JSON"
"""Problem message for a non-finite tag value."""


def is_non_finite(value: Any) -> bool:
    """Whether ``value`` is a NaN or infinite float.

    Python's ``json`` accepts the ``NaN``/``Infinity`` literals, but they are
    not valid JSON and the published schema rejects them.
    """
    return isinstance(value, float) and not math.isfinite(value)


# --------------------------------------------------------------------------
# Tags
# --------------------------------------------------------------------------


_TAG_VALUE_TYPES = (str, int, float, bool)
"""Tag value types; mirrors the ``tagObject`` definition in the JSON Schema."""


def check_tags(value: Any, label: str) -> tuple[dict[str, Any], ...]:
    """Check raw tags for a backend, using ``label`` to identify invalid tags."""
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{label} must be an array, got {type(value).__name__}")
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise TypeError(f"{label} [{index}] must be an object, got {type(entry).__name__}")
        if not entry:
            raise ValueError(f"{label} [{index}] must have at least one key")
        for key, tag_value in entry.items():
            if not isinstance(tag_value, _TAG_VALUE_TYPES):
                raise ValueError(
                    f"{label} [{index}] {key!r} must be a string, number, or boolean, "
                    f"got {type(tag_value).__name__}"
                )
            if is_non_finite(tag_value):
                raise ValueError(f"{label} [{index}] {key!r}: {NON_FINITE_MESSAGE}")
        out.append(dict(entry))
    return tuple(out)


def _array(
    name: str,
    item_kind: Any,
    items: str | dict[str, Any],
    description: str,
    *,
    required: bool = False,
    default_factory: Callable[[], Any] | None = None,
) -> FieldSpec:
    """Build a JSON array field; a string ``items`` names a ``$defs`` entry."""
    return FieldSpec(
        name,
        list,
        required=required,
        default_factory=default_factory,
        item_kind=item_kind,
        json_type="array",
        json_items={"$ref": f"#/$defs/{items}"} if isinstance(items, str) else items,
        description=description,
    )


# --------------------------------------------------------------------------
# Shared field groups
# --------------------------------------------------------------------------

_TAGS = FieldSpec(
    "tags",
    ANY,
    default_factory=tuple,
    json_type="array",
    json_items={"$ref": "#/$defs/tagObject"},
    description=("Tags applied to this object. Checked by the backend when each item is created."),
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
)
ITEM_COMMON_NAMES = frozenset(spec.name for spec in ITEM_COMMON)


def _path_spec(item_type: str) -> FieldSpec:
    """Build the ``path`` field of a media item type, listing any known extensions."""
    allowed = MEDIA_EXTENSIONS[item_type]
    description = "Path to the payload file, absolute or relative to the document."
    if allowed is not None:
        listed = ", ".join(f".{extension}" for extension in allowed)
        description += f" Accepted extensions (case-insensitive): {listed}."
    return FieldSpec(
        "path",
        ANY,
        description=description + " Checked by the backend when the item is saved.",
    )


_ANY_JSON_TYPE = ("string", "number", "boolean", "null", "array", "object")

_VALUE = FieldSpec(
    "value",
    ANY,
    json_type=_ANY_JSON_TYPE,
    description="Inline text or HTML payload, checked by the backend during item creation.",
)

TABLE_PROPERTIES: tuple[str, ...] = table_attr + ("rowlbls", "collbls")
"""Table display properties passed to the backend unchanged.

The names the serverless ``Table`` stores, which the REST table payload
accepts too; the drift guard keeps them in sync.
"""

TABLE_FIELDS: tuple[FieldSpec, ...] = (
    # Kept required: REST silently substitutes [[1]] for a missing array.
    FieldSpec(
        "array",
        ANY,
        required=True,
        json_type="array",
        description=(
            "Table data as ADR stores it, one inner array per row label. Checked by the "
            "backend when the item is saved."
        ),
    ),
    FieldSpec(
        "dtype",
        ANY,
        description="NumPy dtype of the array: 'f8' (the default) for numbers or 'S' for text.",
    ),
    *(
        FieldSpec(
            name,
            ANY,
            json_type=_ANY_JSON_TYPE,
            description="ADR table property, passed to the backend unchanged.",
        )
        for name in TABLE_PROPERTIES
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
            ANY,
            json_type="array",
            json_items={"$ref": "#/$defs/treeNode"},
            description="Root nodes of the ADR tree, checked by the backend when the item is saved.",
        ),
    ),
    **{item_type: ITEM_COMMON + (_path_spec(item_type),) for item_type in MEDIA_EXTENSIONS},
}
"""Field tables keyed by ``item_type``."""

TREE_NODE_SPEC: tuple[FieldSpec, ...] = (
    FieldSpec(
        "key",
        str,
        required=True,
        description="Entity type label; not displayed and need not be unique.",
    ),
    FieldSpec("name", str, required=True, description="Text displayed in the tree view."),
    FieldSpec(
        "value",
        ANY,
        required=True,
        json_type=("string", "number", "boolean", "null", "array"),
        # Arrays may nest, as the backend tree validators accept; the
        # self-reference keeps the schema in step with them.
        json_items={"$ref": "#/$defs/treeNode/properties/value"},
        description="Node value: null, a scalar, or a possibly nested array of them.",
    ),
    _array("children", dict, "treeNode", "Child nodes."),
    FieldSpec(
        "state",
        str,
        choices=("expanded", "collapsed", "expandRecursive", "collapseRecursive"),
        description="Initial display state of the node.",
    ),
    FieldSpec(
        "header",
        bool,
        json_type="boolean",
        description="Display the node row as a header.",
    ),
)
"""Fields of an ADR tree node, used to generate the schema.

Tree nodes are complete ADR tree entities: the importer passes them to the
backend unchanged, and the backend tree validators check them when the item is
saved.
"""

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
        description="Names the producing application and groups imported content.",
    ),
    _TAGS,
    _array("items", dict, "item", "Report items to create.", default_factory=tuple),
)
