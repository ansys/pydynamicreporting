import logging
from os import environ
from random import randint
import re
import uuid

import pytest
import requests

from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.constants import DOCKER_DEV_REPO_URL
from ansys.dynamicreporting.core.utils import exceptions as e
from ansys.dynamicreporting.core.utils import report_objects as ro
from ansys.dynamicreporting.core.utils import report_remote_server as r
from ansys.dynamicreporting.core.utils.exceptions import BadRequestError, DBCreationFailedError


def test_copy_item(adr_service_query, tmp_path, get_exec) -> None:
    db_dir = tmp_path / "test_copy_item"
    port = 8000 + randint(0, 3999)

    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=str(db_dir),
            port=port,
        )
    else:
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=str(db_dir),
            port=port,
        )

    tmp_adr.start(create_db=True, exit_on_close=True, delete_db=True)
    try:
        s = tmp_adr.serverobj
        success = s.copy_items(
            source=adr_service_query.serverobj,
            obj_type="item",
            progress=False,
            progress_qt=False,
        )
    except Exception:
        success = False
    finally:
        tmp_adr.stop()
    assert success


@pytest.mark.ado_test
def test_start_stop(tmp_path, get_exec) -> None:
    db_dir = tmp_path / "test_start_stop"
    port_r = 8000 + randint(0, 3999)
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=port_r,
        )
    else:
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
    except Exception:
        succ = False
    assert succ


def test_validate_existing(adr_service_query) -> None:
    succ = True
    try:
        _ = r.validate_local_db(db_dir=adr_service_query._db_directory, version_check=True)
    except Exception:
        succ = False
    assert succ


def test_fail_newdb(tmp_path, get_exec) -> None:
    db_dir = tmp_path / "test_fail_newdb"
    db_dir.mkdir(parents=True)  # create beforehand
    port_r = 8000 + randint(0, 3999)
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=port_r,
        )
    else:
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=port_r,
        )
    succ = False
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


def test_none_url() -> None:
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


def test_server_token(adr_service_create) -> None:
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
    assert succ and succ_two and succ_three and succ_four and succ_five


@pytest.mark.ado_test
def test_server_guids(adr_service_create) -> None:
    s = adr_service_create.serverobj
    succ = s.get_user_groups() == ["nexus"]
    succ_two = s.get_object_guids() == []
    s.get_object_from_guid(guid=str(uuid.uuid1()))
    succ_three = s.get_file(obj=None, fileobj=None) == requests.codes.service_unavailable
    assert succ and succ_two and succ_three


@pytest.mark.ado_test
def test_default() -> None:
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
def test_template() -> None:
    s = r.Server()
    assert isinstance(s.create_template(parent=s.create_template()), ro.basicREST)


@pytest.mark.ado_test
def test_url_query() -> None:
    s = r.Server()
    s.cur_url = "http://localhost:8000"
    assert "&a=1&b=2" in s.build_url_with_query(
        report_guid=str(uuid.uuid1()), query={"a": 1, "b": 2}
    )


# todo: Error: Unable to delete the database: /tmp/pytest-of-runner/pytest-0/test_delete_db0/test_delete_db is not a database dir
def test_delete_db(tmp_path, get_exec) -> None:
    db_dir = tmp_path / "test_delete_db"
    port = 8000 + randint(0, 3999)

    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=str(db_dir),
            port=port,
        )
    else:
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=str(db_dir),
            port=port,
        )
    r.create_new_local_database(
        parent=None,
        directory=db_dir,
        exec_basis=tmp_adr._ansys_installation,
        ansys_version=tmp_adr._ansys_version,
    )
    try:
        r.delete_database(db_dir=db_dir)
        succ = True
    except Exception:
        succ = False
    assert succ


def test_export_html(adr_service_query) -> None:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        success = True
    except SyntaxError:
        success = False
    s = adr_service_query.serverobj
    s.export_report_as_html(report_guid=my_report.report.guid, directory_name="htmltest")
    assert success is True


@pytest.mark.ado_test
def test_export_pdf(adr_service_query, get_exec) -> None:
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
    assert success is True


@pytest.mark.ado_test
def test_export_pdf_with_filter(adr_service_query, get_exec) -> None:
    exec_basis = get_exec
    item_filter = "A|i_type|cont|image;"
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
            item_filter=item_filter,
        )
    else:
        # If no local installation, then you can not run the routine for pdf conversion. OSError expected.
        try:
            s.export_report_as_pdf(
                report_guid=my_report.report.guid, file_name="mytest", item_filter=item_filter
            )
        except OSError:
            success = True
    assert success is True


