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

from pathlib import Path
from os.path import join
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import requests

from ansys.dynamicreporting.core.compatibility import DEFAULT_STATIC_ASSET_VERSION
from ansys.dynamicreporting.core.utils import report_download_html as rd
from ansys.dynamicreporting.core.utils.html_export_constants import (
    MATHJAX_2X_FILES,
    MATHJAX_4X_FILES,
)


def test_download_defaults_to_bundled_asset_namespace() -> None:
    # Direct helper usage often happens without a Service instance, so the
    # fallback namespace should stay pinned to the bundled asset version.
    downloader = rd.ReportDownloadHTML(url=None, directory=".")

    assert downloader._ansys_version == DEFAULT_STATIC_ASSET_VERSION


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


def _make_downloader(
    url="http://localhost:8000/reports/report_display/",
) -> tuple[rd.ReportDownloadHTML, tempfile.TemporaryDirectory]:
    """Return a downloader plus its tempdir so tests control cleanup explicitly."""
    tmpdir = tempfile.TemporaryDirectory()
    downloader = rd.ReportDownloadHTML(url=url, directory=tmpdir.name)
    return downloader, tmpdir


def _build_mathjax_url(source_rel_path: str) -> str:
    """Build the remote static URL that ``_download_special_files()`` requests."""
    return f"http://localhost:8000/static/{source_rel_path}"


def _make_response(status_code: int, content: bytes = b"asset") -> MagicMock:
    """Create a small fake ``requests`` response for MathJax download tests."""
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    return response


def _make_text_response(status_code: int, text: str) -> MagicMock:
    """Create a fake HTML response for downloader flow tests."""
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.content = text.encode("utf-8")
    return response


def _assert_paths_exist(base_path: Path, relative_paths: tuple[str, ...]) -> None:
    """Assert that every relative path exists below ``base_path``."""
    for relative_path in relative_paths:
        assert (base_path / relative_path).is_dir()


def _assert_paths_missing(base_path: Path, relative_paths: tuple[str, ...]) -> None:
    """Assert that every relative path is absent below ``base_path``."""
    for relative_path in relative_paths:
        assert not (base_path / relative_path).exists()


def _run_download_until_after_directory_setup(
    downloader: rd.ReportDownloadHTML, mathjax_version: str
) -> None:
    """Create only the export directories for the requested MathJax version."""
    downloader._make_output_dirs(mathjax_version)


def test_detect_mathjax_version_4x() -> None:
    """HEAD returning 200 for the 4.x sentinel → version "4"."""
    downloader, _tmpdir = _make_downloader()
    mock_resp = MagicMock()
    mock_resp.status_code = requests.codes.ok
    with patch("requests.head", return_value=mock_resp) as mock_head:
        version = downloader._detect_mathjax_version()
    assert version == "4"
    # Only one HEAD call needed once the 4.x sentinel matches
    assert mock_head.call_count == 1


def test_detect_mathjax_version_2x() -> None:
    """HEAD returning 404 for 4.x and 200 for 2.x sentinel → version "2"."""
    downloader, _tmpdir = _make_downloader()

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
    downloader, _tmpdir = _make_downloader()
    mock_resp = MagicMock()
    mock_resp.status_code = 405
    with patch("requests.head", return_value=mock_resp):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_detect_mathjax_version_403_returns_unknown() -> None:
    """HEAD returning 403 (forbidden) for all sentinels → "unknown"."""
    downloader, _tmpdir = _make_downloader()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("requests.head", return_value=mock_resp):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_detect_mathjax_version_connection_error_returns_unknown() -> None:
    """HEAD raising ConnectionError for all sentinels → "unknown"."""
    downloader, _tmpdir = _make_downloader()
    with patch("requests.head", side_effect=requests.ConnectionError("unreachable")):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_detect_mathjax_version_timeout_returns_unknown() -> None:
    """HEAD raising Timeout for all sentinels → "unknown"."""
    downloader, _tmpdir = _make_downloader()
    with patch("requests.head", side_effect=requests.Timeout("timed out")):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_detect_mathjax_version_request_exception_returns_unknown() -> None:
    """HEAD raising RequestException for all sentinels should return unknown."""
    downloader, _tmpdir = _make_downloader()
    with patch("requests.head", side_effect=requests.RequestException("generic failure")):
        version = downloader._detect_mathjax_version()
    assert version == "unknown"


