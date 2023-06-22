"""This module allows pytest to perform unit testing."""


from os.path import join
from random import random

from ansys.dynamicreporting.core import Report, Service, docker_support
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL
from ansys.dynamicreporting.core.exceptions import DatabaseDirNotProvidedError, PyadrException
from ansys.dynamicreporting.core.utils import report_remote_server

from .conftest import cleanup_docker


def test_unit_nexus() -> bool:
    valid = False
    a = Service()
    try:
        a.start()
    except TypeError:
        valid = True
    assert valid


def test_unit_nexus_nosession(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile7.txt")
    a = Service(logfile=logfile)
    _ = a.session_guid
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "No session attached to this instance" in line:
                err_msg = True
    assert err_msg


def test_unit_nodbpath(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile8.txt")
    a = Service(logfile=logfile, db_directory="aaa")
    _ = a.start(create_db=True)
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "Error creating the database at the path" in line:
                err_msg = True
    assert err_msg


def test_unit_nexus_stop(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile.txt")
    a = Service(logfile=logfile)
    a.stop()
    f = open(logfile)
    assert "There is no service connected to the current session" in f.read()


def test_unit_nexus_connect(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile_2.txt")
    a = Service(logfile=logfile)
    a.connect(url=f"http://localhost:{8000 + int(random() * 4000)}")
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if " Can not validate dynamic reporting server" in line:
                err_msg = True
    assert err_msg


def test_unit_createitem() -> bool:
    a = Service()
    a.serverobj = report_remote_server.Server()
    valid = False
    try:
        a.create_item()
    except Exception:
        valid = True
    assert valid


def test_unit_query() -> bool:
    a = Service()
    a.serverobj = report_remote_server.Server()
    query_list = a.query()
    assert query_list == []


def test_unit_invalidqueryone() -> bool:
    a = Service()
    valid = a.__check_filter__("F|i_type|cont|html;")
    assert valid is False


def test_unit_invalidquerytwo() -> bool:
    a = Service()
    valid = a.__check_filter__("A|b_type|cont|html;")
    assert valid is False


def test_unit_delete_invalid(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile_4.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    a.delete("aa")
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "Error: passed argument is not a list" in line:
                err_msg = True
    assert err_msg


def test_unit_delete() -> bool:
    a = Service()
    a.serverobj = report_remote_server.Server()
    ret = a.delete([])
    assert ret is False


def test_unit_get_report(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile_5.txt")
    a = Service(logfile=logfile)
    _ = a.get_report(report_name="Abc")
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "Error: no connection to any service" in line:
                err_msg = True
    assert err_msg


def test_unit_get_listreport(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile_9.txt")
    a = Service(logfile=logfile)
    _ = a.get_list_reports()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "Error: no connection to any service" in line:
                err_msg = True
    assert err_msg


def test_no_directory() -> bool:
    success = True
    try:
        Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory="",
        )
        success = True
    except DatabaseDirNotProvidedError:
        success = False
    assert success is False


def test_no_docker(request) -> bool:
    success = True
    try:
        Service(
            ansys_installation="docker",
            docker_image="ghcr.io/ansys-internal/not_existing_docker",
            db_directory=join(join(request.fspath.dirname, "test_data"), "abc"),
        )
        success = True
    except RuntimeError:
        success = False
    assert success is False


def test_start_empty_database(adr_service_create) -> bool:
    session_guid = adr_service_create.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )
    assert session_guid != "0"


def test_set_sessionguid(adr_service_create) -> bool:
    _ = adr_service_create.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )
    canset = True
    try:
        adr_service_create.session_guid = "ABCDE"
    except AttributeError:
        canset = False
    assert canset is False


def test_connect_to_connected(adr_service_create) -> bool:
    adr_service_create.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )
    try_again = adr_service_create.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )
    assert "0" == try_again


def test_create_on_existing(request) -> bool:
    cleanup_docker(request)
    db_dir = join(join(request.fspath.dirname, "test_data"), "query_db")
    tmp_adr = Service(
        ansys_installation="docker", docker_image=DOCKER_DEV_REPO_URL, db_directory=db_dir
    )
    session_id = tmp_adr.start(create_db=True)
    assert session_id == "0"


def test_stop_before_starting(adr_service_create) -> bool:
    success = adr_service_create.stop()
    assert success


def test_get_sessionid(adr_service_create) -> bool:
    session_id = adr_service_create.start(create_db=True, delete_db=True, exit_on_close=True)
    assert session_id == adr_service_create.session_guid


def test_query_sessions(adr_service_query) -> bool:
    len_queried = len(adr_service_query.query(query_type="Session"))
    adr_service_query.stop()
    assert 3 == len_queried


def test_query_dataset(adr_service_query) -> bool:
    len_queried = len(adr_service_query.query(query_type="Dataset"))
    adr_service_query.stop()
    assert 4 == len_queried


def test_query_table(adr_service_query) -> bool:
    all_items = adr_service_query.query(query_type="Item")
    only_table = [x for x in all_items if x.type == "table"]
    adr_service_query.stop()
    assert 1 == len(only_table)


def test_delete_item(adr_service_query) -> bool:
    only_text = adr_service_query.query(query_type="Item", filter="A|i_type|cont|html")
    # a_text = only_text[0].item_text
    ret = adr_service_query.delete(only_text)
    newly_items = adr_service_query.query(query_type="Item", filter="A|i_type|cont|html")
    adr_service_query.stop()
    assert ret and len(newly_items) == 0


def test_vis_report(adr_service_query) -> bool:
    success = False
    try:
        adr_service_query.visualize_report()
        success = True
    except SyntaxError:
        success = False
    adr_service_query.stop()
    assert success is True


def test_vis_report_filtered(adr_service_query) -> bool:
    success = False
    try:
        filter = "A|s_guid|cont|15401c2b-089e-11ed-b75d-747827182a82"
        adr_service_query.visualize_report(report_name="My Top Report", filter=filter)
        success = True
    except SyntaxError:
        success = False
    adr_service_query.stop()
    assert success is True


def test_vis_not_running(adr_service_create) -> bool:
    success = adr_service_create.visualize_report()
    assert success is None


def test_vis_report_name(adr_service_query) -> bool:
    success = adr_service_query.visualize_report(report_name="Not existing")
    adr_service_query.stop()
    assert success is None


def test_connect_to_running(adr_service_query, request) -> bool:
    # Connect to a running service and make sure you can access the same dataset
    all_items = adr_service_query.query(query_type="Item")
    db_dir = join(join(request.fspath.dirname, "test_data"), "query_db")
    tmp_adr = Service(
        ansys_installation="docker",
        docker_image=DOCKER_DEV_REPO_URL,
        db_directory=db_dir,
        port=8000 + int(random() * 4000),
    )
    tmp_adr.connect(url=adr_service_query.url, session=adr_service_query.session_guid)
    all_items_second = tmp_adr.query(query_type="Item")
    adr_service_query.stop()
    tmp_adr.stop()
    assert len(all_items_second) == len(all_items)


def test_get_report_name(adr_service_query) -> bool:
    my_report = adr_service_query.get_list_reports()
    adr_service_query.stop()
    assert len(my_report) == 1 and type(my_report[0]) is str


def test_get_report(adr_service_query) -> bool:
    my_report = adr_service_query.get_list_reports(r_type="report")
    adr_service_query.stop()
    assert len(my_report) == 1 and type(my_report[0]) is Report


def test_docker_unit() -> bool:
    a = docker_support.DockerLauncher()
    succ = a.container_name() is None
    succ_two = a.ansys_version() is None
    succ_three = a.cei_home() is None
    succ_four = a.nexus_directory() is None
    a._cei_home = "/scratch"
    succ_five = False
    try:
        a.copy_from_cei_home_to_host_directory(src="")
    except AttributeError as e:
        succ_five = "has no attribute" in str(e)
    assert succ and succ_two and succ_three and succ_four and succ_five


def test_exception() -> bool:
    a = PyadrException()
    succ = a.__str__() == "An error occurred."
    a.detail = ""
    succ_two = a.__str__() == ""
    assert succ and succ_two
