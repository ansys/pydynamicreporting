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

"""Tests for the schema version check."""

from __future__ import annotations

import pytest

from ansys.dynamicreporting.core.exceptions import ImportItemVersionError
from ansys.dynamicreporting.core.utils.json_item_import.spec import (
    SCHEMA_VERSION,
    SUPPORTED_MAJOR,
    check_version,
)


@pytest.mark.unit
def test_check_version_defaults_when_absent():
    assert check_version(None) == SCHEMA_VERSION


@pytest.mark.unit
@pytest.mark.parametrize("text", [SCHEMA_VERSION, "1.7", "1.13"])
def test_check_version_accepts_the_supported_major(text):
    assert check_version(text) == text


@pytest.mark.unit
@pytest.mark.parametrize("text", [f"{SUPPORTED_MAJOR + 1}.0", "0.9"])
def test_check_version_rejects_another_major(text):
    with pytest.raises(ImportItemVersionError, match="not a supported schema version"):
        check_version(text)


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    # Surrounding whitespace and a trailing newline are rejected, matching the
    # JSON Schema pattern, so the schema and the parser agree.
    [
        "1",
        "1.0.0",
        "x.y",
        "",
        "1.",
        ".1",
        "v1.0",
        " 1.0 ",
        "1.0\n",
        "\u0661.\u0660",
        1.0,
        ["1", "0"],
    ],
)
def test_check_version_rejects_malformed(value):
    with pytest.raises(ImportItemVersionError):
        check_version(value)
