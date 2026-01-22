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

import pickle  # nosec B403
import uuid

import pytest

from ansys.dynamicreporting.core.utils import extremely_ugly_hacks as ex


@pytest.mark.ado_test
def test_unpicke() -> None:
    assert ex.safe_unpickle(input_data="!@P{}", item_type="tree") == "!@P{}"


@pytest.mark.ado_test
def test_unpickle_empty() -> None:
    assert ex.safe_unpickle(input_data="") == ""


@pytest.mark.ado_test
def test_unpickle_bytes() -> None:
    assert ex.safe_unpickle(input_data=pickle.dumps("!@P{}")) == "!@P{}"


@pytest.mark.ado_test
def test_unpickle_none() -> None:
    assert ex.safe_unpickle(input_data=None) is None


@pytest.mark.ado_test
def test_unpickle_nobeg() -> None:
    assert ex.safe_unpickle(input_data=pickle.dumps("abcde")) == "abcde"


@pytest.mark.ado_test
def test_unpickle_error() -> None:
    success = False
    try:
        ex.safe_unpickle(input_data="abcde")
    except Exception as e:
        success = "Unable to decode the payload" in str(e)
    assert success


@pytest.mark.ado_test
def test_rec_tree() -> None:
    test = ex.reconstruct_tree_item(
        [{b"a": 1}, {1: b"b"}, {1: uuid.uuid1()}, {1: [{"a": "b"}, {}]}]
    )
    assert len(test) == 4


@pytest.mark.ado_test
def test_rec_int_data() -> None:
    test = ex.reconstruct_international_text(data={"a": [1, 2, 3], "b": 2})
    assert test == {"a": [1, 2, 3], "b": 2}
