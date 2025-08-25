import logging
from pathlib import Path

import pytest

from ansys.dynamicreporting.core.serverless.html_exporter import ServerlessReportExporter
from ansys.dynamicreporting.core.utils.html_export_constants import ANSYS_VERSION_FALLBACK, FONTS


@pytest.fixture
def exporter_setup(tmp_path):
    """Set up a temporary directory structure for testing."""
    output_dir = tmp_path / "output"
    static_dir = tmp_path / "static"
    media_dir = tmp_path / "media"

    versioned_static_dir = static_dir / f"ansys{ANSYS_VERSION_FALLBACK}" / "nexus" / "images"
    versioned_static_dir.mkdir(parents=True)
    (static_dir / "website" / "content").mkdir(parents=True)
    (static_dir / "website" / "webfonts").mkdir(parents=True)
    media_dir.mkdir()

    (static_dir / "website" / "content" / "site.css").write_text("body {}")
    (static_dir / "website" / "webfonts" / FONTS[0]).write_text("fake_font_data")
    (versioned_static_dir / "play.png").write_text("fake_png_data")
    (media_dir / "user_image.png").write_text("fake_user_png_data")

    return output_dir, static_dir, media_dir


def test_export_into_db_directory_fails(exporter_setup):
    """Verify export fails if output is a Nexus database directory."""
    output_dir, static_dir, media_dir = exporter_setup
    output_dir.mkdir(exist_ok=True)
    (output_dir / "db.sqlite3").touch()

    exporter = ServerlessReportExporter(
        html_content="<html></html>",
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
    )
    with pytest.raises(ValueError, match="Cannot export into a Nexus database directory"):
        exporter.export()


def test_export_debug_mode(exporter_setup):
    """Verify that debug=True saves the raw HTML file."""
    output_dir, static_dir, media_dir = exporter_setup
    html_content = "<html>debug test</html>"
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        debug=True,
    )
    exporter.export()
    raw_html_path = output_dir / "index.raw.html"
    assert raw_html_path.exists()
    assert raw_html_path.read_text() == html_content


def test_process_media_file_no_inline(exporter_setup):
    """Test that a /media/ file is copied when no_inline_files is True."""
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><body><img src="/media/user_image.png"></body></html>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=True,
    )
    exporter.export()
    final_html_path = output_dir / "index.html"
    copied_media_path = output_dir / "media" / "user_image.png"
    assert copied_media_path.exists()
    assert copied_media_path.read_text() == "fake_user_png_data"
    assert 'src="./media/user_image.png"' in final_html_path.read_text()


def test_process_ansys_versioned_file(exporter_setup):
    """
    Test that a versioned path is handled correctly.
    NOTE: The original implementation puts non-static versioned assets in ./media/.
    This test verifies that the new implementation faithfully reproduces this behavior.
    """
    output_dir, static_dir, media_dir = exporter_setup
    # This path is NOT under /static/, so it should be redirected to ./media/
    html_content = f'<html><body><img src="/ansys{ANSYS_VERSION_FALLBACK}/nexus/images/play.png"></body></html>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        ansys_version=ANSYS_VERSION_FALLBACK,
        no_inline_files=True,
    )
    exporter.export()
    # The file should be in media, not in a versioned directory
    copied_file_path = output_dir / "media" / "play.png"
    assert not (
        output_dir / f"ansys{ANSYS_VERSION_FALLBACK}"
    ).exists()  # No versioned dir should be made
    assert copied_file_path.exists()
    final_html_content = (output_dir / "index.html").read_text()
    # The rewritten path must point to ./media/
    assert 'src="./media/play.png"' in final_html_content


def test_filename_collision(exporter_setup):
    """Test that the exporter avoids filename collisions."""
    output_dir, static_dir, media_dir = exporter_setup
    (media_dir / "another_dir").mkdir()
    (media_dir / "another_dir" / "user_image.png").write_text("another_one")
    html_content = '<html><img src="/media/user_image.png"><img src="/media/another_dir/user_image.png"></html>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=True,
    )
    exporter.export()
    assert (output_dir / "media" / "user_image.png").exists()
    assert (output_dir / "media" / "1_user_image.png").exists()
    assert (output_dir / "media" / "1_user_image.png").read_text() == "another_one"


