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

"""Shared mapping helpers for the ADR import adapters.

Every public helper here must be called by **both** backend adapters. A helper
with only one call site means the adapters have grown divergent inline copies,
which the drift guard fails on.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import numpy

_SLUG_RE = re.compile(r"[^0-9a-z]+")


def rows_to_array(rows: Any, column_count: int | None = None) -> numpy.ndarray:
    """Build the ADR table array from record-oriented rows.

    The wire format is record-oriented (one inner list per record), while ADR
    stores tables **series-per-row**: a table labelled
    ``labels_row = ["X", "Sin", "Cos"]`` is a ``(3, n)`` array. The returned
    array is therefore transposed, so that ``shape[0]`` equals the number of
    columns and matches the row labels.

    Parameters
    ----------
    rows : sequence of sequence
        Record-oriented rows, already validated as rectangular.
    column_count : int, optional
        Number of columns, used to shape the array when ``rows`` is empty.

    Returns
    -------
    numpy.ndarray
        A 2-D array of shape ``(n_columns, n_rows)``, of float dtype when
        every cell is numeric and auto-sized bytes dtype otherwise.
    """
    if not len(rows):
        return numpy.zeros((column_count or 0, 0), dtype=float)

    try:
        return numpy.array(rows, dtype="float").T
    except (TypeError, ValueError):
        # Fall back to auto-sized bytes. 'S' without a width never truncates,
        # unlike a fixed '|S20'.
        text_rows = [["" if cell is None else cell for cell in row] for row in rows]
        return numpy.array(text_rows, dtype="S").T


def column_labels(columns: Any) -> list[str]:
    """Return the column names, accepting bare strings or column objects."""
    return [column if isinstance(column, str) else column.name for column in columns]


def derive_axes(
    columns: Any, xaxis: str | None = None, yaxis: Any = None
) -> tuple[str | None, list[str]]:
    """Resolve the x and y axis labels for a table.

    Explicit values always win; otherwise column 0 becomes the x axis and the
    remaining columns become the y axes.

    Returns
    -------
    tuple of (str or None, list of str)
        The resolved x-axis label and y-axis labels.
    """
    names = column_labels(columns)
    resolved_x = xaxis if xaxis is not None else (names[0] if names else None)
    if yaxis is not None:
        resolved_y = list(yaxis)
    else:
        resolved_y = names[1:] if len(names) > 1 else []
    return resolved_x, resolved_y


def _slug(text: str) -> str:
    """Lowercase ``text`` and collapse non-alphanumeric runs to underscores."""
    return _SLUG_RE.sub("_", text.lower()).strip("_")


def flatten_tree(nodes: Any) -> list[dict[str, Any]]:
    """Convert tree node payloads into ADR's nested dict structure.

    Generated keys embed the position of the node in the tree, so two
    siblings with the same name cannot collide. An explicit ``key`` on a node
    is preserved.
    """

    def _convert(node: Any, path: str) -> dict[str, Any]:
        children = [
            _convert(child, f"{path}_{index}_{_slug(child.name)}")
            for index, child in enumerate(node.children)
        ]
        return {
            "key": node.key or path,
            "name": node.name,
            "value": node.value,
            "children": children,
        }

    return [_convert(node, f"node_{index}_{_slug(node.name)}") for index, node in enumerate(nodes)]


def _item_label(item: Any) -> str:
    """Return a human-readable name for log messages."""
    return getattr(item, "name", None) or getattr(item, "obj_name", None) or "<unnamed>"


def apply_properties(item: Any, properties: Any, logger: Any = None) -> None:
    """Apply escape-hatch properties onto a created item.

    Keys that are private or that would shadow a method are skipped and
    logged, so a document cannot overwrite ``save`` or ``delete``.

    Parameters
    ----------
    item : Any
        Backend item object.
    properties : sequence of dict
        One-key objects from the item ``properties`` array.
    logger : object, optional
        Logger used to report skipped keys.
    """
    if not properties:
        return

    flat: dict[str, Any] = {}
    for entry in properties:
        flat.update(entry)

    for key, value in flat.items():
        if not isinstance(key, str) or key.startswith("_"):
            if logger is not None:
                logger.warning(
                    "Item %r: property %r is not a public field name; ignored.",
                    _item_label(item),
                    key,
                )
            continue
        class_attribute = getattr(type(item), key, None)
        if callable(class_attribute) and not isinstance(class_attribute, property):
            if logger is not None:
                logger.warning(
                    "Item %r: property %r would shadow a method; ignored.",
                    _item_label(item),
                    key,
                )
            continue
        setattr(item, key, value)


def resolve_path(path: str, base_dir: str | None = None) -> str:
    """Resolve a media path against the directory holding the document.

    Absolute paths are returned unchanged so a producer keeps full control.
    """
    candidate = Path(path)
    if candidate.is_absolute() or base_dir is None:
        return str(candidate)
    return str(Path(base_dir) / candidate)
