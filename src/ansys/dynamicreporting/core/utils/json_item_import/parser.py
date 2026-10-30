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

"""Validation and construction of ADR import item documents.

The parser walks the declarative tables in
:mod:`~ansys.dynamicreporting.core.utils.json_item_import.spec` and turns raw JSON
into normalized item mappings. The backend adapters pass those mappings to the
existing server and serverless item models.

Every contract violation found in a document is accumulated and reported
together, so a producer can fix a whole document in one edit rather than one
error per run.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import json
import os
from pathlib import Path
from typing import Any, TypeVar

from ...exceptions import ImportItemValidationError
from .models import ImportDocument
from .spec import (
    ANY,
    DOCUMENT_SPEC,
    ITEM_SPECS,
    ITEM_TYPES,
    NON_FINITE_MESSAGE,
    TREE_NODE_SPEC,
    FieldSpec,
    check_version,
    is_non_finite,
)

_INVALID = object()
"""Sentinel returned when a value failed validation."""

_JSON_SCALARS = (str, int, float, bool, type(None))
"""Scalar types that can appear in a table cell or a tree value."""

MAX_TREE_DEPTH = 100
"""Deepest ``children`` nesting accepted.

Reported as a validation error rather than allowed to exhaust the interpreter
stack: the recursive builders run during parsing, so a RecursionError there
would abort the whole document before any item could be saved.
"""

_T = TypeVar("_T")


class ErrorCollector:
    """Accumulates validation problems for a single parse pass.

    ``problems`` holds every recorded ``(location, message)`` pair, in
    discovery order.
    """

    def __init__(self) -> None:
        self.problems: list[tuple[str, str]] = []

    def add(self, location: str, message: str) -> None:
        """Record one problem at ``location``."""
        self.problems.append((location, message))

    def raise_if_any(self) -> None:
        """Raise :class:`ImportItemValidationError` when anything was recorded."""
        if self.problems:
            raise ImportItemValidationError(self.problems)


def _type_name(kind: Any) -> str:
    """Render one or more types as a readable name."""
    if kind is ANY:
        return "any value"
    if isinstance(kind, tuple):
        return " or ".join(sorted({_SIMPLE_NAMES.get(k, k.__name__) for k in kind}))
    return _SIMPLE_NAMES.get(kind, kind.__name__)


_SIMPLE_NAMES = {
    str: "a string",
    int: "an integer",
    float: "a number",
    bool: "a boolean",
    list: "an array",
    dict: "an object",
}


def _matches(value: Any, kind: Any) -> bool:
    """Type check that never treats ``True``/``False`` as an integer."""
    if kind is ANY:
        return True
    kinds = kind if isinstance(kind, tuple) else (kind,)
    if isinstance(value, bool) and bool not in kinds:
        return False
    return isinstance(value, kinds)


def _check_value(value: Any, spec: FieldSpec, location: str, errors: ErrorCollector) -> Any:
    """Validate and normalize one field value.

    Returns
    -------
    Any
        The normalized value, or :data:`_INVALID` when validation failed.
    """
    if value is None:
        if spec.required:
            errors.add(location, "must not be null")
            return _INVALID
        return spec.default_value()

    if not _matches(value, spec.kind):
        errors.add(location, f"expected {_type_name(spec.kind)}, got {type(value).__name__}")
        return _INVALID

    if spec.item_kind is not None:
        bad = False
        for index, element in enumerate(value):
            if not _matches(element, spec.item_kind):
                errors.add(
                    f"{location}[{index}]",
                    f"expected {_type_name(spec.item_kind)}, got {type(element).__name__}",
                )
                bad = True
        if bad:
            return _INVALID

    if spec.min_len is not None and len(value) < spec.min_len:
        noun = "characters" if isinstance(value, str) else "entries"
        errors.add(location, f"must have at least {spec.min_len} {noun}")
        return _INVALID

    if spec.choices is not None and value not in spec.choices:
        allowed = ", ".join(repr(choice) for choice in spec.choices)
        errors.add(location, f"expected one of [{allowed}], got {value!r}")
        return _INVALID

    if spec.coerce is not None:
        try:
            value = spec.coerce(value)
        except ValueError as exc:
            errors.add(location, str(exc))
            return _INVALID

    if spec.validate is not None:
        message = spec.validate(value)
        if message is not None:
            errors.add(location, message)
            return _INVALID

    return value


def apply_spec(
    raw: dict[str, Any],
    specs: tuple[FieldSpec, ...],
    location: str,
    errors: ErrorCollector,
    *,
    logger: Any = None,
) -> dict[str, Any]:
    """Validate ``raw`` against ``specs``.

    Parameters
    ----------
    raw : dict
        Raw JSON object.
    specs : tuple of FieldSpec
        Field table to validate against.
    location : str
        Dotted/indexed path used in problem reports.
    errors : ErrorCollector
        Collector that receives every problem found.
    logger : object, optional
        Logger used to warn about unknown keys, which are ignored.

    Returns
    -------
    dict
        Normalized field values, keyed by field name.
    """
    values: dict[str, Any] = {}

    for spec in specs:
        field_location = f"{location}.{spec.name}" if location else spec.name
        if spec.name in raw:
            checked = _check_value(raw[spec.name], spec, field_location, errors)
        else:
            if spec.required:
                errors.add(field_location, "is required")
            checked = _INVALID
        values[spec.name] = spec.default_value() if checked is _INVALID else checked

    if logger is not None:
        for key in raw:
            if key not in values:
                logger.warning("%s: unknown key %r is ignored.", location or "<document>", key)

    return values


def _build_each(raws: Iterable[Any], build: Callable[[Any, int], _T | None]) -> tuple[_T, ...]:
    """Call ``build(raw, index)`` on every entry, dropping the ones that failed."""
    built = (build(raw, index) for index, raw in enumerate(raws))
    return tuple(entry for entry in built if entry is not None)


def _check_scalar(value: Any, location: str, errors: ErrorCollector, expected: str) -> None:
    """Check that ``value`` is a finite JSON scalar; ``expected`` prefixes the type error."""
    if not isinstance(value, _JSON_SCALARS):
        errors.add(location, f"{expected}, got {type(value).__name__}")
    elif is_non_finite(value):
        errors.add(location, NON_FINITE_MESSAGE)


def _validate_tree_value(value: Any, location: str, errors: ErrorCollector) -> None:
    """Check that a tree node value is a finite JSON scalar or a list of them."""
    if isinstance(value, list):
        for index, element in enumerate(value):
            _check_scalar(element, f"{location}[{index}]", errors, "tree values must be scalars")
    else:
        _check_scalar(value, location, errors, "tree values must be a scalar or a list of scalars")


def build_tree_node(
    raw: Any,
    location: str,
    errors: ErrorCollector,
    *,
    logger: Any = None,
    depth: int = 1,
) -> dict[str, Any] | None:
    """Build one tree node, recursing into its children."""
    if not isinstance(raw, dict):
        errors.add(location, f"expected an object, got {type(raw).__name__}")
        return None

    if depth > MAX_TREE_DEPTH:
        errors.add(location, f"tree nesting is deeper than {MAX_TREE_DEPTH} levels")
        return None

    values = apply_spec(raw, TREE_NODE_SPEC, location, errors, logger=logger)

    value = values["value"]
    if value is None:
        # The schema defines an omitted value as the node name.
        value = values["name"]
    else:
        _validate_tree_value(value, f"{location}.value", errors)

    children = _build_each(
        values["children"],
        lambda child, index: build_tree_node(
            child,
            f"{location}.children[{index}]",
            errors,
            logger=logger,
            depth=depth + 1,
        ),
    )
    return {"name": values["name"], "value": value, "key": values["key"], "children": children}


def _validate_table(values: dict[str, Any], location: str, errors: ErrorCollector) -> None:
    """Check table shape, cell types, and axis references."""
    columns = values["columns"] or ()
    rows = values["rows"] or ()
    column_names = [column["name"] for column in columns]

    expected_width = len(columns) if columns else (len(rows[0]) if rows else 0)
    for row_index, row in enumerate(rows):
        row_location = f"{location}.rows[{row_index}]"
        if len(row) != expected_width:
            errors.add(
                row_location,
                f"expected {expected_width} cells to match the other rows, got {len(row)}",
            )
        for cell_index, cell in enumerate(row):
            _check_scalar(
                cell, f"{row_location}[{cell_index}]", errors, "table cells must be scalars"
            )

    if not column_names:
        return

    xaxis = values.get("xaxis")
    if xaxis is not None and xaxis not in column_names:
        errors.add(f"{location}.xaxis", f"{xaxis!r} does not name a column")

    yaxis = values.get("yaxis")
    if yaxis is not None:
        for index, label in enumerate(yaxis):
            if label not in column_names:
                errors.add(f"{location}.yaxis[{index}]", f"{label!r} does not name a column")


def build_item(
    raw: Any,
    index: int,
    errors: ErrorCollector,
    *,
    base_dir: str | None = None,
    logger: Any = None,
) -> dict[str, Any] | None:
    """Build one item payload from the document ``items`` array."""
    location = f"items[{index}]"
    if not isinstance(raw, dict):
        errors.add(location, f"expected an object, got {type(raw).__name__}")
        return None

    item_type = raw.get("item_type")
    if item_type not in ITEM_SPECS:
        allowed = ", ".join(repr(name) for name in ITEM_TYPES)
        errors.add(f"{location}.item_type", f"expected one of [{allowed}], got {item_type!r}")
        return None

    values = apply_spec(raw, ITEM_SPECS[item_type], location, errors, logger=logger)

    if item_type == "table":
        _validate_table(values, location, errors)
    elif item_type == "tree":
        values["nodes"] = _build_each(
            values["nodes"] or (),
            lambda node, node_index: build_tree_node(
                node, f"{location}.nodes[{node_index}]", errors, logger=logger
            ),
        )

    return {**values, "base_dir": base_dir}


def build_document(
    raw: Any,
    *,
    base_dir: str | Path | None = None,
    logger: Any = None,
) -> ImportDocument:
    """Validate a raw mapping and build an :class:`ImportDocument`.

    Parameters
    ----------
    raw : Any
        Decoded JSON document.
    base_dir : str or pathlib.Path, optional
        Directory that relative media paths resolve against.
    logger : object, optional
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
    errors = ErrorCollector()
    if not isinstance(raw, dict):
        errors.add("<document>", f"expected an object, got {type(raw).__name__}")
        errors.raise_if_any()

    base = None if base_dir is None else str(base_dir)

    # Version is an envelope-level precondition: fail before anything else is
    # interpreted, because another major may redefine every field below.
    schema_version = check_version(raw.get("schema_version"))

    values = apply_spec(raw, DOCUMENT_SPEC, "", errors, logger=logger)
    items = _build_each(
        values["items"],
        lambda item_raw, index: build_item(item_raw, index, errors, base_dir=base, logger=logger),
    )

    errors.raise_if_any()

    if logger is not None and not items:
        logger.warning("The import document declares no items.")

    return ImportDocument(
        schema_version=schema_version,
        app_id=values["app_id"],
        tags=values["tags"],
        items=items,
        base_dir=base,
    )


