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

from __future__ import annotations

from pathlib import Path
import textwrap
from unittest.mock import patch

import pytest

from ansys.dynamicreporting.core.serverless.html_exporter import ServerlessReportExporter

# ----------------------------
# helpers
# ----------------------------


def _write(p: Path, data: bytes | str):
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data, encoding="utf-8")


def _fragment_with_static_ref(path: str) -> str:
    # pure fragment (no <html>), to force the exporter to wrap into a full document
    return f'<div class="body-content m-1"><link rel="stylesheet" href="{path}"/></div>'


def _make_exporter_for_mathjax_detection(
    tmp_path: Path, *, html_content: str = "<div/>"
) -> ServerlessReportExporter:
    """Build a minimal exporter instance for filesystem-only MathJax tests.

    These tests exercise version detection directly, so they do not need the
    heavier ADR fixture.  Keeping the setup local makes the tests fast and
    avoids mixing static-directory concerns with the broader export behavior.
    """
    return ServerlessReportExporter(
        html_content=html_content,
        output_dir=tmp_path / "out",
        static_dir=tmp_path / "static",
        media_dir=tmp_path / "media",
        static_url="/static/",
        media_url="/media/",
        ansys_version="252",
    )


def _assert_output_dirs_exist(base_path: Path, relative_paths: tuple[str, ...]) -> None:
    """Assert that each expected output directory exists."""
    for relative_path in relative_paths:
        assert (base_path / relative_path).is_dir()


def _assert_output_dirs_missing(base_path: Path, relative_paths: tuple[str, ...]) -> None:
    """Assert that each directory path is absent from the export tree."""
    for relative_path in relative_paths:
        assert not (base_path / relative_path).exists()


# ----------------------------
# tests
# ----------------------------


@pytest.mark.ado_test
def test_wraps_fragment_and_emits_title_and_favicon(adr_serverless, tmp_path: Path):
    static_dir = Path(adr_serverless.static_directory)
    media_dir = Path(adr_serverless.media_directory)
    ver = str(adr_serverless.ansys_version)

    # Ensure required inputs exist in the real static dir used by the fixture
    _write(static_dir / "website/images/favicon.png", b"\x89PNG\x00")
    _write(static_dir / "website/content/site.css", "body{overflow:hidden;}")

    href = f"{adr_serverless.static_url}website/content/site.css"

    exporter = ServerlessReportExporter(
        html_content=_fragment_with_static_ref(href),
        output_dir=tmp_path / "export1",
        static_dir=static_dir,
        media_dir=media_dir,
        static_url=adr_serverless.static_url,
        media_url=adr_serverless.media_url,
        ansys_version=ver,
    )
    exporter.export()

    out = (tmp_path / "export1" / "index.html").read_text(encoding="utf-8")
    # Full document wrapper
    assert out.lstrip().startswith("<!DOCTYPE html>")
    assert "<title>Report - ADR</title>" in out
    assert 'rel="shortcut icon" href="./media/favicon.ico"' in out

    # favicon copied (.png) and duplicated as .ico, css flattened to ./media
    assert (tmp_path / "export1" / "media" / "favicon.png").is_file()
    assert (tmp_path / "export1" / "media" / "favicon.ico").is_file()
    assert (tmp_path / "export1" / "media" / "site.css").is_file()


@pytest.mark.ado_test
def test_static_is_flattened_media_and_ansys_tree_preserved(adr_serverless, tmp_path: Path):
    static_dir = Path(adr_serverless.static_directory)
    media_dir = Path(adr_serverless.media_directory)
    ver = str(adr_serverless.ansys_version)

    # Create a test file under ansys tree (preserved)
    _write(static_dir / f"ansys{ver}/nexus/utils/js-test.js", "/* ansys util */")
    # Create a non-ansys static file (flattened)
    _write(static_dir / "website/scripts/plotly.min.js", "/* plotly */")
    # favicon for wrapper
    _write(static_dir / "website/images/favicon.png", b"\x89PNG\x00")

    plotly_href = f"{adr_serverless.static_url}website/scripts/plotly.min.js"
    ansys_util_src = f"{adr_serverless.static_url}ansys{ver}/nexus/utils/js-test.js"

    html = _fragment_with_static_ref(plotly_href) + textwrap.dedent(
        f"""
        <script src="{ansys_util_src}"></script>
        """
    )

    exporter = ServerlessReportExporter(
        html_content=html,
        output_dir=tmp_path / "export2",
        static_dir=static_dir,
        media_dir=media_dir,
        static_url=adr_serverless.static_url,
        media_url=adr_serverless.media_url,
        ansys_version=ver,
    )
    exporter.export()

    # Filesystem results
    assert (tmp_path / "export2" / "media" / "plotly.min.js").is_file()
    assert (tmp_path / "export2" / f"ansys{ver}/nexus/utils/js-test.js").is_file()

    # Rewritten references in HTML
    out = (tmp_path / "export2" / "index.html").read_text(encoding="utf-8")
    assert 'href="./media/plotly.min.js"' in out or 'src="./media/plotly.min.js"' in out
    assert f"./ansys{ver}/nexus/utils/js-test.js" in out


