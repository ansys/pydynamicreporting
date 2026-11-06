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
from typing import Any

from ..report_objects import ItemREST
from .spec import TABLE_PROPERTIES

__all__ = [
    "combine_tags",
    "item_content",
    "normalize_tags",
    "resolve_path",
    "table_fields",
]

# Reuses the REST model's quoting rather than the serverless
# BaseModel._add_quotes, which would pull in Django.
_quote = ItemREST.add_quotes


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
    str, dict, or list of dict
        The inline string for ``text``/``html``, the ``array`` and ``dtype``
        given for ``table``, the ``nodes`` exactly as the document gave them for
        ``tree``, and the resolved file path for every media type.
    """
    item_type = item_data["item_type"]
    if item_type in ("text", "html"):
        return item_data["value"]
    if item_type == "table":
        # An omitted dtype is left out so each backend applies its own default.
        return {key: item_data[key] for key in ("array", "dtype") if item_data[key] is not None}
    if item_type == "tree":
        return item_data["nodes"]
    return resolve_path(item_data["path"], item_data["base_dir"])


def table_fields(item_data: dict[str, Any]) -> dict[str, Any]:
    """Return the table display properties the document sets, unchanged."""
    return {key: item_data[key] for key in TABLE_PROPERTIES if item_data[key] is not None}


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
