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

"""Parsed payload objects for the ADR import document.

These are plain frozen dataclasses. They are produced by
:mod:`~ansys.dynamicreporting.core.utils.json_import.parser` and consumed by
the importer core and the backend adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TableColumn:
    """A single table column definition."""

    name: str
    type: str = "string"


@dataclass(frozen=True)
class TreeNode:
    """A node of a tree item payload."""

    name: str
    value: Any = None
    key: str | None = None
    children: tuple["TreeNode", ...] = ()


@dataclass(frozen=True)
class ItemPayload:
    """A validated item from the document ``items`` array.

    Type-specific fields live in :attr:`payload` and are surfaced by the
    convenience properties below, so every item type shares one class.
    """

    item_type: str
    name: str
    tags: tuple[dict[str, Any], ...] = ()
    source: str = ""
    sequence: int = 0
    properties: tuple[dict[str, Any], ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    base_dir: str | None = None

    @property
    def value(self) -> str | None:
        """Inline body for ``text`` and ``html`` items."""
        return self.payload.get("value")

    @property
    def path(self) -> str | None:
        """Unresolved file path for media items."""
        return self.payload.get("path")

    @property
    def columns(self) -> tuple[TableColumn, ...]:
        """Column definitions for ``table`` items."""
        return self.payload.get("columns", ())

    @property
    def rows(self) -> tuple[tuple[Any, ...], ...]:
        """Record-oriented rows for ``table`` items."""
        return self.payload.get("rows", ())

    @property
    def nodes(self) -> tuple[TreeNode, ...]:
        """Root nodes for ``tree`` items."""
        return self.payload.get("nodes", ())

    @property
    def plot(self) -> str | None:
        """Plot style for ``table`` items."""
        return self.payload.get("plot")

    @property
    def table_format(self) -> str | None:
        """Cell format for ``table`` items.

        Named ``table_format`` rather than ``format`` to avoid shadowing
        :meth:`str.format` semantics on the payload object.
        """
        return self.payload.get("format")

    @property
    def xaxis(self) -> str | None:
        """Explicit x-axis label for ``table`` items, if supplied."""
        return self.payload.get("xaxis")

    @property
    def yaxis(self) -> tuple[str, ...] | None:
        """Explicit y-axis labels for ``table`` items, if supplied."""
        return self.payload.get("yaxis")


@dataclass(frozen=True)
class TemplatePayload:
    """A validated node of the document ``templates`` tree."""

    template_type: str
    name: str
    tags: tuple[dict[str, Any], ...] = ()
    item_filter: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    html: str | None = None
    column_count: int | None = None
    column_widths: tuple[float, ...] | None = None
    sort_selection: str | None = None
    sort_fields: tuple[str, ...] | None = None
    filter_mode: str | None = None
    children: tuple["TemplatePayload", ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionPayload:
    """A validated entry of the document ``sessions`` array.

    Accepted and retained in v1.0, but not applied to created items.
    """

    name: str | None = None
    tags: tuple[dict[str, Any], ...] = ()
    application: str | None = None
    hostname: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DatasetPayload:
    """A validated entry of the document ``datasets`` array.

    Accepted and retained in v1.0, but not applied to created items.
    """

    name: str | None = None
    tags: tuple[dict[str, Any], ...] = ()
    filename: str | None = None
    format: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportDocument:
    """A validated ADR import document."""

    schema_version: str
    app_id: str
    tags: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    sessions: tuple[SessionPayload, ...] = ()
    datasets: tuple[DatasetPayload, ...] = ()
    items: tuple[ItemPayload, ...] = ()
    templates: tuple[TemplatePayload, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)
    base_dir: str | None = None