@pytest.mark.ado_test
def test_favicon_png_is_duplicated_as_ico(adr_serverless, tmp_path: Path):
    static_dir = Path(adr_serverless.static_directory)
    media_dir = Path(adr_serverless.media_directory)
    ver = str(adr_serverless.ansys_version)

    _write(static_dir / "website/images/favicon.png", b"PNGDATA")
    _write(static_dir / "website/content/site.css", "h2{}")

    href = f"{adr_serverless.static_url}website/content/site.css"

    exporter = ServerlessReportExporter(
        html_content=_fragment_with_static_ref(href),
        output_dir=tmp_path / "export4",
        static_dir=static_dir,
        media_dir=media_dir,
        static_url=adr_serverless.static_url,
        media_url=adr_serverless.media_url,
        ansys_version=ver,
    )
    exporter.export()

    ico = tmp_path / "export4" / "media" / "favicon.ico"
    png = tmp_path / "export4" / "media" / "favicon.png"
    assert ico.is_file() and png.is_file()
    assert ico.read_bytes() == png.read_bytes()


@pytest.mark.ado_test
def test_inline_viewer_size_exception_sets_proxy_only(adr_serverless, tmp_path: Path):
    static_dir = Path(adr_serverless.static_directory)
    media_dir = Path(adr_serverless.media_directory)
    ver = str(adr_serverless.ansys_version)

    # Provide a "large" file to force size exception
    _write(media_dir / "bigfile.stl", b"x" * 2048)
    _write(media_dir / "preview.png", b"P")
    _write(static_dir / "website/images/favicon.png", b"P")

    media_src = f"{adr_serverless.media_url}bigfile.stl"
    media_preview = f"{adr_serverless.media_url}preview.png"

    html = textwrap.dedent(
        f"""
        <div>
          <ansys-nexus-viewer src="{media_src}" proxy_img="{media_preview}"></ansys-nexus-viewer>
        </div>
        """
    )

    exporter = ServerlessReportExporter(
        html_content=html,
        output_dir=tmp_path / "export5",
        static_dir=static_dir,
        media_dir=media_dir,
        static_url=adr_serverless.static_url,
        media_url=adr_serverless.media_url,
        ansys_version=ver,
    )
    exporter._max_inline_size = 1  # minuscule cap to trigger the exception path
    exporter.export()

    out = (tmp_path / "export5" / "index.html").read_text(encoding="utf-8")
    assert 'proxy_only="3D geometry too large for stand-alone HTML file"' in out
    assert 'src=""' in out  # viewer src cleared
    # proxy_img still inlined or copied
    assert "./media/preview.png" in out or "data:application/octet-stream;base64," in out


@pytest.mark.ado_test
def test_scene_js_inlines_binary_block_and_namespaces_filename(adr_serverless, tmp_path: Path):
    static_dir = Path(adr_serverless.static_directory)
    media_dir = Path(adr_serverless.media_directory)
    ver = str(adr_serverless.ansys_version)

    # Babylon scene referencing a binary block; exporter will inline it
    media_blob = f"{adr_serverless.media_url}blob.bin"
    _write(static_dir / "website/scenes/guid123.scene.js", f"load_binary_block('{media_blob}');")
    _write(media_dir / "blob.bin", b"\x00\x01\x02\x03")
    _write(static_dir / "website/images/favicon.png", b"P")

    script_src = f"{adr_serverless.static_url}website/scenes/guid123.scene.js"
    html = f'<div><script src="{script_src}"></script></div>'

    exporter = ServerlessReportExporter(
        html_content=html,
        output_dir=tmp_path / "export6",
        static_dir=static_dir,
        media_dir=media_dir,
        static_url=adr_serverless.static_url,
        media_url=adr_serverless.media_url,
        ansys_version=ver,
    )
    exporter.export()

    # For scene.js, exporter writes to ./media with a namespaced filename:
    # basename becomes f"{parent.name}_{basename}" -> "scenes_guid123.scene.js"
    scene_out = tmp_path / "export6" / "media" / "scenes_guid123.scene.js"
    assert scene_out.is_file(), "Expected scene.js to be written to media/"
    content = scene_out.read_text(encoding="utf-8")
    assert "data:application/octet-stream;base64," in content


