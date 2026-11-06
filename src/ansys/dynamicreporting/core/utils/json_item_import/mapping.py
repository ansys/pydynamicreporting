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

"""Shared payload mapping and tag validation for both import backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .spec import TABLE_PROPERTIES, check_tags

__all__ = [
    "item_content",
    "item_tags",
    "resolve_path",
    "table_fields",
]


def resolve_path(path: object, base_dir: str | None = None) -> object:
    """Resolve a media path against the directory holding the document.

    Absolute paths are returned unchanged so a producer keeps full control.
    A value that is not a string is also returned unchanged, so the backend
    file validator reports it when the item is saved.
    """
    if not isinstance(path, str):
        return path
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


def item_tags(doc_tags: Any, raw_item_tags: Any) -> list[tuple[str, Any]]:
    """Check raw document/item tags and return their ``(key, value)`` pairs, document first.

    Each backend passes the pairs to its own ``add_tag``.
    """
    checked = check_tags(doc_tags, "document tags") + check_tags(raw_item_tags, "item tags")
    return [pair for tags in checked for pair in tags.items()]
