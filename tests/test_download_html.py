# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from os.path import join

from ansys.dynamicreporting.core.utils import report_download_html as rd


def test_download_use_data(request, adr_service_query) -> None:
    test_dir = join(join(request.fspath.dirname, "test_data"), "test_html_ext")
    my_url = "http://localhost:" + str(adr_service_query._port)
    my_url += "/reports/report_display/?report_table_length=10&view=c4afe878-a4fe-11ed-a616-747827182a82&usemenus=on&dpi=96&pwidth=19.41&query="
    a = rd.ReportDownloadHTML(url=my_url, directory=test_dir, debug=True)
    test_res = a._should_use_data_uri(size=5)
    assert test_res


def test_download_nourl(request, adr_service_query) -> None:
    test_dir = join(join(request.fspath.dirname, "test_data"), "exp_test_html")
    my_url = None
    a = rd.ReportDownloadHTML(url=my_url, directory=test_dir, debug=True)
    try:
        a.download()
        success = False
    except ValueError:
        success = True
    assert success


def test_download_nodir(request, adr_service_query) -> None:
    my_url = "http://localhost:" + str(adr_service_query._port)
    my_url += "/reports/report_display/?report_table_length=10&view=c4afe878-a4fe-11ed-a616-747827182a82&usemenus=on&dpi=96&pwidth=19.41&query="
    a = rd.ReportDownloadHTML(url=my_url, directory=None, debug=True)
    try:
        a.download()
        success = False
    except ValueError:
        success = True
    assert success


def test_download_sqlite(request, adr_service_query) -> None:
    test_dir = join(join(join(request.fspath.dirname, "test_data"), "query_db"), "db.sqlite3")
    my_url = "http://localhost:" + str(adr_service_query._port)
    my_url += "/reports/report_display/?report_table_length=10&view=c4afe878-a4fe-11ed-a616-747827182a82&usemenus=on&dpi=96&pwidth=19.41&query="
    a = rd.ReportDownloadHTML(url=my_url, directory=test_dir, debug=True)
    try:
        a.download()
        success = False
    except Exception as e:
        print(f"Download failed as expected with exception: {str(e)}")
        success = True
    assert success


def test_download(request, adr_service_query) -> None:
    test_dir = join(join(request.fspath.dirname, "test_data"), "html_exp")
    my_url = "http://localhost:" + str(adr_service_query._port)
    my_url += "/reports/report_display/?report_table_length=10&view=c4afe878-a4fe-11ed-a616-747827182a82&usemenus=on&dpi=96&pwidth=19.41&query="
    a = rd.ReportDownloadHTML(url=my_url, directory=test_dir, debug=True)
    test_res = a.download()
    assert test_res is None