@pytest.mark.ado_test
def test_preserves_existing_full_document(adr_serverless, tmp_path: Path):
    static_dir = Path(adr_serverless.static_directory)
    media_dir = Path(adr_serverless.media_directory)
    ver = str(adr_serverless.ansys_version)

    _write(static_dir / "website/images/favicon.png", b"P")

    html_doc = textwrap.dedent(
        """\
        <!DOCTYPE html>
        <html><head><title>Already Full</title></head>
        <body><div>hi</div></body></html>
        """
    )

    exporter = ServerlessReportExporter(
        html_content=html_doc,
        output_dir=tmp_path / "export7",
        static_dir=static_dir,
        media_dir=media_dir,
        static_url=adr_serverless.static_url,
        media_url=adr_serverless.media_url,
        ansys_version=ver,
    )
    exporter.export()

    out = (tmp_path / "export7" / "index.html").read_text(encoding="utf-8")
    assert "<title>Already Full</title>" in out  # wrapper not added


@pytest.mark.ado_test
def test_no_inline_flag_forces_copy_not_data_uri(adr_serverless, tmp_path: Path):
    static_dir = Path(adr_serverless.static_directory)
    media_dir = Path(adr_serverless.media_directory)
    ver = str(adr_serverless.ansys_version)

    _write(static_dir / "website/images/favicon.png", b"P")
    _write(media_dir / "tiny.bin", b"ABCD")

    href = f"{adr_serverless.media_url}tiny.bin"
    html = f'<div><a href="{href}">dl</a></div>'

    exporter = ServerlessReportExporter(
        html_content=html,
        output_dir=tmp_path / "export8",
        static_dir=static_dir,
        media_dir=media_dir,
        static_url=adr_serverless.static_url,
        media_url=adr_serverless.media_url,
        ansys_version=ver,
        no_inline_files=True,
    )
    exporter.export()

    out = (tmp_path / "export8" / "index.html").read_text(encoding="utf-8")
    assert "data:application/octet-stream" not in out
    assert "./media/tiny.bin" in out
    assert (tmp_path / "export8" / "media" / "tiny.bin").is_file()


@pytest.mark.ado_test
def test_missing_source_file_keeps_original_ref(adr_serverless, tmp_path: Path):
    static_dir = Path(adr_serverless.static_directory)
    media_dir = Path(adr_serverless.media_directory)
    ver = str(adr_serverless.ansys_version)

    _write(static_dir / "website/images/favicon.png", b"P")

    # Refer to a media file that doesn't exist
    missing_href = f"{adr_serverless.media_url}does_not_exist.xyz"
    html = f'<div><img src="{missing_href}"/></div>'

    exporter = ServerlessReportExporter(
        html_content=html,
        output_dir=tmp_path / "export9",
        static_dir=static_dir,
        media_dir=media_dir,
        static_url=adr_serverless.static_url,
        media_url=adr_serverless.media_url,
        ansys_version=ver,
    )
    exporter.export()

    out = (tmp_path / "export9" / "index.html").read_text(encoding="utf-8")
    # Exporter leaves the original path when it can't find a local file
    assert missing_href in out


def test_detect_mathjax_version_4x_from_static_tree(tmp_path: Path):
    """A 4.x sentinel on disk should be reported without probing the 2.x tree."""
    exporter = _make_exporter_for_mathjax_detection(tmp_path)
    _write(exporter._static_dir / "website/scripts/mathjax/tex-mml-chtml.js", "")

    assert exporter._detect_mathjax_version() == "4"


def test_detect_mathjax_version_prefers_html_over_static_tree(tmp_path: Path):
    """Rendered HTML should decide the version before static fallback probes."""
    exporter = _make_exporter_for_mathjax_detection(
        tmp_path,
        html_content='<script src="/static/website/scripts/mathjax/tex-mml-chtml.js"></script>',
    )

    with patch.object(
        exporter,
        "_detect_mathjax_version_from_static_tree",
        side_effect=AssertionError("static fallback should not run"),
    ):
        assert exporter._detect_mathjax_version() == "4"