def test_detect_mathjax_version_prefers_report_html_when_available() -> None:
    """Rendered HTML should decide the version before any installation probe."""
    downloader, _tmpdir = _make_downloader()
    downloader._report_html = '<script src="/static/website/scripts/mathjax/MathJax.js"></script>'

    with patch.object(
        downloader,
        "_detect_mathjax_version_from_installation",
        side_effect=AssertionError("installation probe should not run"),
    ):
        version = downloader._detect_mathjax_version()

    assert version == "2"


def test_detect_mathjax_version_falls_back_to_installation_when_html_is_unknown() -> None:
    """Unknown HTML should defer to the installation-level sentinel probe."""
    downloader, _tmpdir = _make_downloader()
    downloader._report_html = "<div>No MathJax loader here</div>"

    with patch.object(downloader, "_detect_mathjax_version_from_installation", return_value="4"):
        version = downloader._detect_mathjax_version()

    assert version == "4"


def test_download_uses_report_html_for_mathjax_directory_selection(tmp_path) -> None:
    """The main download flow should create MathJax dirs from the report HTML."""
    downloader = rd.ReportDownloadHTML(
        url="http://localhost:8000/reports/report_display/", directory=str(tmp_path)
    )
    html_response = _make_text_response(
        requests.codes.ok,
        '<script src="/static/website/scripts/mathjax/MathJax.js"></script>',
    )

    with patch("requests.get", return_value=html_response):
        with patch.object(
            downloader,
            "_detect_mathjax_version_from_installation",
            side_effect=AssertionError("installation probe should not run"),
        ):
            with patch.object(downloader, "_download_special_files"):
                with patch.object(
                    downloader, "_replace_blocks", side_effect=lambda html, *a, **k: html
                ):
                    with patch.object(
                        downloader, "_inline_ansys_viewer", side_effect=lambda html: html
                    ):
                        downloader._download()

    assert (tmp_path / "media" / "config").is_dir()
    assert not (tmp_path / "media" / "a11y").exists()


def test_download_special_files_only_requests_detected_4x_assets(tmp_path) -> None:
    """A detected 4.x install should not waste GETs on the 2.x tree."""
    downloader = rd.ReportDownloadHTML(
        url="http://localhost:8000/reports/report_display/", directory=str(tmp_path)
    )
    requested_urls: list[str] = []
    expected_urls = {_build_mathjax_url(source_rel_path) for source_rel_path in MATHJAX_4X_FILES}

    def _get_side_effect(url, **kwargs):
        requested_urls.append(url)
        if url in expected_urls:
            return _make_response(requests.codes.ok)
        return _make_response(404)

    with patch.object(downloader, "_detect_mathjax_version", return_value="4"):
        # Stub unrelated asset downloads so this test only exercises MathJax behavior.
        with patch.object(downloader, "_download_static_files"):
            with patch("requests.get", side_effect=_get_side_effect):
                with patch("builtins.print") as mock_print:
                    downloader._download_special_files()

    assert set(requested_urls) == expected_urls
    assert not mock_print.called
    assert not (tmp_path / "media" / "MathJax.js").exists()


def test_download_special_files_writes_2x_loader_and_ui_assets(tmp_path) -> None:
    """A detected 2.x install should write the loader and menu assets offline."""
    downloader = rd.ReportDownloadHTML(
        url="http://localhost:8000/reports/report_display/", directory=str(tmp_path)
    )
    requested_urls: list[str] = []
    expected_urls = {_build_mathjax_url(source_rel_path) for source_rel_path in MATHJAX_2X_FILES}

    def _get_side_effect(url, **kwargs):
        requested_urls.append(url)
        if url in expected_urls:
            return _make_response(requests.codes.ok, content=b"mathjax-2x")
        return _make_response(404)

    with patch.object(downloader, "_detect_mathjax_version", return_value="2"):
        # Stub unrelated asset downloads so this test only exercises MathJax behavior.
        with patch.object(downloader, "_download_static_files"):
            with patch("requests.get", side_effect=_get_side_effect):
                with patch("builtins.print") as mock_print:
                    downloader._download_special_files()

    assert set(requested_urls) == expected_urls
    assert not mock_print.called
    assert (tmp_path / "media" / "MathJax.js").read_bytes() == b"mathjax-2x"
    assert (tmp_path / "media" / "extensions" / "HelpDialog.js").read_bytes() == b"mathjax-2x"
    assert (tmp_path / "media" / "images" / "CloseX-31.png").read_bytes() == b"mathjax-2x"


