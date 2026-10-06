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

"""Tests for tag rendering."""

from __future__ import annotations

import pytest

from ansys.dynamicreporting.core.utils.json_import.tags import combine_tags, normalize_tags


@pytest.mark.unit
def test_normalize_tags_none_is_empty():
    assert normalize_tags(None) == ""


@pytest.mark.unit
def test_normalize_tags_passes_through_a_string():
    assert normalize_tags("already=rendered other=tag") == "already=rendered other=tag"
    assert normalize_tags("  padded=value  ") == "padded=value"


@pytest.mark.unit
def test_normalize_tags_renders_a_single_mapping():
    assert normalize_tags({"section": "intro", "dp": 0}) == "section=intro dp=0"


@pytest.mark.unit
def test_normalize_tags_renders_a_list_of_mappings():
    assert normalize_tags([{"section": "intro"}, {"dp": "dp227"}]) == "section=intro dp=dp227"


@pytest.mark.unit
def test_normalize_tags_renders_a_list_of_strings():
    assert normalize_tags(["section=intro", " dp=1 ", ""]) == "section=intro dp=1"


@pytest.mark.unit
def test_normalize_tags_renders_a_bare_scalar():
    assert normalize_tags(42) == "42"
    assert normalize_tags(True) == "True"


@pytest.mark.unit
def test_normalize_tags_skips_none_values_and_entries():
    assert normalize_tags({"keep": "yes", "drop": None}) == "keep=yes"
    assert normalize_tags([{"keep": "yes"}, None]) == "keep=yes"


@pytest.mark.unit
def test_normalize_tags_quotes_whitespace():
    assert normalize_tags({"run name": "thermal run"}) == "'run name'='thermal run'"


@pytest.mark.unit
def test_normalize_tags_renders_scalar_entries_in_a_list():
    assert normalize_tags([7, 8]) == "7 8"


@pytest.mark.unit
def test_normalize_tags_accepts_a_tuple():
    assert normalize_tags(({"a": 1},)) == "a=1"


@pytest.mark.unit
def test_combine_tags_joins_non_empty_parts():
    assert combine_tags("doc=1", [{"section": "intro"}], None, "") == "doc=1 section=intro"


@pytest.mark.unit
def test_combine_tags_of_nothing_is_empty():
    assert combine_tags(None, "", []) == ""
