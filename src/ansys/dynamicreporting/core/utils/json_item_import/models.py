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

"""Document envelope objects for the ADR import item document."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    items: tuple[dict[str, Any], ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)
    base_dir: str | None = None