def _obsolete_test_download_creates_media_dir_when_version_unknown(tmp_path) -> None:
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


def test_download_creates_media_dir_when_version_unknown(tmp_path) -> None:
    """Unknown version should still create the common media root."""
    downloader = rd.ReportDownloadHTML(
        url="http://localhost:8000/reports/report_display/", directory=str(tmp_path)
    )
    downloader._make_output_dirs("unknown")

    assert (tmp_path / "media").is_dir()


def test_download_creates_only_4x_mathjax_dirs_when_version_is_4(tmp_path) -> None:
    """A detected 4.x install should precreate only the 4.x MathJax tree."""
    downloader = rd.ReportDownloadHTML(
        url="http://localhost:8000/reports/report_display/", directory=str(tmp_path)
    )
    ansys_root = f"ansys{downloader._ansys_version}"

    _run_download_until_after_directory_setup(downloader, "4")

    _assert_paths_exist(
        tmp_path,
        (
            "media",
            "media/a11y",
            "media/input/mml/extensions",
            "media/input/tex/extensions",
            "media/output",
            "media/sre/mathmaps",
            "media/ui",
            "webfonts",
            f"{ansys_root}/nexus/images",
            f"{ansys_root}/nexus/utils",
            f"{ansys_root}/nexus/threejs/libs/draco/gltf",
            f"{ansys_root}/nexus/novnc/vendor/jQuery-contextMenu",
        ),
    )
    _assert_paths_missing(
        tmp_path,
        (
            "media/config",
            "media/extensions/TeX",
            "media/jax/element/mml",
            "media/jax/input/TeX",
            "media/jax/input/MathML",
            "media/jax/input/AsciiMath",
            "media/images",
        ),
    )


def test_download_creates_only_2x_mathjax_dirs_when_version_is_2(tmp_path) -> None:
    """A detected 2.x install should precreate only the legacy MathJax tree."""
    downloader = rd.ReportDownloadHTML(
        url="http://localhost:8000/reports/report_display/", directory=str(tmp_path)
    )
    ansys_root = f"ansys{downloader._ansys_version}"

    _run_download_until_after_directory_setup(downloader, "2")

    _assert_paths_exist(
        tmp_path,
        (
            "media",
            "media/config",
            "media/extensions/TeX",
            "media/jax/output/SVG/fonts/TeX/Main/Regular",
            "media/jax/output/SVG/fonts/TeX/Size1/Regular",
            "media/jax/element/mml",
            "media/jax/input/TeX",
            "media/jax/input/MathML",
            "media/jax/input/AsciiMath",
            "media/images",
            "webfonts",
            f"{ansys_root}/nexus/images",
            f"{ansys_root}/nexus/utils",
            f"{ansys_root}/nexus/threejs/libs/draco/gltf",
            f"{ansys_root}/nexus/novnc/vendor/jQuery-contextMenu",
        ),
    )
    _assert_paths_missing(
        tmp_path,
        (
            "media/a11y",
            "media/input/mml/extensions",
            "media/input/tex/extensions",
            "media/output",
            "media/sre/mathmaps",
            "media/ui",
        ),
    )


def test_download_unknown_version_skips_all_version_specific_mathjax_dirs(tmp_path) -> None:
    """Unknown version should leave only the common export directories in place."""
    downloader = rd.ReportDownloadHTML(
        url="http://localhost:8000/reports/report_display/", directory=str(tmp_path)
    )
    ansys_root = f"ansys{downloader._ansys_version}"

    _run_download_until_after_directory_setup(downloader, "unknown")

    _assert_paths_exist(
        tmp_path,
        (
            "media",
            "webfonts",
            f"{ansys_root}/nexus/images",
            f"{ansys_root}/nexus/utils",
            f"{ansys_root}/nexus/threejs/libs/draco/gltf",
            f"{ansys_root}/nexus/novnc/vendor/jQuery-contextMenu",
        ),
    )
    _assert_paths_missing(
        tmp_path,
        (
            "media/a11y",
            "media/input/mml/extensions",
            "media/input/tex/extensions",
            "media/output",
            "media/sre/mathmaps",
            "media/ui",
            "media/config",
            "media/extensions/TeX",
            "media/jax/element/mml",
            "media/jax/input/TeX",
            "media/jax/input/MathML",
            "media/jax/input/AsciiMath",
            "media/images",
        ),
    )