def test_inline_size_limit(exporter_setup):
    """Test that a file exceeding the inline size limit is not inlined."""
    output_dir, static_dir, media_dir = exporter_setup
    (media_dir / "large_file.bin").write_text("A")
    html_content = '<html><a href="/media/large_file.bin">link</a></html>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=False,
    )
    exporter._max_inline_size = 0
    exporter.export()
    final_html_content = (output_dir / "index.html").read_text()
    assert "data:application/octet-stream;base64," not in final_html_content
    assert (output_dir / "media" / "large_file.bin").exists()


def test_inline_ansys_viewer(exporter_setup):
    """Test special handling for the ansys-nexus-viewer component."""
    output_dir, static_dir, media_dir = exporter_setup
    (media_dir / "proxy.png").write_text("proxy_data")
    (media_dir / "scene.avz").write_text("scene_data")
    html_content = '<ansys-nexus-viewer src="/media/scene.avz" proxy_img="/media/proxy.png"></ansys-nexus-viewer>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=False,
    )
    exporter.export()
    final_html_content = (output_dir / "index.html").read_text()
    assert final_html_content.count("data:application/octet-stream;base64,") == 2
    assert 'src_ext="AVZ"' in final_html_content


def test_missing_file_handling(exporter_setup, caplog):
    """Test that a missing file is handled gracefully and logged."""
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/non_existent_file.png"></html>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
    )
    # Correctly set the level on the logger the exporter will use
    exporter._logger.setLevel(logging.WARNING)
    with caplog.at_level(logging.WARNING):
        exporter.export()
    final_html_content = (output_dir / "index.html").read_text()
    assert 'src="/media/non_existent_file.png"' in final_html_content
    assert (
        "Warning: Unable to find local file for path: /media/non_existent_file.png" in caplog.text
    )


def test_scene_file_is_inlined_by_default(exporter_setup):
    """Test that a scene file (.avz) is inlined by default."""
    output_dir, static_dir, media_dir = exporter_setup
    (media_dir / "scene.avz").write_text("scene_data")
    html_content = '<html><a href="/media/scene.avz">Scene</a></html>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=False,
    )
    exporter.export()
    final_html_content = (output_dir / "index.html").read_text()
    assert 'href="data:application/octet-stream;base64,' in final_html_content


def test_babylon_scene_js_handling(exporter_setup):
    """Test special case for handling babylon.js scene.js files."""
    output_dir, static_dir, media_dir = exporter_setup
    scene_dir = media_dir / "a_guid_scene"
    scene_dir.mkdir()
    (scene_dir / "scene.js").write_text("load_binary_block('/media/a_guid_scene/p0.bin', mesh0);")
    (scene_dir / "p0.bin").write_text("binary_data")
    html_content = '<script src="/media/a_guid_scene/scene.js"></script>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=False,
    )
    exporter.export()
    copied_scene_js = output_dir / "media" / "a_guid_scene_scene.js"
    assert copied_scene_js.exists()
    scene_js_content = copied_scene_js.read_text()
    assert "load_binary_block('data:application/octet-stream;base64," in scene_js_content


def test_filemap_cache(exporter_setup, monkeypatch):
    """Test that the filemap cache prevents processing the same file multiple times."""
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/user_image.png"><img src="/media/user_image.png"></html>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
    )
    original_read_bytes = Path.read_bytes
    call_count = 0

    def spy_read_bytes(self, *args, **kwargs):
        if self.name == "user_image.png":
            nonlocal call_count
            call_count += 1
        return original_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)
    exporter.export()
    assert call_count == 1


def test_save_datauri_source_debug_env_var(exporter_setup, monkeypatch):
    """
    Test the debug feature to save sources of inlined assets.
    This requires using a file type that is inlined by default, like a scene file.
    """
    output_dir, static_dir, media_dir = exporter_setup
    (media_dir / "scene.avz").write_text("scene_data")
    html_content = '<html><a href="/media/scene.avz">link</a></html>'
    monkeypatch.setenv("NEXUS_REPORT_DOWNLOAD_SAVE_DATAURI_SOURCE", "1")
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=False,
    )
    exporter.export()
    # Check that the source file was saved in media, even though it was inlined
    assert (output_dir / "media" / "scene.avz").exists()
    final_html_content = (output_dir / "index.html").read_text()
    assert 'href="data:application/octet-stream;base64,' in final_html_content


