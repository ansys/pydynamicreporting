from os import environ
from os.path import isdir, join
from random import random
import shutil
import uuid

import pytest
import requests

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL
from ansys.dynamicreporting.core.utils import report_objects as ro
from ansys.dynamicreporting.core.utils import report_remote_server as r
from ansys.dynamicreporting.core.utils.exceptions import DBCreationFailedError

from .conftest import cleanup_docker


def test_copy_item(adr_service_query, request, get_exec) -> bool:
    db_dir = join(join(request.fspath.dirname, "test_data"), "newcopy")
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=8000 + int(random() * 4000),
        )
    else:
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=8000 + int(random() * 4000),
        )
    tmp_adr.start(create_db=True, exit_on_close=True, delete_db=True)
    s = tmp_adr.serverobj
    succ = s.copy_items(
        source=adr_service_query.serverobj, obj_type="item", progress=False, progress_qt=False
    )
    adr_service_query.stop()
    tmp_adr.stop()
    if get_exec == "":
        cleanup_docker(request)
    assert succ


@pytest.mark.ado_test
def test_start_stop(request, get_exec) -> bool:
    db_dir = join(join(request.fspath.dirname, "test_data"), "create_delete")
    port_r = 8000 + int(random() * 4000)
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=port_r,
        )
    else:
        cleanup_docker(request)
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=port_r,
        )
    succ = True
    try:
        r.create_new_local_database(
            parent=None,
            directory=db_dir,
            exec_basis=tmp_adr._ansys_installation,
            ansys_version=tmp_adr._ansys_version,
        )
        r.launch_local_database_server(
            parent=None,
            directory=db_dir,
            terminate_on_python_exit=True,
            delete_db_on_python_exit=True,
            use_debug=True,
            exec_basis=tmp_adr._ansys_installation,
            ansys_version=400,
        )
        _ = r.validate_local_db(db_dir=db_dir, version_check=True)
        r.stop_background_local_server(server_dirname=db_dir)
        r.delete_database(db_dir=db_dir)
    except Exception:
        succ = False
    assert succ


def test_validate_existing(adr_service_query) -> bool:
    succ = True
    try:
        _ = r.validate_local_db(db_dir=adr_service_query._db_directory, version_check=True)
        r.stop_background_local_server(server_dirname=adr_service_query._db_directory)
    except Exception:
        succ = False
    assert succ


def test_fail_newdb(request, get_exec) -> bool:
    db_dir = join(join(request.fspath.dirname, "test_data"), "create_twice")
    port_r = 8000 + int(random() * 4000)
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=port_r,
        )
    else:
        cleanup_docker(request)
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=port_r,
        )
    succ = True
    try:
        r.create_new_local_database(
            parent=None,
            directory=db_dir,
            exec_basis=tmp_adr._ansys_installation,
            ansys_version=tmp_adr._ansys_version,
            raise_exception=True,
            run_local=True,
        )
    except DBCreationFailedError as e:
        succ = "Unable to generate a new database by migration" in str(e)
    assert succ


def test_none_url() -> bool:
    a = r.Server()
    succ = a.get_server_name() is None
    succ_two = False
    try:
        a.acls_enabled
    except Exception as e:
        succ_two = "No server URL selected" in str(e)
    succ_three = False
    try:
        a.generate_magic_token()
    except Exception as e:
        succ_three = "No server URL selected" in str(e)
    succ_four = False
    try:
        a._validate_magic_token(token="")
    except Exception as e:
        succ_four = "No server URL selected" in str(e)
    succ_five = False
    try:
        a.magic_token
    except Exception as e:
        succ_five = "No server URL selected" in str(e)
    assert succ and succ_two and succ_three and succ_four and succ_five


def test_server_token(adr_service_create) -> bool:
    _ = adr_service_create.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )
    s = adr_service_create.serverobj
    token = s.generate_magic_token(max_age=10)
    succ = s._validate_magic_token(token=token)
    s.magic_token = token
    succ_two = token in s.get_url_with_magic_token()
    succ_three = s.get_last_error() == ""
    s.set_username(u=s.get_username())
    s.set_password(p=s.get_password())
    succ_four = s.get_server_name() == "ADR Database"
    succ_five = s.stop_server_allowed()
    s.stop_local_server()
    adr_service_create.stop()
    assert succ and succ_two and succ_three and succ_four and succ_five


@pytest.mark.ado_test
def test_server_guids(adr_service_create) -> bool:
    _ = adr_service_create.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )
    s = adr_service_create.serverobj
    succ = s.get_user_groups() == ["nexus"]
    succ_two = s.get_object_guids() == []
    s.get_object_from_guid(guid=str(uuid.uuid1()))
    succ_three = s.get_file(obj=None, fileobj=None) == requests.codes.service_unavailable
    adr_service_create.stop()
    assert succ and succ_two and succ_three


@pytest.mark.ado_test
def test_default() -> bool:
    s = r.Server()
    succ = False
    try:
        s.set_default_dataset(dataset="a")
    except ValueError as e:
        succ = "must be an instance of report_objects.DatasetREST" in str(e)
    s.set_default_dataset(dataset=s.get_default_dataset(), validate_digest=True)
    succ_two = False
    try:
        s.set_default_session(session="a")
    except ValueError as e:
        succ_two = "must be an instance of report_objects.SessionREST" in str(e)
    s.set_default_session(session=s.get_default_session(), validate_digest=True)
    succ_three = isinstance(s.create_item_category(), ro.ItemCategoryREST)
    assert succ and succ_two and succ_three


