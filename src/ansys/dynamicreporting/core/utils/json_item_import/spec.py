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
renders them to the committed JSON Schema artifact. The parser additionally
enforces the cross-field rules JSON Schema cannot express, such as equal row
widths and axis names that match a column.

It also holds the closed wire vocabularies and the schema version helpers. It
must not import any backend module, so that the import core stays
backend-agnostic; the drift guard asserts the vocabularies stay in sync with
the backend registries.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
import math
from pathlib import PurePath
import re
from typing import Any

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
    "image": ("png", "jpg", "tif", "tiff"),
    "animation": ("mp4",),
    "scene": ("stl", "ply", "csf", "avz", "scdoc", "scdocx", "dsco", "glb", "obj"),
    "file": None,
}
"""Accepted lowercase file extensions per media ``item_type``; ``None`` accepts any.

Copied from the serverless content validators, which are the strictest
backend, because importing them would load Django. The drift guard asserts
these stay equal to the serverless ``ALLOWED_EXT`` tuples and to the lists the
REST payload setters accept.
"""

# --------------------------------------------------------------------------
# Schema version
# --------------------------------------------------------------------------

SCHEMA_VERSION = "1.0"
"""Schema version emitted and fully understood by this importer."""

SUPPORTED_MAJOR = 1
"""Highest document major version this importer accepts."""

# The format is deliberately 'MAJOR.MINOR' and not semver: a third component
# would have no defined meaning for this contract, so it is rejected instead of
# being silently ignored.
_VERSION_RE = re.compile(r"([0-9]+)\.([0-9]+)")


def parse_version(version: str) -> tuple[int, int]:
    """Parse a ``"MAJOR.MINOR"`` schema version string.

    Parameters
    ----------
    version : str
        Version string, for example ``"1.3"``.

    Returns
    -------
    tuple of (int, int)
        The major and minor components.

    Raises
    ------
    ImportItemVersionError
        If ``version`` is not exactly two dot-separated integers.
    """
    if not isinstance(version, str):
        raise ImportItemVersionError(
            f"expected a 'MAJOR.MINOR' version string, got {type(version).__name__}"
        )
    match = _VERSION_RE.fullmatch(version)
    if match is None:
        raise ImportItemVersionError(
            f"{version!r} is not a valid schema version; expected 'MAJOR.MINOR', for example '1.0'"
        )
    return int(match.group(1)), int(match.group(2))


def check_version(version: str | None, logger: object | None = None) -> str:
    """Validate a document schema version against this importer.

    Parameters
    ----------
    version : str or None
        Version declared by the document. ``None`` is treated as
        :data:`SCHEMA_VERSION` with a logged warning.
    logger : object, optional
        Logger used for the missing-version warning and the
        forward-compatibility note.

    Returns
    -------
    str
        The resolved version string.

    Raises
    ------
    ImportItemVersionError
        If the version is malformed or its major exceeds
        :data:`SUPPORTED_MAJOR`.
    """
    if version is None:
        if logger is not None:
            logger.warning(
                "No 'schema_version' in the import document; assuming %s.", SCHEMA_VERSION
            )
        return SCHEMA_VERSION

    major, minor = parse_version(version)
    if major > SUPPORTED_MAJOR:
        raise ImportItemVersionError(
            f"document major version {major} is newer than the supported major "
            f"{SUPPORTED_MAJOR}; upgrade ansys-dynamicreporting-core to import it"
        )

    supported_major, supported_minor = parse_version(SCHEMA_VERSION)
    if major == supported_major and minor > supported_minor and logger is not None:
        logger.info(
            "Import document declares schema version %s, newer than the supported %s; "
            "unrecognized fields are retained but not interpreted.",
            version,
            SCHEMA_VERSION,
        )
    return version


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
    choices: tuple[Any, ...] | None = None
    item_kind: Any = None
    coerce: Callable[[Any], Any] | None = None
    validate: Callable[[Any], str | None] | None = None
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