def test_detect_mathjax_version_2x_from_static_tree(tmp_path: Path):
    """A 2.x sentinel on disk should be reported when the 4.x loader is absent."""
    exporter = _make_exporter_for_mathjax_detection(tmp_path)
    _write(exporter._static_dir / "website/scripts/mathjax/MathJax.js", "")

    assert exporter._detect_mathjax_version() == "2"


def test_detect_mathjax_version_unknown_when_no_sentinel_exists(tmp_path: Path):
    """Missing sentinel files should leave the exporter in the unknown state."""
    exporter = _make_exporter_for_mathjax_detection(tmp_path)

    assert exporter._detect_mathjax_version() == "unknown"


def test_detect_mathjax_version_falls_back_to_static_tree_when_html_is_unknown(tmp_path: Path):
    """Unknown HTML should defer to the static-tree sentinel check."""
    exporter = _make_exporter_for_mathjax_detection(tmp_path)
    _write(exporter._static_dir / "website/scripts/mathjax/MathJax.js", "")

    assert exporter._detect_mathjax_version() == "2"


def test_detect_mathjax_version_uses_cached_result_after_first_lookup(tmp_path: Path):
    """Repeated detector calls should reuse the first resolved installation state.

    The exporter asks for the MathJax version from both directory creation and
    asset-copy code paths during one export.  This test verifies that the
    version is resolved once per exporter instance and then served from the
    cache instead of touching the filesystem again.
    """
    exporter = _make_exporter_for_mathjax_detection(tmp_path)
    mathjax_root = exporter._static_dir / "website/scripts/mathjax"
    first_sentinel = mathjax_root / "tex-mml-chtml.js"
    second_sentinel = mathjax_root / "MathJax.js"

    _write(first_sentinel, "")
    assert exporter._detect_mathjax_version() == "4"

    # If the detector re-ran the filesystem scan, the changed sentinels below
    # would flip the answer to 2.x.  A cached result keeps the export behavior
    # stable for the lifetime of this exporter instance.
    first_sentinel.unlink()
    _write(second_sentinel, "")

    assert exporter._detect_mathjax_version() == "4"


def test_make_output_dirs_creates_only_4x_mathjax_tree(tmp_path: Path):
    """A page that references MathJax 4.x should get only the 4.x directory layout."""
    exporter = _make_exporter_for_mathjax_detection(
        tmp_path,
        html_content='<script src="/static/website/scripts/mathjax/tex-mml-chtml.js"></script>',
    )

    exporter._make_output_dirs()

    _assert_output_dirs_exist(
        exporter._output_dir,
        (
            "media/a11y",
            "media/input/mml/extensions",
            "media/input/tex/extensions",
            "media/output",
            "media/sre/mathmaps",
            "media/ui",
            "webfonts",
            "ansys252/nexus/images",
            "ansys252/nexus/utils",
            "ansys252/nexus/threejs/libs/draco/gltf",
            "ansys252/nexus/novnc/vendor/jQuery-contextMenu",
        ),
    )
    _assert_output_dirs_missing(
        exporter._output_dir,
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


def test_make_output_dirs_creates_only_2x_mathjax_tree(tmp_path: Path):
    """A page that references MathJax 2.x should get only the legacy directory layout."""
    exporter = _make_exporter_for_mathjax_detection(
        tmp_path,
        html_content='<script src="/static/website/scripts/mathjax/MathJax.js"></script>',
    )

    exporter._make_output_dirs()

    _assert_output_dirs_exist(
        exporter._output_dir,
        (
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
            "ansys252/nexus/images",
            "ansys252/nexus/utils",
            "ansys252/nexus/threejs/libs/draco/gltf",
            "ansys252/nexus/novnc/vendor/jQuery-contextMenu",
        ),
    )
    _assert_output_dirs_missing(
        exporter._output_dir,
        (
            "media/a11y",
            "media/input/mml/extensions",
            "media/input/tex/extensions",
            "media/output",
            "media/sre/mathmaps",
            "media/ui",
        ),
    )


def test_make_output_dirs_unknown_version_skips_version_specific_dirs(tmp_path: Path):
    """Unknown installs should still create the common export directories."""
    exporter = _make_exporter_for_mathjax_detection(tmp_path)

    exporter._make_output_dirs()

    _assert_output_dirs_exist(
        exporter._output_dir,
        (
            "webfonts",
            "ansys252/nexus/images",
            "ansys252/nexus/utils",
            "ansys252/nexus/threejs/libs/draco/gltf",
            "ansys252/nexus/novnc/vendor/jQuery-contextMenu",
        ),
    )
    _assert_output_dirs_missing(
        exporter._output_dir,
        (
            "media",
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
