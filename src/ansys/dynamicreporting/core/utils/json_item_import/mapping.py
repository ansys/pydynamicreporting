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

"""Shared mapping helpers for the ADR item import backends.

``item_content``, ``table_fields``, and ``combine_tags`` are the only helpers
the backends call; they keep the REST and serverless models fed with identical
values. The lower-level helpers are their building blocks.

Both backends are required to render tags through :func:`normalize_tags` and
:func:`combine_tags`. A backend that builds its own ``key=value`` string will
drift from the other one; the drift guard asserts there is no such local
rendering.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import numpy

from ..report_objects import ItemREST

__all__ = [
    "column_labels",
    "combine_tags",
    "derive_axes",
    "flatten_tree",
    "item_content",
    "normalize_tags",
    "resolve_path",
    "rows_to_array",
    "table_fields",
]

_SLUG_RE = re.compile(r"[^0-9a-z]+")

# Reuses the REST model's quoting rather than the serverless
# BaseModel._add_quotes, which would pull in Django.
_quote = ItemREST.add_quotes


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
        every cell is a JSON number, boolean, or null, and auto-sized bytes
        dtype otherwise.
    """
    if not len(rows):
        return numpy.zeros((column_count or 0, 0), dtype=float)

    # Decide from the JSON cell types rather than letting NumPy try a float
    # cast: NumPy parses numeric-looking strings, so "001" would become 1.0.
    if all(cell is None or isinstance(cell, (int, float)) for row in rows for cell in row):
        return numpy.array(rows, dtype="float").T

    # Auto-sized bytes. 'S' without a width never truncates, unlike a fixed
    # '|S20'. Cells are encoded explicitly because NumPy encodes str -> bytes
    # as ASCII, which rejects a degree sign.
    text_rows = [
        [b"" if cell is None else str(cell).encode("utf-8") for cell in row] for row in rows
    ]
    return numpy.array(text_rows, dtype="S").T


def column_labels(columns: Any) -> list[str]:
    """Return names from bare strings or normalized column mappings."""
    return [column if isinstance(column, str) else column["name"] for column in columns]


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
    resolved_y = list(yaxis) if yaxis is not None else names[1:]
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
        name = node["name"]
        children = [
            _convert(child, f"{path}_{index}_{_slug(child['name'])}")
            for index, child in enumerate(node["children"])
        ]
        return {
            "key": node["key"] or path,
            "name": name,
            "value": node["value"],
            "children": children,
        }

    return [
        _convert(node, f"node_{index}_{_slug(node['name'])}") for index, node in enumerate(nodes)
    ]


def resolve_path(path: str, base_dir: str | None = None) -> str:
    """Resolve a media path against the directory holding the document.

    Absolute paths are returned unchanged so a producer keeps full control.
    """
    candidate = Path(path)
    if candidate.is_absolute() or base_dir is None:
        return str(candidate)
    return str(Path(base_dir) / candidate)


def item_content(item_data: dict[str, Any]) -> Any:
    """Build the payload content for one validated item.

    Returns
    -------
    str, numpy.ndarray, or list of dict
        The inline string for ``text``/``html``, the series-per-row array for
        ``table``, the nested node dicts for ``tree``, and the resolved file
        path for every media type.
    """
    item_type = item_data["item_type"]
    if item_type in ("text", "html"):
        return item_data["value"]
    if item_type == "table":
        return rows_to_array(item_data["rows"], len(item_data["columns"]))
    if item_type == "tree":
        return flatten_tree(item_data["nodes"])
    return resolve_path(item_data["path"], item_data["base_dir"])


def table_fields(item_data: dict[str, Any]) -> dict[str, Any]:
    """Return the first-class table display fields to set on a table item.

    Returns
    -------
    dict
        ``labels_row`` always, plus ``xaxis``, ``yaxis``, ``plot``, and
        ``format`` when they resolve to a value.
    """
    columns = item_data["columns"]
    fields: dict[str, Any] = {"labels_row": column_labels(columns)}
    xaxis, yaxis = derive_axes(columns, item_data["xaxis"], item_data["yaxis"])
    if xaxis is not None:
        fields["xaxis"] = xaxis
    if yaxis:
        fields["yaxis"] = yaxis
    for key in ("plot", "format"):
        if item_data[key] is not None:
            fields[key] = item_data[key]
    return fields


def _render_mapping(mapping: dict[Any, Any]) -> list[str]:
    """Render one tag object as a list of ``key=value`` tokens."""
    return [
        f"{_quote(str(key))}={_quote(str(value))}"
        for key, value in mapping.items()
        if value is not None
    ]


def normalize_tags(raw_tags: Any) -> str:
    """Render tags into ADR's space-separated ``key=value`` string.

    Parameters
    ----------
    raw_tags : Any
        ``None``, an already-rendered string, a single mapping, a list of
        mappings, a list of ``"key=value"`` strings, or a bare scalar.

    Returns
    -------
    str
        Space-separated tag string. Empty when there is nothing to render.
    """
    if raw_tags is None:
        return ""
    if isinstance(raw_tags, str):
        return raw_tags.strip()
    if isinstance(raw_tags, dict):
        return " ".join(_render_mapping(raw_tags))
    if isinstance(raw_tags, (list, tuple, set)):
        tokens: list[str] = []
        for entry in raw_tags:
            if entry is None:
                continue
            if isinstance(entry, dict):
                tokens.extend(_render_mapping(entry))
            elif isinstance(entry, str):
                stripped = entry.strip()
                if stripped:
                    tokens.append(stripped)
            else:
                tokens.append(_quote(str(entry)))
        return " ".join(tokens)
    return _quote(str(raw_tags))


def combine_tags(*parts: Any) -> str:
    """Normalize every part and join the non-empty results.

    Parameters
    ----------
    *parts : Any
        Tag payloads accepted by :func:`normalize_tags`.

    Returns
    -------
    str
        Space-separated tag string.
    """
    rendered = [normalize_tags(part) for part in parts]
    return " ".join(part for part in rendered if part)