def read_document(path: str | Path) -> Any:
    """Read and decode an import document from a JSON file without validating it.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the JSON document.

    Returns
    -------
    Any
        The decoded JSON value, to pass to :func:`build_document`.

    Raises
    ------
    ImportItemValidationError
        If the file cannot be read, is not UTF-8, or is not valid JSON.
    """
    document_path = Path(path)
    try:
        # utf-8-sig also reads plain UTF-8; Windows editors routinely add a BOM.
        with document_path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError:
        problem = (str(document_path), "the import document does not exist")
    except OSError as exc:
        # Permission denied, a directory instead of a file, and similar.
        reason = f"the import document cannot be read: {exc.strerror or exc}"
        problem = (str(document_path), reason)
    except UnicodeDecodeError as exc:
        problem = (f"{document_path}:byte {exc.start}", "the import document is not valid UTF-8")
    except json.JSONDecodeError as exc:
        problem = (f"{document_path}:{exc.lineno}:{exc.colno}", f"invalid JSON: {exc.msg}")
    raise ImportItemValidationError([problem]) from None


def load_document(
    document: str | Path | dict[str, Any],
    *,
    base_dir: str | Path | None = None,
    logger: Any = None,
) -> ImportDocument:
    """Validate an import document given as a JSON file path or a decoded dict.

    Parameters
    ----------
    document : str, pathlib.Path, or dict
        Path to the JSON document, or the already-decoded document.
    base_dir : str or pathlib.Path, optional
        Directory that relative media paths resolve against. Defaults to the
        directory containing the file, or to the current working directory
        for a dict.
    logger : object, optional
        Logger used for warnings.

    Returns
    -------
    ImportDocument
        The validated document.

    Raises
    ------
    ImportItemValidationError
        If the file cannot be read, is not valid JSON, or the document
        violates the contract.
    ImportItemVersionError
        If the declared schema version is not supported.
    """
    if isinstance(document, (str, os.PathLike)):
        raw = read_document(document)
        if base_dir is None:
            base_dir = Path(document).parent
    else:
        raw = document
    return build_document(raw, base_dir=base_dir, logger=logger)
