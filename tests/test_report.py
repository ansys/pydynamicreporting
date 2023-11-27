import os

import pytest

from ansys.dynamicreporting.core import Report, Service
from ansys.dynamicreporting.core.utils import report_remote_server


@pytest.mark.ado_test
def test_geturl_report(adr_service_query) -> bool:
    my_report = adr_service_query.get_report(report_name="My Top Report")
    url = my_report.get_url()
    adr_service_query.stop()
    assert "http:" in url


def test_visualize_report(adr_service_query) -> bool:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        my_report.visualize()
        my_report.visualize(new_tab=True)
        success = True
    except SyntaxError:
        success = False
    adr_service_query.stop()
    assert success is True


def test_iframe_report(adr_service_query) -> bool:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        _ = my_report.get_iframe()
        success = True
    except SyntaxError:
        success = False
    adr_service_query.stop()
    assert success is True


@pytest.mark.ado_test
def test_unit_report_url(request) -> bool:
    logfile = os.path.join(request.fspath.dirname, "outfile_3.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    myreport = Report(service=a)
    _ = myreport.get_url()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "" in line:
                err_msg = True
    assert err_msg


def test_unit_report_visualize(request) -> bool:
    logfile = os.path.join(request.fspath.dirname, "outfile_6.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    myreport = Report(service=a)
    myreport.visualize()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "Error: could not obtain url for report" in line:
                err_msg = True
    assert err_msg


@pytest.mark.ado_test
def test_unit_report_iframe(request) -> bool:
    logfile = os.path.join(request.fspath.dirname, "outfile_6.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    myreport = Report(service=a)
    _ = myreport.get_iframe()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "No connection to any server" in line:
                err_msg = True
    assert err_msg


@pytest.mark.ado_test
def test_unit_no_url(request) -> bool:
    logfile = os.path.join(request.fspath.dirname, "outfile_6.txt")
    a = Service(logfile=logfile)
    a.serverobj = report_remote_server.Server()
    myreport = Report(service=a)
    _ = myreport.get_url()
    err_msg = False
    with open(logfile) as file:
        for line in file:
            if "No connection to any server" in line:
                err_msg = True
    assert err_msg


@pytest.mark.ado_test
def test_save_as_pdf(adr_service_query, request, get_exec) -> bool:
    exec_basis = get_exec
    if exec_basis:
        success = False
        try:
            my_report = adr_service_query.get_report(report_name="My Top Report")
            pdf_file = os.path.join(request.fspath.dirname, "again_mytest")
            success = my_report.export_pdf(file_name=pdf_file)
        except Exception:
            success = False
        adr_service_query.stop()
    else:  # If no local installation, then skip this test
        success = True
    assert success is True


@pytest.mark.ado_test
def test_save_as_html(adr_service_query) -> bool:
    success = False
    try:
        my_report = adr_service_query.get_report(report_name="My Top Report")
        success = my_report.export_html(directory_name="htmltest_again")
    except Exception:
        success = False
    adr_service_query.stop()
    assert success is True
