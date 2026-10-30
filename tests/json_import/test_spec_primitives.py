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

"""Tests for the spec primitives underneath the document parser."""

from __future__ import annotations

import pytest

from ansys.dynamicreporting.core import exceptions
from ansys.dynamicreporting.core.exceptions import ImportItemValidationError
from ansys.dynamicreporting.core.utils import json_item_import
from ansys.dynamicreporting.core.utils.json_item_import.parser import (
    ErrorCollector,
    _matches,
    _type_name,
    apply_spec,
)
from ansys.dynamicreporting.core.utils.json_item_import.spec import (
    ANY,
    FieldSpec,
    coerce_columns,
    coerce_tag_list,
)


def _positive(value):
    """Stand-in for a FieldSpec.validate hook."""
    return None if value > 0 else "must be greater than 0"


# --------------------------------------------------------------------------
# ErrorCollector
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_error_collector_starts_empty():
    errors = ErrorCollector()
    assert errors.problems == []
    errors.raise_if_any()


@pytest.mark.unit
def test_error_collector_records_in_order():
    errors = ErrorCollector()
    errors.add("a", "first")
    errors.add("b", "second")

    assert errors.problems == [("a", "first"), ("b", "second")]


@pytest.mark.unit
def test_error_collector_raises_with_every_problem():
    errors = ErrorCollector()
    errors.add("a", "first")
    errors.add("b", "second")

    with pytest.raises(ImportItemValidationError) as excinfo:
        errors.raise_if_any()
    assert excinfo.value.problems == (("a", "first"), ("b", "second"))
    assert "2 problems found" in str(excinfo.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "name", ["ADRItemImportError", "ImportItemValidationError", "ImportItemVersionError"]
)
def test_import_errors_live_with_the_public_exceptions(name):
    # The import package re-exports the same classes, so either import works.
    error_class = getattr(exceptions, name)
    assert issubclass(error_class, exceptions.ADRException)
    assert getattr(json_item_import, name) is error_class


# --------------------------------------------------------------------------
# Type helpers
# --------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (str, "a string"),
        (int, "an integer"),
        (float, "a number"),
        (list, "an array"),
        (dict, "an object"),
        (ANY, "any value"),
    ],
)
def test_type_name_renders_simple_kinds(kind, expected):
    assert _type_name(kind) == expected


@pytest.mark.unit
def test_type_name_renders_a_tuple_of_kinds():
    rendered = _type_name((str, dict))
    assert "a string" in rendered
    assert "an object" in rendered
    assert " or " in rendered


@pytest.mark.unit
def test_type_name_falls_back_to_the_class_name():
    class Custom:
        pass

    assert _type_name(Custom) == "Custom"


@pytest.mark.unit
def test_matches_accepts_any():
    assert _matches(object(), ANY) is True
    assert _matches(True, ANY) is True


@pytest.mark.unit
def test_matches_rejects_bool_where_int_is_expected():
    assert _matches(True, int) is False
    assert _matches(1, int) is True


@pytest.mark.unit
def test_matches_accepts_bool_when_bool_is_declared():
    assert _matches(True, (int, bool)) is True


# --------------------------------------------------------------------------
# apply_spec edge cases
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_explicit_null_is_replaced_by_the_default():
    errors = ErrorCollector()
    spec = (FieldSpec("opt", str, default="fallback"),)
    values = apply_spec({"opt": None}, spec, "obj", errors)
    assert values["opt"] == "fallback"
    assert errors.problems == []


@pytest.mark.unit
def test_explicit_null_on_a_required_field_is_an_error():
    errors = ErrorCollector()
    spec = (FieldSpec("req", str, required=True),)
    apply_spec({"req": None}, spec, "obj", errors)
    assert errors.problems == [("obj.req", "must not be null")]


@pytest.mark.unit
def test_min_len_message_differs_for_strings_and_arrays():
    errors = ErrorCollector()
    specs = (
        FieldSpec("text", str, min_len=2),
        FieldSpec("array", list, min_len=2),
    )
    apply_spec({"text": "a", "array": [1]}, specs, "obj", errors)
    messages = dict(errors.problems)
    assert "characters" in messages["obj.text"]
    assert "entries" in messages["obj.array"]


@pytest.mark.unit
def test_all_bad_elements_of_a_list_are_reported():
    errors = ErrorCollector()
    specs = (FieldSpec("names", list, item_kind=str),)
    apply_spec({"names": ["ok", 1, 2]}, specs, "obj", errors)
    locations = [location for location, _ in errors.problems]
    assert locations == ["obj.names[1]", "obj.names[2]"]


@pytest.mark.unit
def test_a_coerce_failure_is_reported_at_the_field():
    errors = ErrorCollector()
    specs = (FieldSpec("tags", list, coerce=coerce_tag_list),)
    apply_spec({"tags": [{"a": {"b": 1}}]}, specs, "obj", errors)
    assert errors.problems[0][0] == "obj.tags"


@pytest.mark.unit
def test_a_validate_failure_is_reported_at_the_field():
    errors = ErrorCollector()
    specs = (FieldSpec("count", int, validate=_positive),)
    apply_spec({"count": -1}, specs, "obj", errors)
    assert errors.problems == [("obj.count", "must be greater than 0")]


@pytest.mark.unit
def test_field_location_omits_an_empty_parent():
    errors = ErrorCollector()
    specs = (FieldSpec("app_id", str, required=True),)
    apply_spec({}, specs, "", errors)
    assert errors.problems == [("app_id", "is required")]


# --------------------------------------------------------------------------
# Coercers
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_coerce_tag_list_accepts_scalar_values():
    tags = [{"a": "1"}, {"b": 2, "c": 1.5, "d": True}]
    assert coerce_tag_list(tags) == ({"a": "1"}, {"b": 2, "c": 1.5, "d": True})


@pytest.mark.unit
def test_coerce_tag_list_rejects_a_nested_value():
    with pytest.raises(ValueError) as excinfo:
        coerce_tag_list([{"a": {"b": 1}}])
    assert "'a' must be a string, number, or boolean" in str(excinfo.value)


@pytest.mark.unit
def test_coerce_tag_list_rejects_an_empty_object():
    with pytest.raises(ValueError) as excinfo:
        coerce_tag_list([{}])
    assert "at least one key" in str(excinfo.value)


@pytest.mark.unit
def test_coerce_columns_rejects_a_non_string_type():
    with pytest.raises(ValueError) as excinfo:
        coerce_columns([{"name": "a", "type": 7}])
    assert "'type' must be a string" in str(excinfo.value)


@pytest.mark.unit
def test_coerce_columns_rejects_an_empty_name():
    with pytest.raises(ValueError):
        coerce_columns([{"name": ""}])
