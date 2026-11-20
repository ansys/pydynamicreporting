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

"""Shared payload mapping for both import backends."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .spec import TABLE_PROPERTIES


def payload_from_json(item_data: dict[str, Any]) -> Any:
    """Build the payload content for one validated item.

    Returns
    -------
    Any
        The ``value`` for ``text``/``html``, the ``array`` and ``dtype`` for
        ``table``, the ``nodes`` for ``tree``, and the file path for media.
    """
    item_type = item_data["item_type"]
    if item_type in ("text", "html"):
        return item_data["value"]
    if item_type == "table":
        # An omitted dtype is left out so each backend applies its own default.
        return {key: item_data[key] for key in ("array", "dtype") if item_data[key] is not None}
    if item_type == "tree":
        return item_data["nodes"]
    path, base_dir = item_data["path"], item_data["base_dir"]
    # Joining keeps an absolute path as is. A non-string path is passed
    # unchanged so the backend file validator reports it.
    if isinstance(path, str) and base_dir is not None:
        return str(Path(base_dir) / path)
    return path


def table_properties_from_json(item_data: dict[str, Any]) -> dict[str, Any]:
    """Return the table display properties the document sets, unchanged."""
    return {key: item_data[key] for key in TABLE_PROPERTIES if item_data[key] is not None}
