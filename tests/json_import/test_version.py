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

"""Tests for schema version parsing and compatibility checks."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ansys.dynamicreporting.core.utils.json_import.errors import ImportVersionError
from ansys.dynamicreporting.core.utils.json_import.version import (
    SCHEMA_VERSION,
    SUPPORTED_MAJOR,
    check_version,
    parse_version,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "expected"),
    [("1.0", (1, 0)), ("1.7", (1, 7)), ("2.13", (2, 13)), (" 1.0 ", (1, 0)), ("0.1", (0, 1))],
)
def test_parse_version_accepts_major_minor(text, expected):
    assert parse_version(text) == expected


@pytest.mark.unit
@pytest.mark.parametrize("text", ["1", "1.0.0", "x.y", "", "1.", ".1", "1,0", "v1.0", "1.0b"])
def test_parse_version_rejects_malformed(text):
    with pytest.raises(ImportVersionError):
        parse_version(text)


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, 1.0, 10, ["1", "0"]])
def test_parse_version_rejects_non_strings(value):
    with pytest.raises(ImportVersionError):
        parse_version(value)


@pytest.mark.unit
def test_check_version_defaults_when_absent_and_warns():
    logger = MagicMock()
    assert check_version(None, logger) == SCHEMA_VERSION
    logger.warning.assert_called_once()


@pytest.mark.unit
def test_check_version_defaults_without_a_logger():
    assert check_version(None) == SCHEMA_VERSION


@pytest.mark.unit
def test_check_version_accepts_current():
    logger = MagicMock()
    assert check_version(SCHEMA_VERSION, logger) == SCHEMA_VERSION
    logger.info.assert_not_called()
    logger.warning.assert_not_called()


@pytest.mark.unit
def test_check_version_accepts_newer_minor_with_an_info_note():
    logger = MagicMock()
    assert check_version("1.7", logger) == "1.7"
    logger.info.assert_called_once()


@pytest.mark.unit
def test_check_version_accepts_newer_minor_without_a_logger():
    assert check_version("1.7") == "1.7"


@pytest.mark.unit
def test_check_version_accepts_older_major():
    assert check_version("0.9") == "0.9"


@pytest.mark.unit
def test_check_version_rejects_newer_major():
    with pytest.raises(ImportVersionError) as excinfo:
        check_version(f"{SUPPORTED_MAJOR + 1}.0")
    assert "newer than the supported major" in str(excinfo.value)


@pytest.mark.unit
def test_check_version_rejects_malformed():
    with pytest.raises(ImportVersionError):
        check_version("1.0.0")
