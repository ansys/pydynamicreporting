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
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import requests

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


# ---------------------------------------------------------------------------
# Unit tests for _detect_mathjax_version — no live ADR service needed
# ---------------------------------------------------------------------------


def _make_downloader(url="http://localhost:8000/reports/report_display/") -> rd.ReportDownloadHTML:
    """Return a ReportDownloadHTML instance with a fake URL (no live server)."""
    tmpdir = tempfile.TemporaryDirectory()
    downloader = rd.ReportDownloadHTML(url=url, directory=tmpdir.name)
    # Keep a reference to the TemporaryDirectory so it is not garbage-collected
    # (and thus deleted) before the downloader is done being used.
    downloader._tmpdir = tmpdir  # type: ignore[attr-defined]
    return downloader


def test_detect_mathjax_version_4x() -> None:
    """HEAD returning 200 for the 4.x sentinel → version "4"."""
    downloader = _make_downloader()
    mock_resp = MagicMock()
    mock_resp.status_code = requests.codes.ok
    with patch("requests.head", return_value=mock_resp) as mock_head:
        version = downloader._detect_mathjax_version()
    assert version == "4"
    # Only one HEAD call needed once the 4.x sentinel matches
    assert mock_head.call_count == 1


def test_detect_mathjax_version_2x() -> None:
    """HEAD returning 404 for 4.x and 200 for 2.x sentinel → version "2"."""
    downloader = _make_downloader()

    def _head_side_effect(url, **kwargs):
        resp = MagicMock()
        if "tex-mml-chtml.js" in url:
            resp.status_code = 404
        else:
            resp.status_code = requests.codes.ok
        return resp

    with patch("requests.head", side_effect=_head_side_effect):
        version = downloader._detect_mathjax_version()
    assert version == "2"


def test_detect_mathjax_version_405_returns_unknown() -> None:
    """HEAD returning 405 (method not allowed) for all sentinels → "unknown"."""
    downloader = _make_downloader()
    mock_resp = MagicMock()
    mock_resp.status_code = 405
    with patch("requests.head", return_value=mock_resp):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_detect_mathjax_version_403_returns_unknown() -> None:
    """HEAD returning 403 (forbidden) for all sentinels → "unknown"."""
    downloader = _make_downloader()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("requests.head", return_value=mock_resp):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_detect_mathjax_version_connection_error_returns_unknown() -> None:
    """HEAD raising ConnectionError for all sentinels → "unknown"."""
    downloader = _make_downloader()
    with patch("requests.head", side_effect=requests.ConnectionError("unreachable")):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_detect_mathjax_version_timeout_returns_unknown() -> None:
    """HEAD raising Timeout for all sentinels → "unknown"."""
    downloader = _make_downloader()
    with patch("requests.head", side_effect=requests.Timeout("timed out")):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_download_creates_media_dir_when_version_unknown(tmp_path) -> None:
    """When _detect_mathjax_version returns 'unknown', media/ must still be created."""
    downloader = rd.ReportDownloadHTML(
        url="http://localhost:8000/reports/report_display/", directory=str(tmp_path)
    )
    with patch.object(downloader, "_detect_mathjax_version", return_value="unknown"):
        # Only test that _make_dir is called for media/ — stop before the
        # network fetch by simulating a failing GET after dir setup.
        with patch("requests.get", side_effect=RuntimeError("stop after dirs")):
            with pytest.raises(RuntimeError, match="stop after dirs"):
                downloader._download()
    # media/ must have been created unconditionally
    assert (tmp_path / "media").is_dir()
