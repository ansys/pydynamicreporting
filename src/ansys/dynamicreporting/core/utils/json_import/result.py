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

"""Result objects returned by the ADR JSON importer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ItemFailure:
    """A single item that could not be saved.

    Parameters
    ----------
    index : int
        Zero-based position of the item in the document ``items`` array.
    name : str
        Item name, used instead of an index in log messages.
    item_type : str
        Wire ``item_type`` of the failed item.
    error : str
        Rendered exception text.
    """

    index: int
    name: str
    item_type: str
    error: str


@dataclass
class ImportResult:
    """Summary of a single document import.

    Parameters
    ----------
    schema_version : str
        Resolved schema version of the imported document.
    app_id : str
        ``app_id`` declared by the document.
    templates_created : int
        Number of templates created, counting every node of every tree.
    items_saved : int
        Number of items successfully persisted.
    failures : list of ItemFailure
        Per-item failures collected when ``on_error="collect"``.
    root_guids : list of str
        GUIDs of the root templates created by this import.
    """

    schema_version: str
    app_id: str
    templates_created: int = 0
    items_saved: int = 0
    failures: list[ItemFailure] = field(default_factory=list)
    root_guids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether every item in the document was saved."""
        return not self.failures
