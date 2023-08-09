"""This module allows pytest to perform unit testing."""


from os.path import join
from random import random

import pytest

from ansys.dynamicreporting.core import Report, Service, docker_support
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL
from ansys.dynamicreporting.core.exceptions import (
    AlreadyConnectedError,
    CannotCreateDatabaseError,
    ConnectionToServiceError,
    DatabaseDirNotProvidedError,
    MissingReportError,
    MissingSession,
    NotValidServer,
    PyadrException,
)
from ansys.dynamicreporting.core.utils import report_remote_server

from .conftest import cleanup_docker


@pytest.mark.ado_test
def test_unit_nexus() -> bool:
    a = Service()
    success = False
    try:
        a.start()
    except DatabaseDirNotProvidedError:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_nexus_nosession(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile7.txt")
    a = Service(logfile=logfile)
    success = False
    try:
        _ = a.session_guid
    except MissingSession:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_nodbpath(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile8.txt")
    a = Service(logfile=logfile, db_directory="aaa")
    success = False
    try:
        _ = a.start(create_db=True)
    except CannotCreateDatabaseError:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_nexus_stop(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile.txt")
    a = Service(logfile=logfile)
    a.stop()
    f = open(logfile)
    assert "There is no service connected to the current session" in f.read()


@pytest.mark.ado_test
def test_unit_nexus_connect(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile_2.txt")
    a = Service(logfile=logfile)
    success = False
    try:
        a.connect(url=f"http://localhost:{8000 + int(random() * 4000)}")
    except NotValidServer:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_createitem() -> bool:
    a = Service()
    a.serverobj = report_remote_server.Server()
    valid = False
    try:
        a.create_item()
    except Exception:
        valid = True
    assert valid


@pytest.mark.ado_test
def test_unit_query() -> bool:
    a = Service()
    a.serverobj = report_remote_server.Server()
    query_list = a.query()
    assert query_list == []


@pytest.mark.ado_test
def test_unit_invalidqueryone() -> bool:
    a = Service()
    valid = a.__check_filter__("F|i_type|cont|html;")
    assert valid is False


@pytest.mark.ado_test
def test_unit_invalidquerytwo() -> bool:
    a = Service()
    valid = a.__check_filter__("A|b_type|cont|html;")
    assert valid is False


@pytest.mark.ado_test
def test_unit_delete_invalid(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile_4.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    success = False
    try:
        a.delete("aa")
    except TypeError:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_delete() -> bool:
    a = Service()
    a.serverobj = report_remote_server.Server()
    ret = a.delete([])
    assert ret is None


@pytest.mark.ado_test
def test_unit_get_report(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile_5.txt")
    a = Service(logfile=logfile)
    success = False
    try:
        _ = a.get_report(report_name="Abc")
    except ConnectionToServiceError:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_get_listreport(request) -> bool:
    logfile = join(request.fspath.dirname, "outfile_9.txt")
    a = Service(logfile=logfile)
    success = False
    try:
        _ = a.get_list_reports()
    except ConnectionToServiceError:
        success = True
    assert success


@pytest.mark.ado_test
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
    success = False
    try:
        _ = adr_service_create.start(
            create_db=True,
            exit_on_close=True,
            delete_db=True,
        )
    except AlreadyConnectedError:
        success = True
    assert success


def test_create_on_existing(request, get_exec) -> bool:
    db_dir = join(join(request.fspath.dirname, "test_data"), "query_db")
    if get_exec != "":
        tmp_adr = Service(ansys_installation=get_exec, db_directory=db_dir)
    else:
        cleanup_docker(request)
        tmp_adr = Service(
            ansys_installation="docker", docker_image=DOCKER_DEV_REPO_URL, db_directory=db_dir
        )
    success = False
    try:
        _ = tmp_adr.start(create_db=True)
    except CannotCreateDatabaseError:
        success = True
    assert success


@pytest.mark.ado_test
def test_stop_before_starting(adr_service_create) -> bool:
    success = adr_service_create.stop()
    assert success is None


def test_get_sessionid(adr_service_create) -> bool:
    session_id = adr_service_create.start(create_db=True, delete_db=True, exit_on_close=True)
    assert session_id == adr_service_create.session_guid


@pytest.mark.ado_test
def test_query_sessions(adr_service_query) -> bool:
    len_queried = len(adr_service_query.query(query_type="Session"))
    adr_service_query.stop()
    assert 3 == len_queried


@pytest.mark.ado_test
def test_query_dataset(adr_service_query) -> bool:
    len_queried = len(adr_service_query.query(query_type="Dataset"))
    adr_service_query.stop()
    assert 4 == len_queried


def test_query_table(adr_service_query) -> bool:
    all_items = adr_service_query.query(query_type="Item")
    only_table = [x for x in all_items if x.type == "table"]
    adr_service_query.stop()
    assert 1 == len(only_table)


@pytest.mark.ado_test
def test_delete_item(adr_service_query) -> bool:
    only_text = adr_service_query.query(query_type="Item", filter="A|i_type|cont|html")
    adr_service_query.delete(only_text)
    newly_items = adr_service_query.query(query_type="Item", filter="A|i_type|cont|html")
    adr_service_query.stop()
    assert len(newly_items) == 0


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
    success = False
    try:
        adr_service_create.visualize_report()
    except ConnectionToServiceError:
        success = True
    assert success


def test_vis_report_name(adr_service_query) -> bool:
    success = False
    try:
        _ = adr_service_query.visualize_report(report_name="Not existing")
    except MissingReportError:
        success = True
    adr_service_query.stop()
    assert success


@pytest.mark.ado_test
def test_connect_to_running(adr_service_query, request, get_exec) -> bool:
    # Connect to a running service and make sure you can access the same dataset
    db_dir = join(join(request.fspath.dirname, "test_data"), "query_db")
    all_items = adr_service_query.query(query_type="Item")
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
        )
    else:
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
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


@pytest.mark.ado_test
def test_exception() -> bool:
    a = PyadrException()
    succ = a.__str__() == "An error occurred."
    a.detail = ""
    succ_two = a.__str__() == ""
    assert succ and succ_two
