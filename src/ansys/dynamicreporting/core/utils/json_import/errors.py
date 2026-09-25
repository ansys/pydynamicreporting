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

"""Exceptions raised by the ADR JSON import layer."""

from __future__ import annotations

from collections.abc import Iterable

from ...exceptions import ADRException


class ADRImportError(ADRException):
    """Base class for every failure raised by the JSON import layer."""

    detail = "ADR JSON import failed"


class ImportVersionError(ADRImportError):
    """Raised when a document declares an unsupported or malformed schema version."""

    detail = "Unsupported ADR import schema version"


class ImportValidationError(ADRImportError):
    """Raised when a document violates the import contract.

    Unlike a fail-fast validator, this error carries **every** problem found
    during a single validation pass so that a producer can fix an entire
    document in one edit.

    Parameters
    ----------
    problems : iterable of tuple of (str, str)
        Pairs of ``(location, message)``, where ``location`` is a dotted and
        indexed path into the document such as ``"items[3].path"``.
    """

    detail = "The ADR import document is not valid"

    def __init__(self, problems: Iterable[tuple[str, str]]) -> None:
        self.problems: tuple[tuple[str, str], ...] = tuple(problems)
        super().__init__(self._render(self.problems))

    @staticmethod
    def _render(problems: tuple[tuple[str, str], ...]) -> str:
        """Render all collected problems as a single indented block."""
        count = len(problems)
        header = f"{count} problem{'' if count == 1 else 's'} found"
        lines = [f"  {location}: {message}" for location, message in problems]
        return "\n".join([header, *lines])
