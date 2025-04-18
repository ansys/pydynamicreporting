from os.path import join

import numpy as np
import pytest

from ansys.dynamicreporting.core.utils import report_utils as ru


def return_file_paths(request) -> list:
    test_path = join(request.fspath.dirname, "test_data")
    image_file = join(test_path, "aa_00_0_alpha1.png")
    scene_file = join(join(test_path, "scenes"), "scene.avz")
    ens_file = join(test_path, "dam_break.ens")
    evsn_file = join(test_path, "ami.evsn")
    scdoc_file = join(test_path, "viewer_test.scdoc")
    csf_file = join(test_path, "flow2d.csf")
    return [image_file, scene_file, ens_file, evsn_file, scdoc_file, csf_file]


@pytest.mark.ado_test
def test_encode_decode() -> None:
    mys = "D:\tmp\\My String()"
    encoded_s = ru.encode_url(mys)
    decoded_s = ru.decode_url(encoded_s)
    assert mys == decoded_s


@pytest.mark.ado_test
def test_is_enve_image(request) -> None:
    img = ru.is_enve_image_or_pil(return_file_paths(request)[0])
    assert img is True


@pytest.mark.ado_test
def test_enve_image_to_data(request) -> None:
    img_data = ru.image_to_data(return_file_paths(request)[0])
    assert "file_data" in img_data.keys()


@pytest.mark.ado_test
def test_env_arch() -> None:
    local_arch = ru.enve_arch()
    assert ("win" in local_arch) or ("lin" in local_arch)


def test_enve_home() -> None:
    enve_home = ru.enve_home()
    assert "ansys" in enve_home


@pytest.mark.ado_test
def test_ceiversion_nexus_suffix() -> None:
    suffix = ru.ceiversion_nexus_suffix()
    try:
        int_suffix = int(suffix)
        success = True
    except Exception:
        success = False
    assert success and int_suffix / 100 < 10


@pytest.mark.ado_test
def test_ceiversion_apex_suffix() -> None:
    suffix = ru.ceiversion_apex_suffix()
    try:
        int_suffix = int(suffix)
        success = True
    except Exception:
        success = False
    assert success and int_suffix / 100 < 10


@pytest.mark.ado_test
def test_ceiversion_ensight_suffix() -> None:
    suffix = ru.ceiversion_ensight_suffix()
    try:
        int_suffix = int(suffix)
        success = True
    except Exception:
        success = False
    assert success and int_suffix / 100 < 10


@pytest.mark.ado_test
def test_platform_encoding() -> None:
    encode = ru.platform_encoding()
    assert encode == "mbcs" or encode == "utf-8"


@pytest.mark.ado_test
def test_local_to_utf8() -> None:
    testone = ru.local_to_utf8(v=b"33")
    testtwo = ru.local_to_utf8(v=b"33", use_unicode=True)
    assert type(testone) is bytes and type(testtwo) is str


@pytest.mark.ado_test
def test_utf8_to_local() -> None:
    assert type(ru.utf8_to_local(v="rr")) is bytes


@pytest.mark.ado_test
def test_utf8_to_unicode() -> None:
    assert type(ru.utf8_to_unicode(v="rr")) is str and type(ru.utf8_to_unicode(v=b"rr"))


@pytest.mark.ado_test
def test_to_local_8bit() -> None:
    assert type(ru.to_local_8bit(v="rr")) is str


@pytest.mark.ado_test
def test_from_local_8bit() -> None:
    testone = ru.from_local_8bit(v=b"33")
    testtwo = ru.from_local_8bit(v="33")
    assert type(testone) is str and type(testtwo) is str


@pytest.mark.ado_test
def test_run_web_request(adr_service_query) -> None:
    resp = ru.run_web_request(method="GET", server=adr_service_query.serverobj, relative_url="")
    assert resp.ok is True


@pytest.mark.ado_test
def test_isSQLite3(request) -> None:
    test_path = join(request.fspath.dirname, "test_data")
    slite_file = join(join(test_path, "query_db"), "db.sqlite3")
    assert ru.isSQLite3(slite_file) is True


@pytest.mark.ado_test
def test_no_isSQLite3(request) -> None:
    slite_file = return_file_paths(request)[0]
    assert ru.isSQLite3(slite_file) is False


@pytest.mark.ado_test
def test_narray() -> None:
    try:
        a = ru.nexus_array(dtype="u8", shape=(1, 2))
        a.set_shape(value=(2, 3))
        a.dtype = "Q"
        a.from_bytes(value=bytes(0))
        a.set_dtype(value="S4")
        a.set_dtype(value="f8")
        _ = a.count()
        _ = a.element_size()
        _ = a.count(string_size=True)
        a.set_size(shape=(3, 4))
        a.dtype = "S3"
        a.dtype = "f8"
        _ = a.numpy_to_array_type(np_dtype="S3")
        _ = a.numpy_to_na_type(np_dtype="f4")
        _ = a.to_bytes()
        _ = a.to_2dlist()
        _ = a.to_numpy(writeable=False)
        _ = a.to_numpy(writeable=True)
        _ = a.to_json()
        a.dtype = "S4"
        a.from_2dlist(value="0")
        a.from_2dlist(value=[])
        a.from_numpy(value=np.array(object=None, dtype="S2"))
        a.unit_test()
        success = True
    except Exception:
        success = False
    assert success


@pytest.mark.ado_test
def test_narray_index() -> None:
    a = ru.nexus_array()
    mystr = a._index(key="a")
    myint = a._index(key=(1, 1))
    assert mystr == "a" and myint == 2


@pytest.mark.ado_test
def test_narray_getitem() -> None:
    b = ru.nexus_array()
    b.__setitem__(key=0, value=10)
    myval = b.__getitem__(key=0)
    b.set_dtype(value="S4")
    b.__setitem__(key=0, value="a")
    myb = b.__getitem__(key=0)
    assert myval == 10 and type(myb) is bytes


@pytest.mark.ado_test
def test_settings() -> None:
    try:
        _ = ru.Settings(defaults={"a": 1, "b": 2})
        success = True
    except Exception:
        success = False
    assert success


@pytest.mark.ado_test
def test_find_unused_ports() -> None:
    ports = ru.find_unused_ports(count=3)
    single_port = ru.find_unused_ports(start=0, end=9000, count=1, avoid=range(10, 1000))
    succ = len(ru.find_unused_ports(count=0)) <= 1
    succ_two = ru.find_unused_ports(count=0, avoid=range(100000)) == []
    assert len(ports) == 3 and len(single_port) == 1 and succ and succ_two


@pytest.mark.ado_test
def test_is_port_in_use() -> None:
    ret_f = ru.is_port_in_use(port=-34)
    ret_t = ru.is_port_in_use(port=9090)
    ret_less = ru.is_port_in_use(admin_check=True, port=90)
    assert ret_f is False and ret_t is False and ret_less is False


@pytest.mark.ado_test
def test_get_links_from_html() -> None:
    res = ru.get_links_from_html(html="www.mocksite.com")
    assert res == []


@pytest.mark.ado_test
def test_htmlparser() -> None:
    a = ru.HTMLParser()
    a.handle_starttag(tag="a", attrs=[("href", 1)])
    assert a._links == [1]