NON_FINITE_MESSAGE = "NaN and Infinity are not valid JSON; use null for a missing number"
"""Problem message for a non-finite number anywhere in a document."""


def is_non_finite(value: Any) -> bool:
    """Whether ``value`` is a NaN or infinite float.

    Python's ``json`` accepts the ``NaN``/``Infinity`` literals, but they are
    not valid JSON and the published schema rejects them.
    """
    return isinstance(value, float) and not math.isfinite(value)


class _TagDetector(HTMLParser):
    """Records whether at least one start tag was seen."""

    def __init__(self) -> None:
        super().__init__()
        self.found = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.found = True


def validate_html(value: str) -> str | None:
    """Require at least one HTML tag.

    Mirrors the serverless ``HTMLContent`` validator, so an ``html`` item that
    the serverless backend would reject fails validation for both backends.
    """
    detector = _TagDetector()
    detector.feed(value)
    return None if detector.found else "must contain at least one HTML tag"


def _extension_validator(allowed: tuple[str, ...]) -> Callable[[str], str | None]:
    """Build a ``path`` validator that accepts only the ``allowed`` extensions."""
    listed = ", ".join(f"'.{extension}'" for extension in allowed)

    def _validate(path: str) -> str | None:
        extension = PurePath(path).suffix.lower().lstrip(".")
        if extension in allowed:
            return None
        found = f"'.{extension}'" if extension else "no extension"
        return f"file type {found} is not supported; expected one of [{listed}]"

    return _validate


# --------------------------------------------------------------------------
# Coercers
# --------------------------------------------------------------------------


_TAG_VALUE_TYPES = (str, int, float, bool)
"""Tag value types; mirrors the ``tagObject`` definition in the JSON Schema."""


def coerce_tag_list(value: Any) -> tuple[dict[str, Any], ...]:
    """Freeze tag objects, rejecting empty objects and non-scalar or non-finite values."""
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(value):
        if not entry:
            raise ValueError(f"tag [{index}] must have at least one key")
        for key, tag_value in entry.items():
            if not isinstance(tag_value, _TAG_VALUE_TYPES):
                raise ValueError(
                    f"tag [{index}] {key!r} must be a string, number, or boolean, "
                    f"got {type(tag_value).__name__}"
                )
            if is_non_finite(tag_value):
                raise ValueError(f"tag [{index}] {key!r}: {NON_FINITE_MESSAGE}")
        out.append(dict(entry))
    return tuple(out)


def coerce_columns(value: Any) -> tuple[dict[str, str], ...]:
    """Normalize table columns to objects with a name and optional type."""
    out: list[dict[str, str]] = []
    for index, entry in enumerate(value):
        if isinstance(entry, str):
            out.append({"name": entry, "type": "string"})
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"column [{index}] requires a non-empty string 'name'")
        col_type = entry.get("type", "string")
        if not isinstance(col_type, str):
            raise ValueError(f"column [{index}] 'type' must be a string")
        out.append({"name": name, "type": col_type})
    return tuple(out)


def coerce_rows(value: Any) -> tuple[tuple[Any, ...], ...]:
    """Freeze table rows. Shape and cell types are checked by the parser."""
    return tuple(tuple(row) for row in value)


def coerce_dict_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    """Freeze a list of objects."""
    return tuple(dict(entry) for entry in value)


def _array(
    name: str,
    item_kind: Any,
    items: str | dict[str, Any],
    description: str,
    *,
    required: bool = False,
    default_factory: Callable[[], Any] | None = None,
    coerce: Callable[[Any], Any] | None = None,
) -> FieldSpec:
    """Build a JSON array field; a string ``items`` names a ``$defs`` entry."""
    return FieldSpec(
        name,
        list,
        required=required,
        default_factory=default_factory,
        item_kind=item_kind,
        coerce=coerce,
        json_type="array",
        json_items={"$ref": f"#/$defs/{items}"} if isinstance(items, str) else items,
        description=description,
    )


_NOT_APPLIED = "Accepted and retained in v1.0, but not applied to created items."


