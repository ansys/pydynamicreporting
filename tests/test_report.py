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


@pytest.mark.ado_test
def test_geturl_report_with_filter(adr_service_query) -> bool:
    my_report = adr_service_query.get_report(report_name="My Top Report")
    url = my_report.get_url(filter='"A|b_type|cont|image;"')
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


def test_get_guid(adr_service_query) -> bool:
    my_report = adr_service_query.get_report(report_name="My Top Report")
    guid = my_report.get_guid()
    adr_service_query.stop()
    assert len(guid) > 0


def test_get_report(adr_service_query) -> bool:
    # Run node.js server
    def run_node_server(server_directory):
        """Run the Node.js server located in a different directory."""
        # Run a node.js proxy server using python subprocess module
        import subprocess

        try:
            # access success var
            global success
            # Use the full path to server.js
            server_js_path = os.path.join(server_directory, "index.js")
            print(f"Starting the Node.js server from {server_js_path}...")

            # Run the Node.js server using subprocess
            node_process = subprocess.Popen(
                ["node", server_js_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # Check for exit code
            if node_process.returncode == 0:
                print("Pytest finished successfully")
            else:
                print(f"Pytest failed with exit code {node_process.returncode}")

            # Print the Node.js server output
            for line in node_process.stdout:
                print(line.decode("utf-8").strip())

            # once the server is successfully launch, flip the success flag
            node_process.wait()
            success = True
            node_process.kill()
            print("Node.js server stopped.")
        except Exception as e:
            print(f"Error starting Node.js server: {e}")

    # create index.html file (if not exist) and add <adr-report> component script & tag to fetch the ADR report
    # (assuming running at docker default port 8000)
    def create_or_modify_index_html(directory, html_content):
        """Create an index.html file or insert content if it exists."""
        file_path = os.path.join(directory, "index.html")

        # Check if the index.html file already exists
        if os.path.exists(file_path):
            print(f"'index.html' already exists in {directory}. Modifying it.")
        else:
            print(f"Creating a new 'index.html' in {directory}.")

        # Open the file in 'w' mode to clear its content before write in, or create file if it doesn't exist
        try:
            file = open(file_path, "w")
            print(f"Opening '{file_path}' for writing.")
            file.write(html_content)
            print(f"Inserted the following HTML content:\n{html_content}")
            file.close()
            print("file done writing")
        except Exception as e:
            print(f"Error occurred: {e}")

    success = False

    my_report = adr_service_query.get_report(report_name="My Top Report")

    # Define the path to the directory containing index.js
    server_directory = os.path.join(os.getcwd(), "tests", "test_data", "simple_proxy_server_test")
    # HTML content to insert into the index.html file
    html_tag = f"""
        <!DOCTYPE html>
            <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Report fetch test</title>
                </head>
                <body>
                    <style>
                        iframe{{
                            width: 100vw;
                            height: 50vh;
                        }}
                        main{{
                            width: 95vw;
                            height: auto;
                            margin: 0 auto;
                        }}
                    </style>
                    <h1>Report fetch test</h1>
                    <main>
                        {my_report.get_report_component("report")}
                    </main>
                    <script>
                        {my_report.get_report_script()}
                    </script>
                </body>
            </html>
    """
    # Create or modify the index.html file
    create_or_modify_index_html(server_directory, html_tag)
    # Run the Node.js server from the correct directory
    run_node_server(server_directory)

    adr_service_query.stop()

    assert success is True
