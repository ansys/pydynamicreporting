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

"""Closed wire vocabularies for the ADR import schema.

This module holds plain data only. It must not import any backend module, so
that the import core stays backend-agnostic; the drift guard asserts these
tables stay in sync with the backend registries.
"""

from __future__ import annotations

ITEM_TYPES: tuple[str, ...] = (
    "text",
    "html",
    "table",
    "tree",
    "image",
    "animation",
    "scene",
    "file",
)
"""Closed set of ``item_type`` discriminator values."""

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
table is the only place that translation is allowed to live.
"""

MEDIA_ITEM_TYPES: frozenset[str] = frozenset({"image", "animation", "scene", "file"})
"""Item types whose payload is a file path rather than an inline value."""
