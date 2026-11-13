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

"""Field tables and shared checks for the ADR item import contract.

The parser validates documents against these tables. Payloads (text, HTML,
table, tree, media) are passed to the backend unchanged and checked by its
validators when the item is saved.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from ...adr_utils import table_attr
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

# --------------------------------------------------------------------------
# Schema version
# --------------------------------------------------------------------------

SCHEMA_VERSION = "1.0"
"""Schema version emitted and fully understood by this importer."""

SUPPORTED_MAJOR = 1
"""The only document major version this importer accepts."""

VERSION_PATTERN = rf"{SUPPORTED_MAJOR}\.[0-9]+"
"""Accepted ``schema_version`` values.

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
    kind : type
        Python type the value must have after ``json.load``. Use :data:`ANY`
        to accept any JSON value.
    required : bool, default: False
        Whether the field must be present and non-null.
    default : Any, optional
        Value used when the field is absent, null, or invalid. Shared by every
        document, so it must be immutable.
    min_len : int, optional
        Minimum length for string fields.
    """

    name: str
    kind: Any
    required: bool = False
    default: Any = None
    min_len: int | None = None


# --------------------------------------------------------------------------
# Tags
# --------------------------------------------------------------------------

# ADR stores tags as one shlex-split "key=value" string, and both backends'
# add_tag only quote text containing a space. These characters therefore cannot
# round-trip: "=" truncates the value, quotes break parsing of the whole tag
# string, a backslash is dropped, and a tab or line break splits the token.
_TAG_FORBIDDEN_CLASS = r"""='"\\\t\r\n"""

TAG_KEY_PATTERN = f"^[^{_TAG_FORBIDDEN_CLASS}]+$"
"""Accepted tag keys: non-empty, without ``=``, quotes, backslashes, tabs, or line breaks."""

TAG_VALUE_PATTERN = f"^[^{_TAG_FORBIDDEN_CLASS}]*$"
"""Accepted string tag values; an empty string is stored as a bare key."""

_TAG_TEXT_RULE = "must not contain '=', quotes, backslashes, tabs, or line breaks"


def check_tags(value: Any, label: str) -> tuple[tuple[str, str], ...]:
    """Check raw tags and return their ``(key, value)`` pairs for ``add_tag``.

    ``label`` identifies the tags in error messages. Values are returned as
    text, the way ``add_tag`` renders them, because ``add_tag`` stores any
    falsy value as a bare key: ``0`` and ``False`` keep their value as ``"0"``
    and ``"False"``, while ``""`` still becomes a bare key.
    """
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{label} must be an array, got {type(value).__name__}")
    out: list[tuple[str, str]] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise TypeError(f"{label} [{index}] must be an object, got {type(entry).__name__}")
        if not entry:
            raise ValueError(f"{label} [{index}] must have at least one key")
        for key, tag_value in entry.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"{label} [{index}] key {key!r} must be a string, got {type(key).__name__}"
                )
            if not key:
                raise ValueError(f"{label} [{index}] has an empty key")
            if not re.fullmatch(TAG_KEY_PATTERN, key):
                raise ValueError(f"{label} [{index}] key {key!r} {_TAG_TEXT_RULE}")
            if not isinstance(tag_value, (str, int, float, bool)):
                raise ValueError(
                    f"{label} [{index}] {key!r} must be a string, number, or boolean, "
                    f"got {type(tag_value).__name__}"
                )
            # Python's json accepts NaN and Infinity, but they are not valid JSON.
            if isinstance(tag_value, float) and not math.isfinite(tag_value):
                raise ValueError(f"{label} [{index}] {key!r}: NaN and Infinity are not valid JSON")
            if isinstance(tag_value, str) and not re.fullmatch(TAG_VALUE_PATTERN, tag_value):
                raise ValueError(f"{label} [{index}] {key!r} value {_TAG_TEXT_RULE}")
            out.append((key, str(tag_value)))
    return tuple(out)


# --------------------------------------------------------------------------
# Field tables
# --------------------------------------------------------------------------

# Checked by check_tags: document tags once by the parser, item tags by each backend.
_TAGS = FieldSpec("tags", ANY, default=())

ITEM_COMMON: tuple[FieldSpec, ...] = (
    FieldSpec("item_type", str, required=True),
    FieldSpec("name", str, required=True, min_len=1),
    _TAGS,
    FieldSpec("source", str, default=""),
    FieldSpec("sequence", int, default=0),
)

TABLE_PROPERTIES: tuple[str, ...] = table_attr + ("rowlbls", "collbls")
"""Table display properties passed to the backend unchanged.

The names the serverless ``Table`` stores, which the REST table payload
accepts too.
"""

# Payload fields accept any value: the backend checks them when the item is saved.
_VALUE = FieldSpec("value", ANY)
_PATH = FieldSpec("path", ANY)

ITEM_SPECS: dict[str, tuple[FieldSpec, ...]] = {
    "text": ITEM_COMMON + (_VALUE,),
    "html": ITEM_COMMON + (_VALUE,),
    "table": ITEM_COMMON
    + (
        # Kept required: REST silently substitutes [[1]] for a missing array.
        FieldSpec("array", ANY, required=True),
        FieldSpec("dtype", ANY),
        *(FieldSpec(name, ANY) for name in TABLE_PROPERTIES),
    ),
    "tree": ITEM_COMMON + (FieldSpec("nodes", ANY),),
    "image": ITEM_COMMON + (_PATH,),
    "animation": ITEM_COMMON + (_PATH,),
    "scene": ITEM_COMMON + (_PATH,),
    "file": ITEM_COMMON + (_PATH,),
}
"""Field tables keyed by ``item_type``."""

DOCUMENT_SPEC: tuple[FieldSpec, ...] = (
    FieldSpec("schema_version", str, default=SCHEMA_VERSION),
    FieldSpec("app_id", str, required=True, min_len=1),
    _TAGS,
    FieldSpec("items", list, default=()),
)
