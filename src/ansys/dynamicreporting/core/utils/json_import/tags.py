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

"""Tag rendering for the ADR import layer.

Both backend adapters are required to render tags through these two functions.
A backend that builds its own ``key=value`` string will drift from the other
one; the drift guard asserts there is no such local rendering.
"""

from __future__ import annotations

from typing import Any


def _quote(token: str) -> str:
    """Quote a tag token that contains whitespace.

    Mirrors the convention used by
    :meth:`ansys.dynamicreporting.core.serverless.base.BaseModel._add_quotes`,
    so tags produced here survive a later parse of the tag string.
    """
    if " " in token and not token.startswith("'"):
        return f"'{token}'"
    return token


def _render_mapping(mapping: dict[Any, Any]) -> list[str]:
    """Render one tag object as a list of ``key=value`` tokens."""
    tokens: list[str] = []
    for key, value in mapping.items():
        if value is None:
            continue
        tokens.append(f"{_quote(str(key))}={_quote(str(value))}")
    return tokens


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