@pytest.mark.ado_test
def test_template() -> bool:
    s = r.Server()
    assert isinstance(s.create_template(parent=s.create_template()), ro.basicREST)


@pytest.mark.ado_test
def test_url_query() -> bool:
    s = r.Server()
    s.cur_url = "http://localhost:8000"
    assert "&a=1&b=2" in s.build_url_with_query(
        report_guid=str(uuid.uuid1()), query={"a": 1, "b": 2}
    )


def test_stop_local_server(adr_service_query, request) -> bool:
    db_dir = join(join(request.fspath.dirname, "test_data"), "query_db")
    success = False
    try:
        r.stop_background_local_server(server_dirname=db_dir)
        success = True
    except Exception:
        success = False
    assert success


def test_delete_db(adr_service_create, request) -> bool:
    _ = adr_service_create.start(
        create_db=True,
        exit_on_close=True,
        delete_db=False,
    )
    db_dir = adr_service_create._db_directory
    adr_service_create.stop()
    succ = False
    try:
        r.delete_database(db_dir=db_dir)
        succ = True
    except Exception:
        succ = False
    succ_two = False
    try:
        r.delete_database(db_dir=join(request.fspath.dirname, "test_data"))
        succ_two = True
    except Exception:
        succ_two = False
    assert succ and succ_two


def test_export_html(adr_service_query) -> bool:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        success = True
    except SyntaxError:
        success = False
    s = adr_service_query.serverobj
    s.export_report_as_html(report_guid=my_report.report.guid, directory_name="htmltest")
    adr_service_query.stop()
    assert success is True


@pytest.mark.ado_test
def test_export_pdf(adr_service_query, get_exec) -> bool:
    exec_basis = get_exec
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        success = True
    except SyntaxError:
        success = False
    s = adr_service_query.serverobj
    if exec_basis:
        if environ.get("ANSYS_REL_INT_I"):
            ansys_version = int(environ.get("ANSYS_REL_INT_I"))
        else:
            import re

            matches = re.search(r".*v([0-9]{3}).*", exec_basis)
            ansys_version = int(matches.group(1))
        s.export_report_as_pdf(
            report_guid=my_report.report.guid,
            file_name="mytest",
            exec_basis=exec_basis,
            ansys_version=ansys_version,
        )
    else:
        # If no local installation, then you can not run the routine for pdf conversion. OSError expected.
        try:
            s.export_report_as_pdf(report_guid=my_report.report.guid, file_name="mytest")
        except OSError:
            success = True
    adr_service_query.stop()
    assert success is True


@pytest.mark.ado_test
def test_export_pptx(adr_service_query) -> bool:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        success = True
    except SyntaxError:
        success = False
    s = adr_service_query.serverobj
    s.export_report_as_pptx(report_guid=my_report.report.guid, file_name="mypresentation")
    adr_service_query.stop()
    assert success is True


def test_get_pptx(adr_service_query, request) -> bool:
    db_dir = join(request.fspath.dirname, "test_data")
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        success = True
    except SyntaxError:
        success = False
    s = adr_service_query.serverobj
    s.get_pptx_from_report(report_guid=my_report.report.guid, directory_name=db_dir, query=None)
    adr_service_query.stop()
    cleanup_docker(request)
    assert success is True


def test_copy_template(adr_service_query, request, get_exec) -> bool:
    db_dir = join(join(request.fspath.dirname, "test_data"), "newcopytemp")
    if isdir(db_dir):
        shutil.rmtree(db_dir)
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=8000 + int(random() * 4000),
        )
    else:
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=8000 + int(random() * 4000),
        )
    tmp_adr.start(create_db=True, exit_on_close=True, delete_db=True)
    s = tmp_adr.serverobj
    succ = s.copy_items(
        source=adr_service_query.serverobj, obj_type="template", progress=False, progress_qt=False
    )
    adr_service_query.stop()
    tmp_adr.stop()
    if get_exec == "":
        cleanup_docker(request)
    assert succ


def test_groups(adr_service_create, request) -> bool:
    _ = adr_service_create.start(
        create_db=True,
        exit_on_close=True,
        delete_db=True,
    )
    s = adr_service_create.serverobj
    succ = s.get_auth() == (b"nexus", b"cei")
    succ_two = s.get_user_groups() == ["nexus"]
    s.cur_username = ""
    succ_three = s.get_user_groups() == []
    s.cur_username = "nexus"
    adr_service_create.stop()
    assert succ and succ_two and succ_three


def test_acls_start(request, get_exec) -> bool:
    db_dir = join(join(request.fspath.dirname, "test_data"), "create_delete")
    port_r = 8000 + int(random() * 4000)
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=port_r,
        )
    else:
        cleanup_docker(request)
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=port_r,
        )
    r.create_new_local_database(
        parent=None,
        directory=db_dir,
        exec_basis=tmp_adr._ansys_installation,
        ansys_version=tmp_adr._ansys_version,
    )
    succ = False
    try:
        r.launch_local_database_server(parent=None, directory=db_dir, raise_exception=True, aa=True)
    except TypeError as e:
        succ = "Unknown keyword:" in str(e)
    succ_two = not r.launch_local_database_server(
        parent=None, directory=db_dir, raise_exception=False, aa=True
    )
    succ_three = not r.launch_local_database_server(parent=None, directory=db_dir, acls=True)
    r.delete_database(db_dir=db_dir)
    assert succ and succ_two and succ_three
