import datetime
import uuid

import numpy as np
import pytest

from ansys.dynamicreporting.core.utils import encoders as en
from ansys.dynamicreporting.core.utils import report_utils as ru


@pytest.mark.ado_test
def test_payload() -> bool:
    b = en.PayloaddataEncoder()
    res = b.default(obj=ru.nexus_array())
    assert res == [[0.0]]


@pytest.mark.ado_test
def test_base_datetime() -> bool:
    a = en.BaseEncoder()
    assert a.default(obj=datetime.datetime(year=2023, month=4, day=10)) == "2023-04-10T00:00:00"


@pytest.mark.ado_test
def test_uuid() -> bool:
    a = en.PayloaddataEncoder()
    assert type(a.default(obj=uuid.uuid1())) is str


@pytest.mark.ado_test
def test_bytes() -> bool:
    a = en.BaseEncoder()
    mystr = "aa"
    assert a.default(obj=mystr.encode()) == mystr


@pytest.mark.ado_test
def test_dict() -> bool:
    a = en.BaseEncoder()
    mydict = {"a": 1}
    assert a.default(obj=mydict) == mydict


@pytest.mark.ado_test
def test_nparray() -> bool:
    a = en.PayloaddataEncoder()
    assert isinstance(a.default(obj=np.ndarray(shape=(1, 1))), list)
