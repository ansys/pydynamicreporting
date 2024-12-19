"""This module allows pytest to perform unit testing."""
from pathlib import Path
from random import randint

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
)
from ansys.dynamicreporting.core.utils import report_remote_server


@pytest.mark.ado_test
def test_unit_nexus() -> None:
    a = Service()
    success = False
    try:
        a.start()
    except DatabaseDirNotProvidedError:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_nexus_nosession() -> None:
    logfile = Path(__file__).parent / "outfile7.txt"
    a = Service(logfile=logfile)
    success = False
    try:
        _ = a.session_guid
    except MissingSession:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_nodbpath() -> None:
    logfile = Path(__file__).parent / "outfile8.txt"
    a = Service(logfile=logfile, db_directory="aaa")
    success = False
    try:
        _ = a.start(create_db=True)
    except CannotCreateDatabaseError:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_nexus_stop() -> None:
    logfile = Path(__file__).parent / "outfile.txt"
    a = Service(logfile=logfile)
    a.stop()
    f = open(logfile)
    assert "Error validating the connected service" in f.read()


@pytest.mark.ado_test
def test_unit_nexus_connect() -> None:
    logfile = Path(__file__).parent / "outfile_2.txt"
    a = Service(logfile=logfile)
    success = False
    try:
        a.connect(url=f"http://localhost:{8000 + randint(0, 3999)}")
    except NotValidServer:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_createitem() -> None:
    a = Service()
    a.serverobj = report_remote_server.Server()
    valid = False
    try:
        a.create_item()
    except Exception:
        valid = True
    assert valid


@pytest.mark.ado_test
def test_unit_query() -> None:
    a = Service()
    a.serverobj = report_remote_server.Server()
    query_list = a.query()
    assert query_list == []


@pytest.mark.ado_test
def test_unit_delete_invalid() -> None:
    logfile = Path(__file__).parent / "outfile_4.txt"
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    success = False
    try:
        a.delete("aa")
    except TypeError:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_delete() -> None:
    a = Service()
    a.serverobj = report_remote_server.Server()
    ret = a.delete([])
    assert ret is None


@pytest.mark.ado_test
def test_unit_get_report() -> None:
    logfile = Path(__file__).parent / "outfile_5.txt"
    a = Service(logfile=logfile)
    success = False
    try:
        _ = a.get_report(report_name="Abc")
    except ConnectionToServiceError:
        success = True
    assert success


@pytest.mark.ado_test
def test_unit_get_listreport() -> None:
    logfile = Path(__file__).parent / "outfile_9.txt"
    a = Service(logfile=logfile)
    success = False
    try:
        _ = a.get_list_reports()
    except ConnectionToServiceError:
        success = True
    assert success


@pytest.mark.ado_test
def test_no_directory() -> None:
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


def test_no_docker(tmp_path) -> None:
    try:
        Service(
            ansys_installation="docker",
            docker_image="ghcr.io/ansys-internal/not_existing_docker",
            db_directory=tmp_path / "abc",
        )
        success = True
    except RuntimeError:
        success = False
    assert success is False


def test_connect_to_connected(adr_service_create) -> None:
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


def test_create_on_existing(get_exec) -> None:
    db_dir = Path(__file__).parent / "test_data" / "query_db"
    if get_exec != "":
        tmp_adr = Service(ansys_installation=get_exec, db_directory=db_dir)
    else:
        tmp_adr = Service(
            ansys_installation="docker", docker_image=DOCKER_DEV_REPO_URL, db_directory=db_dir
        )
    success = False
    try:
        _ = tmp_adr.start(create_db=True, error_if_create_db_exists=True)
    except CannotCreateDatabaseError:
        success = True
    assert success


@pytest.mark.ado_test
def test_stop_before_starting(get_exec) -> None:
    db_dir = Path(__file__).parent / "test_data" / "query_db"
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
    success = tmp_adr.stop()
    assert success is None


def test_get_sessionid(adr_service_create) -> None:
    assert (
        isinstance(adr_service_create.session_guid, str)
        and len(adr_service_create.session_guid) > 0
    )


