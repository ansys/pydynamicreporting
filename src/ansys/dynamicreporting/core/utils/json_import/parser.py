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

"""Validation and construction of ADR import documents.

The parser walks the declarative tables in
:mod:`~ansys.dynamicreporting.core.utils.json_import.spec` and turns raw JSON
into the frozen payload objects in
:mod:`~ansys.dynamicreporting.core.utils.json_import.models`.

Every contract violation found in a document is accumulated and reported
together, so a producer can fix a whole document in one edit rather than one
error per run.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
import json
from pathlib import Path
from typing import Any

from ...adr_utils import check_filter
from .enums import ITEM_TYPES, LAYOUT_TEMPLATE_TYPES, TEMPLATE_TYPES
from .errors import ImportValidationError
from .models import (
    DatasetPayload,
    ImportDocument,
    ItemPayload,
    SessionPayload,
    TemplatePayload,
    TreeNode,
)
from .spec import (
    ANY,
    COMMON_ITEM_NAMES,
    DATASET_SPEC,
    DOCUMENT_SPEC,
    ITEM_SPECS,
    SESSION_SPEC,
    TEMPLATE_SPEC,
    TREE_NODE_SPEC,
    FieldSpec,
)
from .version import check_version

_INVALID = object()
"""Sentinel returned when a value failed validation."""

_JSON_SCALARS = (str, int, float, bool, type(None))
"""Scalar types that can appear in a table cell or a tree value."""

TEMPLATE_REPORT_TYPES = frozenset(TEMPLATE_TYPES)
"""Fast membership set for the ``template_type`` discriminator."""

# Layout-only convenience fields. ``set_column_count``/``set_column_widths``
# are defined on Layout, so a generator carrying them is a contract error.
_LAYOUT_ONLY_FIELDS = ("column_count", "column_widths")


class ErrorCollector:
    """Accumulates validation problems for a single parse pass."""

    def __init__(self) -> None:
        self._problems: list[tuple[str, str]] = []

    def add(self, location: str, message: str) -> None:
        """Record one problem at ``location``."""
        self._problems.append((location, message))

    @property
    def problems(self) -> tuple[tuple[str, str], ...]:
        """All problems recorded so far, in discovery order."""
        return tuple(self._problems)

    def __bool__(self) -> bool:
        return bool(self._problems)

    def __len__(self) -> int:
        return len(self._problems)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._problems)

    def raise_if_any(self) -> None:
        """Raise :class:`ImportValidationError` when anything was recorded."""
        if self._problems:
            raise ImportValidationError(self._problems)


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
        return spec.default_factory() if spec.default_factory else spec.default

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
    specs: Iterable[FieldSpec],
    location: str,
    errors: ErrorCollector,
    *,
    strict_keys: bool = False,
    logger: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate ``raw`` against ``specs``.

    Parameters
    ----------
    raw : dict
        Raw JSON object.
    specs : iterable of FieldSpec
        Field table to validate against.
    location : str
        Dotted/indexed path used in problem reports.
    errors : ErrorCollector
        Collector that receives every problem found.
    strict_keys : bool, default: False
        Promote unknown-key warnings to validation errors.
    logger : object, optional
        Logger used for deprecation and unknown-key warnings.

    Returns
    -------
    tuple of (dict, dict)
        Normalized field values, and the retained unknown keys.
    """
    values: dict[str, Any] = {}
    consumed: set[str] = set()

    for spec in specs:
        field_location = f"{location}.{spec.name}" if location else spec.name
        source_key: str | None = None
        if spec.name in raw:
            source_key = spec.name
            consumed.add(spec.name)
        if spec.alias and spec.alias in raw:
            consumed.add(spec.alias)
            if source_key is None:
                source_key = spec.alias
                if logger is not None:
                    logger.warning("%s: %r is deprecated; use %r.", location, spec.alias, spec.name)
            elif logger is not None:
                logger.warning(
                    "%s: both %r and deprecated %r are present; using %r.",
                    location,
                    spec.name,
                    spec.alias,
                    spec.name,
                )

        if source_key is None:
            if spec.required:
                errors.add(field_location, "is required")
            values[spec.name] = spec.default_factory() if spec.default_factory else spec.default
            continue

        checked = _check_value(raw[source_key], spec, field_location, errors)
        if checked is _INVALID:
            values[spec.name] = spec.default_factory() if spec.default_factory else spec.default
            continue
        values[spec.name] = checked

    extra = {key: value for key, value in raw.items() if key not in consumed}
    for key in extra:
        message = f"unknown key {key!r}"
        if strict_keys:
            errors.add(location, message)
        elif logger is not None:
            logger.warning("%s: %s is retained but not interpreted.", location, message)

    return values, extra


