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

"""Validation of ADR JSON item import documents.

Raw JSON is checked against the field tables in
:mod:`~ansys.dynamicreporting.core.utils.json_item_import.spec`. Every problem
found is collected and reported together, so a producer can fix a whole
document in one edit rather than one error per run.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from ...exceptions import ImportItemValidationError
from .models import ImportDocument
from .spec import (
    ANY,
    DOCUMENT_SPEC,
    ITEM_SPECS,
    ITEM_TYPES,
    FieldSpec,
    check_tags,
    check_version,
)

_Problems = list[tuple[str, str]]
"""Validation problems as ``(location, message)`` pairs, in discovery order."""

_SIMPLE_NAMES = {str: "a string", int: "an integer", list: "an array"}
"""JSON names of the field types, used in type-mismatch messages."""


def _apply_spec(
    raw: dict[str, Any],
    specs: tuple[FieldSpec, ...],
    location: str,
    errors: _Problems,
    logger: logging.Logger | None,
) -> dict[str, Any]:
    """Return the fields of ``raw`` described by ``specs``, recording problems in ``errors``.

    A missing, null, or invalid field takes its default. Unknown keys are
    ignored with a warning.
    """
    values: dict[str, Any] = {}

    for spec in specs:
        field = f"{location}.{spec.name}" if location else spec.name
        value = raw.get(spec.name)
        values[spec.name] = spec.default
        if value is None:
            # An optional field that is null counts as omitted.
            if spec.required:
                errors.append((field, "is required"))
        # bool subclasses int in Python, but JSON keeps booleans and numbers apart.
        elif not isinstance(value, spec.kind) or (
            isinstance(value, bool) and spec.kind not in (bool, ANY)
        ):
            expected = _SIMPLE_NAMES.get(spec.kind, spec.kind.__name__)
            errors.append((field, f"expected {expected}, got {type(value).__name__}"))
        elif spec.min_len is not None and len(value) < spec.min_len:
            errors.append((field, f"must have at least {spec.min_len} characters"))
        else:
            values[spec.name] = value

    if logger is not None:
        for key in raw:
            if key not in values:
                logger.warning("%s: unknown key %r is ignored.", location or "<document>", key)

    return values


def build_document(
    raw: Any,
    *,
    base_dir: str | Path | None = None,
    logger: logging.Logger | None = None,
) -> ImportDocument:
    """Validate a raw mapping and build an :class:`ImportDocument`.

    Parameters
    ----------
    raw : Any
        Decoded JSON document.
    base_dir : str or pathlib.Path, optional
        Directory that relative media paths resolve against.
        :func:`load_document` passes the directory containing the JSON file.
    logger : logging.Logger, optional
        Logger used for warnings.

    Returns
    -------
    ImportDocument
        The validated document.

    Raises
    ------
    ImportItemValidationError
        If the document violates the contract. The error carries every
        problem found during the pass.
    ImportItemVersionError
        If the declared schema version is not supported.
    """
    if not isinstance(raw, dict):
        raise ImportItemValidationError(
            [("<document>", f"expected an object, got {type(raw).__name__}")]
        )

    # Version is an envelope-level precondition: fail before anything else is
    # interpreted, because another major may redefine every field below.
    schema_version = check_version(raw.get("schema_version"))

    errors: _Problems = []
    values = _apply_spec(raw, DOCUMENT_SPEC, "", errors, logger)
    # Document tags apply to every item, so they are checked and reported here
    # once rather than as the same failure for every item. Item tags stay per-item.
    doc_tags: tuple[tuple[str, str], ...] = ()
    try:
        doc_tags = check_tags(values["tags"], "document tags")
    except (TypeError, ValueError) as exc:
        errors.append(("tags", str(exc)))

    base = None if base_dir is None else str(base_dir)
    items: list[dict[str, Any]] = []
    for index, item_raw in enumerate(values["items"]):
        location = f"items[{index}]"
        if not isinstance(item_raw, dict):
            errors.append((location, f"expected an object, got {type(item_raw).__name__}"))
            continue
        item_type = item_raw.get("item_type")
        # Tuple membership compares with ==, so an unhashable value (list, object) is safe.
        if item_type not in ITEM_TYPES:
            allowed = ", ".join(repr(name) for name in ITEM_TYPES)
            errors.append(
                (f"{location}.item_type", f"expected one of [{allowed}], got {item_type!r}")
            )
            continue
        item = _apply_spec(item_raw, ITEM_SPECS[item_type], location, errors, logger)
        items.append({**item, "base_dir": base})

    if errors:
        raise ImportItemValidationError(errors)

    if logger is not None and not items:
        logger.warning("The import document declares no items.")

    return ImportDocument(
        schema_version=schema_version,
        app_id=values["app_id"],
        tags=doc_tags,
        items=tuple(items),
    )


def load_document(
    document: str | Path | dict[str, Any],
    *,
    logger: logging.Logger | None = None,
) -> ImportDocument:
    """Validate an import document given as a JSON file path or a decoded dict.

    Relative media paths resolve against the directory containing the JSON
    file, or against the current working directory for a dict.

    Parameters
    ----------
    document : str, pathlib.Path, or dict
        Path to the JSON document, or the already-decoded document.
    logger : logging.Logger, optional
        Logger used for warnings.

    Returns
    -------
    ImportDocument
        The validated document.

    Raises
    ------
    ImportItemValidationError
        If the file cannot be read, is not UTF-8, is not valid JSON, or the
        document violates the contract.
    ImportItemVersionError
        If the declared schema version is not supported.
    """
    if isinstance(document, (str, os.PathLike)):
        try:
            # utf-8-sig also reads plain UTF-8; Windows editors routinely add a BOM.
            with open(document, encoding="utf-8-sig") as handle:
                raw = json.load(handle)
        except (OSError, ValueError) as exc:
            # OSError: missing or unreadable file. ValueError: invalid UTF-8 or JSON.
            raise ImportItemValidationError([(str(document), str(exc))]) from exc
        return build_document(raw, base_dir=Path(document).parent, logger=logger)
    return build_document(document, logger=logger)