@pytest.mark.ado_test
def test_export_pptx_error(adr_service_query) -> None:
    my_report = adr_service_query.get_report(report_name="My Top Report")
    s = adr_service_query.serverobj
    success = False
    try:
        # exports the root report instead of the pptx link.
        s.export_report_as_pptx(report_guid=my_report.report.guid, file_name="mypresentation")
    except Exception:
        success = True
    assert success is True


def test_get_pptx(adr_service_query, tmp_path) -> None:
    db_dir = tmp_path / "test_get_pptx"
    my_report = adr_service_query.get_report(report_name="My Top Report")
    s = adr_service_query.serverobj
    try:
        # scrape all pptx reports from root report
        s.get_pptx_from_report(report_guid=my_report.report.guid, directory_name=db_dir, query=None)
    except Exception:
        success = False
    else:
        success = True
    assert success is True


def test_copy_template(adr_service_query, tmp_path, get_exec) -> None:
    db_dir = tmp_path / "test_copy_template"
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=8000 + randint(0, 3999),
        )
    else:
        tmp_adr = Service(
            ansys_installation="docker",
            docker_image=DOCKER_DEV_REPO_URL,
            db_directory=db_dir,
            port=8000 + randint(0, 3999),
        )
    tmp_adr.start(create_db=True, exit_on_close=True, delete_db=True)
    s = tmp_adr.serverobj
    succ = s.copy_items(
        source=adr_service_query.serverobj, obj_type="template", progress=False, progress_qt=False
    )
    tmp_adr.stop()
    assert succ


def test_groups(adr_service_create) -> None:
    s = adr_service_create.serverobj
    succ = s.get_auth() == (b"nexus", b"cei")
    succ_two = s.get_user_groups() == ["nexus"]
    s.cur_username = ""
    succ_three = s.get_user_groups() == []
    s.cur_username = "nexus"
    assert succ and succ_two and succ_three


def test_acls_start(tmp_path, get_exec) -> None:
    db_dir = tmp_path / "test_acls_start"
    port_r = 8000 + randint(0, 3999)
    if get_exec != "":
        tmp_adr = Service(
            ansys_installation=get_exec,
            db_directory=db_dir,
            port=port_r,
        )
    else:
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
    assert succ and succ_two and succ_three


@pytest.mark.ado_test
def test_get_templates_as_json(adr_service_create) -> bool:
    server = adr_service_create.serverobj

    # Level 0
    template_01 = server.create_template(name="A", parent=None, report_type="Layout:basic")
    server.put_objects(template_01)

    # Level 1
    template_02 = server.create_template(name="B", parent=template_01, report_type="Layout:basic")
    template_04 = server.create_template(name="C", parent=template_01, report_type="Layout:basic")
    server.put_objects([template_02, template_04])

    # Level 2
    template_03 = server.create_template(name="D", parent=template_02, report_type="Layout:basic")
    server.put_objects(template_03)

    # Updates the reports with change in children
    server.put_objects(template_02)
    server.put_objects(template_01)

    templates = server.get_objects(objtype=ro.TemplateREST)
    for template in templates:
        if template.master:
            root_guid = template.guid
            break

    templates_json = server.get_templates_as_json(root_guid)
    assert len(templates_json) == 4
    assert templates_json["Template_0"]["name"] == "A"
    assert templates_json["Template_0"]["report_type"] == "Layout:basic"
    assert templates_json["Template_0"]["tags"] == ""
    assert templates_json["Template_0"]["params"] == {}
    assert templates_json["Template_0"]["sort_selection"] == ""
    assert templates_json["Template_0"]["item_filter"] == ""
    assert templates_json["Template_0"]["parent"] is None
    assert templates_json["Template_0"]["children"] == ["Template_1", "Template_2"]
    server.del_objects(templates)