def _validate_tree_value(value: Any, location: str, errors: ErrorCollector) -> None:
    """Check that a tree node value is a JSON scalar or a list of scalars."""
    if isinstance(value, list):
        for index, element in enumerate(value):
            if not isinstance(element, _JSON_SCALARS):
                errors.add(
                    f"{location}[{index}]",
                    f"tree values must be scalars, got {type(element).__name__}",
                )
        return
    if not isinstance(value, _JSON_SCALARS):
        errors.add(
            location,
            f"tree values must be a scalar or a list of scalars, got {type(value).__name__}",
        )


def build_tree_node(
    raw: Any,
    location: str,
    errors: ErrorCollector,
    *,
    strict_keys: bool = False,
    logger: Any = None,
) -> TreeNode | None:
    """Build one tree node, recursing into its children."""
    if not isinstance(raw, dict):
        errors.add(location, f"expected an object, got {type(raw).__name__}")
        return None

    values, _ = apply_spec(
        raw, TREE_NODE_SPEC, location, errors, strict_keys=strict_keys, logger=logger
    )

    value = values["value"]
    if value is None:
        # The schema defines an omitted value as the node name.
        value = values["name"]
    else:
        _validate_tree_value(value, f"{location}.value", errors)

    children = tuple(
        node
        for index, child in enumerate(values["children"])
        if (
            node := build_tree_node(
                child,
                f"{location}.children[{index}]",
                errors,
                strict_keys=strict_keys,
                logger=logger,
            )
        )
        is not None
    )

    return TreeNode(name=values["name"], value=value, key=values["key"], children=children)


def _normalize_table_shape(
    raw: dict[str, Any], location: str, errors: ErrorCollector, logger: Any
) -> dict[str, Any]:
    """Fold a ``data: {columns, rows}`` wrapper into the top-level form.

    The wrapper is removed so exactly one representation reaches the rest of
    the parser; carrying both forward is what makes downstream code guess.
    """
    if "data" not in raw:
        return raw

    normalized = dict(raw)
    wrapper = normalized.pop("data")
    if not isinstance(wrapper, dict):
        errors.add(f"{location}.data", f"expected an object, got {type(wrapper).__name__}")
        return normalized

    for key in ("columns", "rows"):
        if key not in wrapper:
            continue
        if key in normalized:
            if logger is not None:
                logger.warning(
                    "%s: both top-level %r and 'data.%s' are present; using the top-level value.",
                    location,
                    key,
                    key,
                )
            continue
        normalized[key] = wrapper[key]
    return normalized


