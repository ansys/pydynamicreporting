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

"""Backend-agnostic JSON import contract for Ansys Dynamic Reporting.

This package owns the import document schema, its validation, and the
orchestration that drives a backend adapter. It depends only on the standard
library and NumPy; it must never import a backend module.
"""

from .enums import ITEM_TYPES, TEMPLATE_REPORT_TYPE, TEMPLATE_TYPES
from .errors import ADRImportError, ImportValidationError, ImportVersionError
from .importer import ImportBackend, JSONImporter
from .models import (
    DatasetPayload,
    ImportDocument,
    ItemPayload,
    SessionPayload,
    TableColumn,
    TemplatePayload,
    TreeNode,
)
from .parser import build_document, load_document
from .result import ImportResult, ItemFailure
from .tags import combine_tags, normalize_tags
from .version import SCHEMA_VERSION, SUPPORTED_MAJOR, check_version, parse_version

__all__ = [
    "ADRImportError",
    "ImportValidationError",
    "ImportVersionError",
    "ImportBackend",
    "JSONImporter",
    "ImportDocument",
    "ItemPayload",
    "TemplatePayload",
    "SessionPayload",
    "DatasetPayload",
    "TableColumn",
    "TreeNode",
    "ImportResult",
    "ItemFailure",
    "ITEM_TYPES",
    "TEMPLATE_TYPES",
    "TEMPLATE_REPORT_TYPE",
    "SCHEMA_VERSION",
    "SUPPORTED_MAJOR",
    "build_document",
    "load_document",
    "check_version",
    "parse_version",
    "combine_tags",
    "normalize_tags",
]
