import pickle
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