def _validate_table(values: dict[str, Any], location: str, errors: ErrorCollector) -> None:
    """Check table shape, cell types, and axis references."""
    columns = values["columns"] or ()
    rows = values["rows"] or ()
    column_names = [column.name for column in columns]

    expected_width = len(columns) if columns else (len(rows[0]) if rows else 0)
    for row_index, row in enumerate(rows):
        row_location = f"{location}.rows[{row_index}]"
        if len(row) != expected_width:
            errors.add(
                row_location,
                f"expected {expected_width} cells to match the other rows, got {len(row)}",
            )
        for cell_index, cell in enumerate(row):
            if not isinstance(cell, _JSON_SCALARS):
                errors.add(
                    f"{row_location}[{cell_index}]",
                    f"table cells must be scalars, got {type(cell).__name__}",
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
    strict_keys: bool = False,
    logger: Any = None,
) -> ItemPayload | None:
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

    if item_type == "table":
        raw = _normalize_table_shape(raw, location, errors, logger)

    values, extra = apply_spec(
        raw, ITEM_SPECS[item_type], location, errors, strict_keys=strict_keys, logger=logger
    )

    if item_type == "table":
        _validate_table(values, location, errors)
    elif item_type == "tree":
        values["nodes"] = tuple(
            node
            for node_index, node_raw in enumerate(values["nodes"] or ())
            if (
                node := build_tree_node(
                    node_raw,
                    f"{location}.nodes[{node_index}]",
                    errors,
                    strict_keys=strict_keys,
                    logger=logger,
                )
            )
            is not None
        )

    payload = {name: value for name, value in values.items() if name not in COMMON_ITEM_NAMES}
    return ItemPayload(
        item_type=values["item_type"],
        name=values["name"],
        tags=values["tags"],
        source=values["source"],
        sequence=values["sequence"],
        properties=values["properties"],
        payload=payload,
        extra=extra,
        base_dir=base_dir,
    )


def build_template(
    raw: Any,
    location: str,
    errors: ErrorCollector,
    *,
    strict_keys: bool = False,
    logger: Any = None,
) -> TemplatePayload | None:
    """Build one template payload, recursing into its children."""
    if not isinstance(raw, dict):
        errors.add(location, f"expected an object, got {type(raw).__name__}")
        return None

    template_type = raw.get("template_type")
    if template_type not in TEMPLATE_REPORT_TYPES:
        allowed = ", ".join(repr(name) for name in TEMPLATE_TYPES)
        errors.add(
            f"{location}.template_type", f"expected one of [{allowed}], got {template_type!r}"
        )
        return None

    values, extra = apply_spec(
        raw, TEMPLATE_SPEC, location, errors, strict_keys=strict_keys, logger=logger
    )

    if template_type not in LAYOUT_TEMPLATE_TYPES:
        for name in _LAYOUT_ONLY_FIELDS:
            if values.get(name) is not None:
                errors.add(
                    f"{location}.{name}",
                    f"is only valid for layout templates, not template_type {template_type!r}",
                )

    item_filter = values["item_filter"]
    if item_filter and not check_filter(item_filter):
        errors.add(
            f"{location}.item_filter",
            f"{item_filter!r} is not a valid ADR query expression; expected "
            "';'-separated stanzas of 'A|i_<field>|<operator>|<value>'",
        )

    children = tuple(
        child
        for child_index, child_raw in enumerate(values["children"])
        if (
            child := build_template(
                child_raw,
                f"{location}.children[{child_index}]",
                errors,
                strict_keys=strict_keys,
                logger=logger,
            )
        )
        is not None
    )

    return TemplatePayload(
        template_type=values["template_type"],
        name=values["name"],
        tags=values["tags"],
        item_filter=item_filter,
        params=values["params"],
        html=values["html"],
        column_count=values["column_count"],
        column_widths=values["column_widths"],
        sort_selection=values["sort_selection"],
        sort_fields=values["sort_fields"],
        filter_mode=values["filter_mode"],
        children=children,
        extra=extra,
    )


def _build_simple(
    raw: Any,
    location: str,
    specs: tuple[FieldSpec, ...],
    factory: Any,
    errors: ErrorCollector,
    *,
    strict_keys: bool,
    logger: Any,
) -> Any:
    """Build a session or dataset payload."""
    if not isinstance(raw, dict):
        errors.add(location, f"expected an object, got {type(raw).__name__}")
        return None
    values, extra = apply_spec(raw, specs, location, errors, strict_keys=strict_keys, logger=logger)
    return factory(**values, extra=extra)


