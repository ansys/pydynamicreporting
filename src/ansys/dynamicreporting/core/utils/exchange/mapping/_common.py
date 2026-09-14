"""Common helpers for ADR exchange importers."""

from __future__ import annotations

from typing import Any

import numpy as np


def rows_to_array(rows: list[list[Any]]) -> np.ndarray:
    """Convert row data to a NumPy array, preferring floats and falling back to bytes."""
    try:
        return np.array(rows, dtype="float")
    except (TypeError, ValueError):
        return np.array(rows, dtype="S")


def derive_axes(columns: list[Any], xaxis: str | None = None, yaxis: list[str] | None = None):
    """Return explicit or derived axis labels for a table."""
    if xaxis is not None:
        resolved_x = xaxis
    elif columns:
        resolved_x = str(columns[0]) if isinstance(columns[0], str) else columns[0].name
    else:
        resolved_x = None

    if yaxis is not None:
        resolved_y = yaxis
    elif len(columns) > 1:
        resolved_y = [
            str(column) if isinstance(column, str) else column.name for column in columns[1:]
        ]
    else:
        resolved_y = []
    return resolved_x, resolved_y


def flatten_tree(nodes: list[Any]) -> list[dict[str, Any]]:
    """Convert tree nodes to the nested dict structure used by the ADR tree item model."""

    def _flatten(node: Any, parent_key: str = "", level: int = 0) -> dict[str, Any]:
        node_key = f"{parent_key}_{node.name}".replace(" ", "_").lower()
        children = [
            _flatten(child, f"{node_key}_child_{idx}", level + 1)
            for idx, child in enumerate(getattr(node, "children", []))
        ]
        return {
            "key": node_key,
            "value": node.name,
            "name": node.name,
            "level": level,
            "children": children,
        }

    return [_flatten(node, f"node_{idx}", 0) for idx, node in enumerate(nodes)]


def apply_properties(item: Any, properties: list[dict[str, Any]] | None) -> None:
    """Apply item properties while guarding against method overrides."""
    if not properties:
        return

    flat: dict[str, Any] = {}
    for entry in properties:
        if isinstance(entry, dict):
            flat.update(entry)

    for key, value in flat.items():
        if not isinstance(key, str) or key.startswith("_"):
            continue
        cls_attr = getattr(type(item), key, None)
        if callable(cls_attr) and not isinstance(cls_attr, property):
            continue
        setattr(item, key, value)