# --------------------------------------------------------------------------
# Shared field groups
# --------------------------------------------------------------------------

_TAGS = _array(
    "tags",
    dict,
    "tagObject",
    "Tags applied to this object.",
    default_factory=tuple,
    coerce=coerce_tag_list,
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
    _array(
        "properties",
        dict,
        "propertyObject",
        "Escape hatch for table fields not promoted to first class. "
        "Ignored with a warning on other item types.",
        default_factory=tuple,
        coerce=coerce_dict_tuple,
    ),
)
ITEM_COMMON_NAMES = frozenset(spec.name for spec in ITEM_COMMON)


def _path_spec(item_type: str) -> FieldSpec:
    """Build the ``path`` field of a media item type, with its extension check."""
    allowed = MEDIA_EXTENSIONS[item_type]
    description = "Path to the payload file, absolute or relative to the document."
    if allowed is not None:
        listed = ", ".join(f".{extension}" for extension in allowed)
        description += f" Accepted extensions (case-insensitive): {listed}."
    return FieldSpec(
        "path",
        str,
        required=True,
        min_len=1,
        validate=_extension_validator(allowed) if allowed is not None else None,
        description=description,
    )


_VALUE = FieldSpec("value", str, required=True, description="Inline payload body.")

_HTML_VALUE = FieldSpec(
    "value",
    str,
    required=True,
    validate=validate_html,
    description="Inline HTML body; must contain at least one HTML tag.",
)

TABLE_FIELDS: tuple[FieldSpec, ...] = (
    _array(
        "columns",
        (str, dict),
        "tableColumn",
        "Column definitions, in wire (record) order.",
        required=True,
        coerce=coerce_columns,
    ),
    _array(
        "rows",
        list,
        {"type": "array", "items": {"type": ["string", "number", "boolean", "null"]}},
        "Record-oriented rows; one inner list per record.",
        required=True,
        coerce=coerce_rows,
    ),
    FieldSpec("plot", str, description="Plot style, for example 'line'."),
    FieldSpec("format", str, description="Cell value format."),
    FieldSpec("xaxis", str, description="Explicit x-axis label; must name a column."),
    _array(
        "yaxis",
        str,
        {"type": "string"},
        "Explicit y-axis labels; each must name a column.",
        coerce=tuple,
    ),
)

ITEM_SPECS: dict[str, tuple[FieldSpec, ...]] = {
    "text": ITEM_COMMON + (_VALUE,),
    "html": ITEM_COMMON + (_HTML_VALUE,),
    "table": ITEM_COMMON + TABLE_FIELDS,
    "tree": ITEM_COMMON
    + (_array("nodes", dict, "treeNode", "Root nodes of the tree.", required=True),),
    **{item_type: ITEM_COMMON + (_path_spec(item_type),) for item_type in MEDIA_EXTENSIONS},
}
"""Field tables keyed by ``item_type``."""

TREE_NODE_SPEC: tuple[FieldSpec, ...] = (
    FieldSpec("name", str, required=True, min_len=1, description="Node label."),
    FieldSpec("key", str, description="Stable node key; generated when absent."),
    FieldSpec(
        "value",
        ANY,
        json_type=("string", "number", "boolean", "null", "array"),
        json_items={"type": ["string", "number", "boolean", "null"]},
        description="Node value. Defaults to the node name.",
    ),
    _array("children", dict, "treeNode", "Child nodes.", default_factory=tuple),
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
        description="Names the producing application and groups imported content.",
    ),
    _TAGS,
    FieldSpec(
        "metadata",
        dict,
        default_factory=dict,
        json_type="object",
        description="Free-form producer metadata. Retained but not interpreted.",
    ),
    _array("sessions", dict, "session", _NOT_APPLIED, default_factory=tuple),
    _array("datasets", dict, "dataset", _NOT_APPLIED, default_factory=tuple),
    _array("items", dict, "item", "Report items to create.", default_factory=tuple),
)
