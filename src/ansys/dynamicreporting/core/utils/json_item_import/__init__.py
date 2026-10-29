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

"""Backend-agnostic JSON item import contract for Ansys Dynamic Reporting.

This package owns the import document schema, its validation, and the
per-item orchestration. Like ``populate_template`` for the template JSON
import, it never imports a backend module: ``report_remote_server.Server`` and
the serverless ``ADR`` pass in the callable that builds their own models.
"""

from ...exceptions import ADRItemImportError, ImportItemValidationError, ImportItemVersionError
from .importer import import_items
from .mapping import combine_tags, normalize_tags
from .models import (
    DatasetPayload,
    ImportDocument,
    ImportResult,
    ItemFailure,
    SessionPayload,
)
from .parser import build_document, load_document, read_document
from .spec import ITEM_TYPES, SCHEMA_VERSION, SUPPORTED_MAJOR, check_version, parse_version

__all__ = [
    "ADRItemImportError",
    "ImportItemValidationError",
    "ImportItemVersionError",
    "import_items",
    "ImportDocument",
    "SessionPayload",
    "DatasetPayload",
    "ImportResult",
    "ItemFailure",
    "ITEM_TYPES",
    "SCHEMA_VERSION",
    "SUPPORTED_MAJOR",
    "build_document",
    "load_document",
    "read_document",
    "check_version",
    "parse_version",
    "combine_tags",
    "normalize_tags",
]