def build_document(
    raw: Any,
    *,
    base_dir: str | None = None,
    strict_keys: bool = False,
    logger: Any = None,
) -> ImportDocument:
    """Validate a raw mapping and build an :class:`ImportDocument`.

    Parameters
    ----------
    raw : Any
        Decoded JSON document.
    base_dir : str, optional
        Directory that relative media paths resolve against.
    strict_keys : bool, default: False
        Treat unknown keys as validation errors.
    logger : object, optional
        Logger used for warnings and notes.

    Returns
    -------
    ImportDocument
        The validated document.

    Raises
    ------
    ImportValidationError
        If the document violates the contract. The error carries every
        problem found during the pass.
    ImportVersionError
        If the declared schema version is malformed or too new.
    """
    errors = ErrorCollector()
    if not isinstance(raw, dict):
        errors.add("<document>", f"expected an object, got {type(raw).__name__}")
        errors.raise_if_any()

    # Version is an envelope-level precondition: fail before anything else is
    # interpreted, because a newer major may redefine every field below.
    schema_version = check_version(raw.get("schema_version"), logger)

    values, extra = apply_spec(
        raw, DOCUMENT_SPEC, "", errors, strict_keys=strict_keys, logger=logger
    )

    sessions = tuple(
        session
        for index, session_raw in enumerate(values["sessions"])
        if (
            session := _build_simple(
                session_raw,
                f"sessions[{index}]",
                SESSION_SPEC,
                SessionPayload,
                errors,
                strict_keys=strict_keys,
                logger=logger,
            )
        )
        is not None
    )
    datasets = tuple(
        dataset
        for index, dataset_raw in enumerate(values["datasets"])
        if (
            dataset := _build_simple(
                dataset_raw,
                f"datasets[{index}]",
                DATASET_SPEC,
                DatasetPayload,
                errors,
                strict_keys=strict_keys,
                logger=logger,
            )
        )
        is not None
    )
    items = tuple(
        item
        for index, item_raw in enumerate(values["items"])
        if (
            item := build_item(
                item_raw,
                index,
                errors,
                base_dir=base_dir,
                strict_keys=strict_keys,
                logger=logger,
            )
        )
        is not None
    )
    templates = tuple(
        template
        for index, template_raw in enumerate(values["templates"])
        if (
            template := build_template(
                template_raw,
                f"templates[{index}]",
                errors,
                strict_keys=strict_keys,
                logger=logger,
            )
        )
        is not None
    )

    errors.raise_if_any()

    if logger is not None:
        if sessions or datasets:
            logger.info(
                "'sessions' and 'datasets' are accepted but not applied in schema version %s; "
                "items use the backend defaults.",
                schema_version,
            )
        if not items and not templates:
            logger.warning("The import document declares no items and no templates.")

    return ImportDocument(
        schema_version=schema_version,
        app_id=values["app_id"],
        tags=values["tags"],
        metadata=values["metadata"],
        sessions=sessions,
        datasets=datasets,
        items=items,
        templates=templates,
        extra=extra,
        base_dir=base_dir,
    )


def load_document(
    path: str | Path,
    *,
    base_dir: str | None = None,
    strict_keys: bool = False,
    logger: Any = None,
) -> ImportDocument:
    """Read and validate an import document from a JSON file.

    Parameters
    ----------
    path : str or pathlib.Path
        Path to the JSON document.
    base_dir : str, optional
        Directory that relative media paths resolve against. Defaults to the
        directory containing ``path``.
    strict_keys : bool, default: False
        Treat unknown keys as validation errors.
    logger : object, optional
        Logger used for warnings and notes.

    Returns
    -------
    ImportDocument
        The validated document.
    """
    document_path = Path(path)
    try:
        with document_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        raise ImportValidationError(
            [(str(document_path), "the import document does not exist")]
        ) from None
    except json.JSONDecodeError as exc:
        raise ImportValidationError(
            [(f"{document_path}:{exc.lineno}:{exc.colno}", f"invalid JSON: {exc.msg}")]
        ) from None

    resolved_base = base_dir if base_dir is not None else str(document_path.parent)
    return build_document(raw, base_dir=resolved_base, strict_keys=strict_keys, logger=logger)