@pytest.mark.ado_test
def test_load_templates(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            "name": "A",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": None,
            "children": ["Template_1", "Template_2"],
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    server.load_templates(templates_json)
    templates = server.get_objects(objtype=ro.TemplateREST)
    assert len(templates) == 4

    template_guid_map = {}
    for template in templates:
        template_guid_map[template.guid] = template.name

    for template in templates:
        if template.name == "A":
            assert template.report_type == "Layout:basic"
            assert template.tags == ""
            assert template.get_params() == {}
            assert template.get_property() == {}
            assert template.get_sort_fields() == []
            assert template.get_sort_selection() == ""
            assert template.item_filter == ""
            assert template.get_filter_mode() == "items"
            assert template.parent is None
            children = []
            for child in template.children:
                children.append(template_guid_map[child])
            assert children == ["B", "C"]
            break
    server.del_objects(templates)


@pytest.mark.ado_test
def test_check_templates_id_name(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "WRONG_NAME": {  # Error
            "name": "A",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": None,
            "children": ["Template_1", "Template_2"],
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    with pytest.raises(
        e.TemplateEditorJSONLoadingError,
        match="The loaded JSON file has an invalid template name: 'WRONG_NAME' as the key.\n"
        "Please note that the naming convention is 'Template_{NONE_NEGATIVE_NUMBER}'",
    ):
        server.load_templates(templates_json)


@pytest.mark.ado_test
def test_check_templates_parent_name(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            "name": "A",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": None,
            "children": ["Template_1", "Template_2"],
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "WRONG_NAME",  # Error
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    with pytest.raises(
        e.TemplateEditorJSONLoadingError,
        match=(
            "The loaded JSON file has an invalid template name: 'WRONG_NAME' "
            "that does not have the correct name convection under the key: 'parent' of 'Template_1'\n"
            "Please note that the naming convention is 'Template_{NONE_NEGATIVE_NUMBER}'"
        ),
    ):
        server.load_templates(templates_json)
    templates = server.get_objects(objtype=ro.TemplateREST)
    server.del_objects(templates)


@pytest.mark.ado_test
def test_check_templates_children_name(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            "name": "A",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": None,
            "children": ["Template_1", "WRONG_NAME"],  # Error
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    with pytest.raises(
        e.TemplateEditorJSONLoadingError,
        match=(
            "The loaded JSON file has an invalid template name: 'WRONG_NAME' "
            "that does not have the correct name convection under the key: 'children' of 'Template_0'\n"
            "Please note that the naming convention is 'Template_{NONE_NEGATIVE_NUMBER}'"
        ),
    ):
        server.load_templates(templates_json)


@pytest.mark.ado_test
def test_check_templates_missing_necessary_key(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            # Missing name
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": None,
            "children": ["Template_1", "Template_2"],
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    with pytest.raises(
        e.TemplateEditorJSONLoadingError,
        match=(
            "The loaded JSON file is missing a necessary key: 'name'\n"
            "Please check the entries under 'Template_0'."
        ),
    ):
        server.load_templates(templates_json)


class CapturingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.records = []  # Store log records

    def emit(self, record):
        self.records.append(self.format(record))  # Store formatted log message

    def get_recent_warnings(self):
        # Return the most recent warning and higher-level messages
        return [
            record for record in self.records if record.startswith("WARNING") or "WARNING" in record
        ]


@pytest.mark.ado_test
def test_check_templates_extra_keys_with_logger(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            "name": "A",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": None,
            "children": ["Template_1", "Template_2"],
            "extra_key": "",  # Extra key
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }

    capture_handler = CapturingHandler()
    formatter = logging.Formatter("%(levelname)s - %(message)s")
    capture_handler.setFormatter(formatter)
    adr_service_create.logger.setLevel(logging.WARNING)
    adr_service_create.logger.addHandler(capture_handler)

    server.load_templates(templates_json, adr_service_create.logger)

    recent_warnings = capture_handler.get_recent_warnings()
    assert (
        recent_warnings[-1]
        == "WARNING - There are some extra keys under 'Template_0': ['extra_key']"
    )


@pytest.mark.ado_test
def test_check_templates_report_type(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            "name": "A",
            "report_type": "Layout:WRONG",  # Error
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": None,
            "children": ["Template_1", "Template_2"],
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    with pytest.raises(
        e.TemplateEditorJSONLoadingError,
        match=("The loaded JSON file has an invalid 'report_type' value: 'Layout:WRONG'"),
    ):
        server.load_templates(templates_json)


@pytest.mark.ado_test
def test_check_templates_item_filter_parts(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            "name": "A",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "A|d_name|cont;",  # Error
            "parent": None,
            "children": ["Template_1", "Template_2"],
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    with pytest.raises(
        e.TemplateEditorJSONLoadingError,
        match=(
            "The loaded JSON file does not follow the correct item_filter convention!\n"
            "Each part should be divided by '|', while the input is 'A|d_name|cont' under 'Template_0', which does not have 4 '|'s"
        ),
    ):
        server.load_templates(templates_json)


@pytest.mark.ado_test
def test_check_templates_item_filter_part0(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            "name": "A",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "W|d_name|cont|12-10.2_2.38.case;",  # Error
            "parent": None,
            "children": ["Template_1", "Template_2"],
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    with pytest.raises(
        e.TemplateEditorJSONLoadingError,
        match=(
            "The loaded JSON file does not follow the correct item_filter convention!\n"
            "The first part of the filter can only be 'A' or 'O', while the first part of the input is 'W' under 'Template_0'"
        ),
    ):
        server.load_templates(templates_json)


@pytest.mark.ado_test
def test_check_templates_item_filter_part1(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    templates_json = {
        "Template_0": {
            "name": "A",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "A|w_name|cont|12-10.2_2.38.case;",  # Error
            "parent": None,
            "children": ["Template_1", "Template_2"],
        },
        "Template_1": {
            "name": "B",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": ["Template_3"],
        },
        "Template_3": {
            "name": "D",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_1",
            "children": [],
        },
        "Template_2": {
            "name": "C",
            "report_type": "Layout:basic",
            "tags": "",
            "params": {},
            "sort_selection": "",
            "item_filter": "",
            "parent": "Template_0",
            "children": [],
        },
    }
    with pytest.raises(
        e.TemplateEditorJSONLoadingError,
        match=re.escape(
            "The loaded JSON file does not follow the correct item_filter convention!\n"
            "The second part of the filter can only be '['i_', 's_', 'd_', 't_']', while the second part of the input is 'w_name' under 'Template_0'"
        ),
    ):
        server.load_templates(templates_json)


@pytest.mark.ado_test
def test_put_objects_bad_request_tmp_name(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_template = server.create_template(name="testing" * 255, report_type="Layout:box")
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure name has no more than 255 characters.")
    ):
        server.put_objects(test_template)


@pytest.mark.ado_test
def test_put_objects_bad_request_tmp_tags(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_template = server.create_template(name="testing", report_type="Layout:box")
    test_template.tags = "testing" * 256
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure tags has no more than 256 characters.")
    ):
        server.put_objects(test_template)


@pytest.mark.ado_test
def test_put_objects_bad_request_tmp_item_filter(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_template = server.create_template(name="testing", report_type="Layout:box")
    test_template.item_filter = "testing" * 1024
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure item_filter has no more than 1024 characters.")
    ):
        server.put_objects(test_template)


@pytest.mark.ado_test
def test_put_objects_bad_request_itm_name(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_item = server.create_item(name="testing" * 255)
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure name has no more than 255 characters.")
    ):
        server.put_objects(test_item)


@pytest.mark.ado_test
def test_put_objects_bad_request_itm_source(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_item = server.create_item(name="testing")
    test_item.source = "testing" * 80
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure source has no more than 80 characters.")
    ):
        server.put_objects(test_item)


@pytest.mark.ado_test
def test_put_objects_bad_request_itm_type(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_item = server.create_item(name="testing")
    test_item.type = "testing" * 16
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure type has no more than 16 characters.")
    ):
        server.put_objects(test_item)


@pytest.mark.ado_test
def test_put_objects_bad_request_ds_filename(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_dataset = server.get_default_dataset()
    test_dataset.filename = "testing" * 256
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure filename has no more than 256 characters.")
    ):
        server.put_objects(test_dataset)


@pytest.mark.ado_test
def test_put_objects_bad_request_ds_dirname(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_dataset = server.get_default_dataset()
    test_dataset.dirname = "testing" * 256
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure dirname has no more than 256 characters.")
    ):
        server.put_objects(test_dataset)


@pytest.mark.ado_test
def test_put_objects_bad_request_ds_format(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_dataset = server.get_default_dataset()
    test_dataset.format = "testing" * 50
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure format has no more than 50 characters.")
    ):
        server.put_objects(test_dataset)


@pytest.mark.ado_test
def test_put_objects_bad_request_se_hostname(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_session = server.get_default_session()
    test_session.hostname = "testing" * 50
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure hostname has no more than 50 characters.")
    ):
        server.put_objects(test_session)


@pytest.mark.ado_test
def test_put_objects_bad_request_se_platform(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_session = server.get_default_session()
    test_session.platform = "testing" * 50
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure platform has no more than 50 characters.")
    ):
        server.put_objects(test_session)


@pytest.mark.ado_test
def test_put_objects_bad_request_se_application(adr_service_create) -> bool:
    server = adr_service_create.serverobj
    test_session = server.get_default_session()
    test_session.application = "testing" * 40
    with pytest.raises(
        BadRequestError, match=re.escape("Ensure application has no more than 40 characters.")
    ):
        server.put_objects(test_session)