def test_viewer_size_exception(exporter_setup):
    """Test size exception handling for the ansys-nexus-viewer."""
    output_dir, static_dir, media_dir = exporter_setup
    (media_dir / "scene.avz").write_text("large_scene_data")
    html_content = '<ansys-nexus-viewer src="/media/scene.avz"></ansys-nexus-viewer>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=False,
    )
    exporter._max_inline_size = 0
    exporter.export()
    final_html_content = (output_dir / "index.html").read_text()
    assert (
        'src="" proxy_only="3D geometry too large for stand-alone HTML file"' in final_html_content
    )


def test_unreadable_source_file(exporter_setup, monkeypatch, caplog):
    """Test that an OSError during file reading is handled gracefully."""
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/user_image.png"></html>'

    def raise_os_error(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "read_bytes", raise_os_error)
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
    )
    # Correctly set the level on the logger the exporter will use
    exporter._logger.setLevel(logging.WARNING)
    with caplog.at_level(logging.WARNING):
        exporter.export()
    final_html_content = (output_dir / "index.html").read_text()
    assert 'src="/media/user_image.png"' in final_html_content
    assert "Warning: Unable to read file" in caplog.text
    assert "Permission denied" in caplog.text


def test_logger_initialization(tmp_path):
    """Test that the logger is correctly initialized."""
    exporter_default = ServerlessReportExporter(
        html_content="",
        output_dir=tmp_path,
        static_dir=tmp_path,
        media_dir=tmp_path,
        logger=None,
    )
    assert exporter_default._logger is not None
    custom_logger = logging.getLogger("custom_test_logger")
    exporter_custom = ServerlessReportExporter(
        html_content="",
        output_dir=tmp_path,
        static_dir=tmp_path,
        media_dir=tmp_path,
        logger=custom_logger,
    )
    assert exporter_custom._logger is custom_logger


def test_no_inline_creates_special_files_and_dirs(exporter_setup):
    """Verify that no_inline_files=True copies special files and creates directories."""
    output_dir, static_dir, media_dir = exporter_setup
    exporter = ServerlessReportExporter(
        html_content="",
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=True,
        # The test MUST pass the version for the directory to be created correctly
        ansys_version=ANSYS_VERSION_FALLBACK,
    )
    exporter.export()
    font_file = FONTS[0]
    assert (output_dir / "webfonts" / font_file).exists()
    assert (output_dir / "webfonts" / font_file).read_text() == "fake_font_data"
    assert (output_dir / f"ansys{ANSYS_VERSION_FALLBACK}" / "nexus" / "utils").is_dir()


def test_missing_static_source_file_warning(exporter_setup, caplog):
    """Test that a warning is logged if a special static file is missing."""
    output_dir, static_dir, media_dir = exporter_setup
    (static_dir / "website" / "webfonts" / FONTS[0]).unlink()
    exporter = ServerlessReportExporter(
        html_content="",
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=True,
    )
    # Correctly set the level on the logger the exporter will use
    exporter._logger.setLevel(logging.WARNING)
    with caplog.at_level(logging.WARNING):
        exporter.export()
    assert "Warning: Static source file not found" in caplog.text
    assert FONTS[0] in caplog.text


def test_path_with_no_surrounding_quotes_is_skipped(exporter_setup):
    """Test that a path not in quotes is skipped."""
    output_dir, static_dir, media_dir = exporter_setup
    html_content = "Some documentation refers to /media/ for user files."
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
    )
    exporter.export()
    final_html_content = (output_dir / "index.html").read_text()
    assert final_html_content == html_content


def test_path_with_no_closing_quote(exporter_setup):
    """Test that a malformed HTML attribute with no closing quote is handled."""
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<img src="/media/user_image.png'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
    )
    exporter.export()
    final_html_content = (output_dir / "index.html").read_text()
    assert final_html_content == html_content


def test_static_file_no_inline_rewrite(exporter_setup):
    """
    Test that a generic /static/ file is correctly copied and rewritten to ./media/.
    This confirms faithful reproduction of the original implementation's logic.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><link rel="stylesheet" href="/static/website/content/site.css"></html>'
    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=True,
    )
    exporter.export()
    # Original logic places all non-versioned-static files in the media directory
    copied_file = output_dir / "media" / "site.css"
    assert not (output_dir / "static").exists()  # No output static dir should be made
    assert copied_file.exists()
    assert copied_file.read_text() == "body {}"
    final_html_content = (output_dir / "index.html").read_text()
    assert 'href="./media/site.css"' in final_html_content
