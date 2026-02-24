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

import datetime
import uuid

import numpy as np
import pytest

from ansys.dynamicreporting.core.utils import encoders as en
from ansys.dynamicreporting.core.utils import report_utils as ru


@pytest.mark.ado_test
def test_payload() -> None:
    b = en.PayloaddataEncoder()
    res = b.default(ru.nexus_array())
    assert res == [[0.0]]


@pytest.mark.ado_test
def test_base_datetime() -> None:
    a = en.BaseEncoder()
    assert a.default(datetime.datetime(year=2023, month=4, day=10)) == "2023-04-10T00:00:00"


@pytest.mark.ado_test
def test_uuid() -> None:
    a = en.PayloaddataEncoder()
    assert type(a.default(uuid.uuid1())) is str


@pytest.mark.ado_test
def test_bytes() -> None:
    a = en.BaseEncoder()
    mystr = "aa"
    assert a.default(mystr.encode()) == mystr


@pytest.mark.ado_test
def test_dict() -> None:
    a = en.BaseEncoder()
    mydict = {"a": 1}
    assert a.default(mydict) == mydict


@pytest.mark.ado_test
def test_nparray() -> None:
    a = en.PayloaddataEncoder()
    assert isinstance(a.default(np.ndarray(shape=(1, 1))), list)