@pytest.mark.ado_test
def test_query_sessions(adr_service_query) -> None:
    len_queried = len(adr_service_query.query(query_type="Session"))
    assert 3 == len_queried


@pytest.mark.ado_test
def test_query_dataset(adr_service_query) -> None:
    len_queried = len(adr_service_query.query(query_type="Dataset"))
    assert 4 == len_queried


def test_query_table(adr_service_query) -> None:
    all_items = adr_service_query.query(query_type="Item")
    only_table = [x for x in all_items if x.type == "table"]
    assert 1 == len(only_table)


@pytest.mark.ado_test
def test_delete_item(adr_service_query) -> None:
    only_text = adr_service_query.query(query_type="Item", filter="A|i_type|cont|html")
    adr_service_query.delete(only_text)
    newly_items = adr_service_query.query(query_type="Item", filter="A|i_type|cont|html")
    assert len(newly_items) == 0


@pytest.mark.ado_test
def test_delete_report(adr_service_query) -> None:
    server = adr_service_query.serverobj
    old_reports = adr_service_query.get_list_reports()
    test_report_name = "To Delete"
    top_report = server.create_template(
        name=test_report_name, parent=None, report_type="Layout:panel"
    )
    top_report.params = '{"HTML": "Hello!!"}'
    server.put_objects(top_report)
    test_report = adr_service_query.get_report(test_report_name)
    adr_service_query.delete([test_report])
    new_reports = adr_service_query.get_list_reports()
    assert len(old_reports) == len(new_reports)


def test_vis_report(adr_service_query) -> None:
    success = False
    try:
        adr_service_query.visualize_report()
        success = True
    except SyntaxError:
        success = False
    assert success is True


def test_vis_report_filtered(adr_service_query) -> None:
    success = False
    try:
        filter = "A|s_guid|cont|15401c2b-089e-11ed-b75d-747827182a82"
        adr_service_query.visualize_report(report_name="My Top Report", filter=filter)
        success = True
    except SyntaxError:
        success = False
    assert success is True


def test_vis_not_running(get_exec) -> None:
    success = False
    try:
        db_dir = Path(__file__).parent / "test_data" / "query_db"
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
        tmp_adr.visualize_report()
    except ConnectionToServiceError:
        success = True
    assert success


def test_vis_report_name(adr_service_query) -> None:
    success = False
    try:
        _ = adr_service_query.visualize_report(report_name="Not existing")
    except MissingReportError:
        success = True
    assert success


@pytest.mark.ado_test
def test_connect_to_running(adr_service_query, get_exec) -> None:
    # Connect to a running service and make sure you can access the same dataset
    db_dir = Path(__file__).parent / "test_data" / "query_db"
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
    assert len(all_items_second) == len(all_items)


def test_get_report_name(adr_service_query) -> None:
    my_report = adr_service_query.get_list_reports()
    assert len(my_report) == 1 and type(my_report[0]) is str


def test_get_report(adr_service_query) -> None:
    my_report = adr_service_query.get_list_reports(r_type="report")
    assert len(my_report) == 1 and type(my_report[0]) is Report


def test_docker_unit() -> None:
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
def test_same_port(tmp_path, get_exec) -> None:
    logfile = tmp_path / "outfile_10.txt"
    db_dir = tmp_path / "sameport"
    db_dir_again = tmp_path / "sameport_again"
    if get_exec != "":
        a = Service(ansys_installation=get_exec, logfile=logfile, db_directory=db_dir)
        b = Service(
            ansys_installation=get_exec, logfile=logfile, db_directory=db_dir_again, port=a._port
        )
    else:
        a = Service(
            ansys_installation="docker", docker_image=DOCKER_DEV_REPO_URL, db_directory=db_dir
        )
        b = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir_again,
            port=a._port,
        )
    _ = a.start(create_db=True)
    _ = b.start(create_db=True)
    a.stop()
    b.stop()
    assert a._port != b._port
