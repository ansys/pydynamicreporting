from os.path import join

from ansys.dynamicreporting.core.utils import report_download_html as rd


def test_download_use_data(request, adr_service_query) -> bool:
    test_dir = join(join(request.fspath.dirname, "test_data"), "test_html_ext")
    my_url = "http://localhost:" + str(adr_service_query._port)
    my_url += "/reports/report_display/?report_table_length=10&view=c4afe878-a4fe-11ed-a616-747827182a82&usemenus=on&dpi=96&pwidth=19.41&query="
    a = rd.ReportDownloadHTML(url=my_url, directory=test_dir, debug=True)
    test_res = a._should_use_data_uri(size=5)
    adr_service_query.stop()
    assert test_res


def test_download_nourl(request, adr_service_query) -> bool:
    test_dir = join(join(request.fspath.dirname, "test_data"), "exp_test_html")
    my_url = None
    a = rd.ReportDownloadHTML(url=my_url, directory=test_dir, debug=True)
    try:
        a.download()
        success = False
    except ValueError:
        success = True
    adr_service_query.stop()
    assert success


def test_download_nodir(request, adr_service_query) -> bool:
    my_url = "http://localhost:" + str(adr_service_query._port)
    my_url += "/reports/report_display/?report_table_length=10&view=c4afe878-a4fe-11ed-a616-747827182a82&usemenus=on&dpi=96&pwidth=19.41&query="
    a = rd.ReportDownloadHTML(url=my_url, directory=None, debug=True)
    try:
        a.download()
        success = False
    except ValueError:
        success = True
    adr_service_query.stop()
    assert success


def test_download_sqlite(request, adr_service_query) -> bool:
    test_dir = join(join(join(request.fspath.dirname, "test_data"), "query_db"), "db.sqlite3")
    my_url = "http://localhost:" + str(adr_service_query._port)
    my_url += "/reports/report_display/?report_table_length=10&view=c4afe878-a4fe-11ed-a616-747827182a82&usemenus=on&dpi=96&pwidth=19.41&query="
    a = rd.ReportDownloadHTML(url=my_url, directory=test_dir, debug=True)
    try:
        a.download()
        success = False
    except Exception:
        success = True
    adr_service_query.stop()
    assert success


def test_download(request, adr_service_query) -> bool:
    test_dir = join(join(request.fspath.dirname, "test_data"), "html_exp")
    my_url = "http://localhost:" + str(adr_service_query._port)
    my_url += "/reports/report_display/?report_table_length=10&view=c4afe878-a4fe-11ed-a616-747827182a82&usemenus=on&dpi=96&pwidth=19.41&query="
    a = rd.ReportDownloadHTML(url=my_url, directory=test_dir, debug=True)
    test_res = a.download()
    adr_service_query.stop()
    assert test_res is None
