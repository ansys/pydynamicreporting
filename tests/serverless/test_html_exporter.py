import logging
from pathlib import Path

import pytest

from ansys.dynamicreporting.core.serverless.html_exporter import ServerlessReportExporter

# Import the constant to make the test dynamic and avoid hardcoding
from ansys.dynamicreporting.core.utils.html_export_constants import ANSYS_VERSION_FALLBACK, FONTS


# Fixture to create a temporary directory structure for testing the exporter
@pytest.fixture
def exporter_setup(tmp_path):
    """
    Sets up a temporary directory structure with output, static, and media folders,
    and populates them with some dummy files for testing the exporter.
    """
    output_dir = tmp_path / "output"
    static_dir = tmp_path / "static"
    media_dir = tmp_path / "media"

    # Use the imported constant to create the versioned directory
    versioned_static_dir = static_dir / f"ansys{ANSYS_VERSION_FALLBACK}" / "nexus" / "images"
    versioned_static_dir.mkdir(parents=True)

    # Create other necessary directories
    (static_dir / "website" / "content").mkdir(parents=True)
    (static_dir / "website" / "webfonts").mkdir(parents=True)
    media_dir.mkdir()

    # Create dummy files in the correct locations
    (static_dir / "website" / "content" / "site.css").write_text("body {}")
    (static_dir / "website" / "webfonts" / FONTS[0]).write_text("fake_font_data")
    (versioned_static_dir / "play.png").write_text("fake_png_data")
    (media_dir / "user_image.png").write_text("fake_user_png_data")

    return output_dir, static_dir, media_dir


def test_export_into_db_directory_fails(exporter_setup):
    """
    Verifies that the export raises a ValueError if the output directory
    appears to be a Nexus database directory.
    """
    output_dir, static_dir, media_dir = exporter_setup
    # The output directory must exist before a file can be created in it.
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
    """
    Verifies that when debug=True, the raw HTML file is saved.
    """
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
    """
    Tests that a file referenced from the /media/ path is correctly copied
    when no_inline_files is True.
    """
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
    assert final_html_path.exists()

    copied_media_path = output_dir / "media" / "user_image.png"
    assert copied_media_path.exists()
    assert copied_media_path.read_text() == "fake_user_png_data"

    final_html_content = final_html_path.read_text()
    assert 'src="./media/user_image.png"' in final_html_content


def test_process_ansys_versioned_file(exporter_setup):
    """
    Tests that a file with a versioned path is handled correctly when creating a directory.
    """
    output_dir, static_dir, media_dir = exporter_setup
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

    copied_file_path = (
        output_dir / f"ansys{ANSYS_VERSION_FALLBACK}" / "nexus" / "images" / "play.png"
    )
    assert copied_file_path.exists()

    final_html_content = (output_dir / "index.html").read_text()
    assert f'src="./ansys{ANSYS_VERSION_FALLBACK}/nexus/images/play.png"' in final_html_content


def test_filename_collision(exporter_setup):
    """
    Tests that if two files with the same name would be copied to the same
    target directory, the exporter avoids a filename collision.
    """
    output_dir, static_dir, media_dir = exporter_setup

    # Create a second file with the same name in a different source directory.
    # Both `/media/user_image.png` and `/media/another_dir/user_image.png`
    # will target the same output path: `output/media/user_image.png`.
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

    # Assert that both files exist in the output media directory, with one renamed
    assert (output_dir / "media" / "user_image.png").exists()
    assert (output_dir / "media" / "1_user_image.png").exists()

    # Verify the content of the renamed file to be sure
    assert (output_dir / "media" / "1_user_image.png").read_text() == "another_one"


def test_inline_size_limit(exporter_setup):
    """
    Tests that a file exceeding the inline size limit is not inlined.
    """
    output_dir, static_dir, media_dir = exporter_setup
    large_file_path = media_dir / "large_file.bin"
    large_file_path.write_text("A")

    html_content = '<html><a href="/media/large_file.bin">link</a></html>'

    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=False,  # Allow inlining
    )
    exporter._max_inline_size = 0
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    assert "data:application/octet-stream;base64," not in final_html_content
    assert (output_dir / "media" / "large_file.bin").exists()


def test_inline_ansys_viewer(exporter_setup):
    """
    Tests the special handling for the ansys-nexus-viewer component when inlining.
    """
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
    """
    Tests that if a file in the HTML is not found on disk, it leaves the path as is
    and logs a warning.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/non_existent_file.png"></html>'

    with caplog.at_level(logging.WARNING):
        exporter = ServerlessReportExporter(
            html_content=html_content,
            output_dir=output_dir,
            static_dir=static_dir,
            media_dir=media_dir,
        )
        exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    assert 'src="/media/non_existent_file.png"' in final_html_content
    assert (
        "Warning: Unable to find local file for path: /media/non_existent_file.png" in caplog.text
    )


def test_scene_file_is_inlined_by_default(exporter_setup):
    """
    Tests that a scene file (.avz) is inlined by default when no_inline_files is False.
    """
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
    """
    Tests the special case for handling babylon.js scene.js files.
    """
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
    """
    Tests that the filemap cache prevents processing the same file multiple times.
    """
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
    Tests the debug feature to save sources of inlined assets.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/user_image.png"></html>'

    monkeypatch.setenv("NEXUS_REPORT_DOWNLOAD_SAVE_DATAURI_SOURCE", "1")

    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=False,
    )
    exporter.export()

    assert (output_dir / "media" / "user_image.png").exists()
    final_html_content = (output_dir / "index.html").read_text()
    assert 'src="data:application/octet-stream;base64,' in final_html_content


def test_viewer_size_exception(exporter_setup):
    """
    Tests the specific size exception handling for the ansys-nexus-viewer.
    """
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
    """
    Tests that an OSError during file reading is handled gracefully and logged.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/user_image.png"></html>'

    def raise_os_error(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "read_bytes", raise_os_error)

    with caplog.at_level(logging.WARNING):
        exporter = ServerlessReportExporter(
            html_content=html_content,
            output_dir=output_dir,
            static_dir=static_dir,
            media_dir=media_dir,
        )
        exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    assert 'src="/media/user_image.png"' in final_html_content
    assert "Warning: Unable to read file" in caplog.text
    assert "Permission denied" in caplog.text


def test_logger_initialization(tmp_path):
    """
    Tests that the logger is correctly initialized, either with a provided
    logger or by creating a default one.
    """
    # Case 1: No logger provided, should create a default one
    exporter_default = ServerlessReportExporter(
        html_content="",
        output_dir=tmp_path,
        static_dir=tmp_path,
        media_dir=tmp_path,
        logger=None,
    )
    assert exporter_default._logger is not None

    # Case 2: A logger is provided
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
    """
    Verifies that when no_inline_files=True, the special required files (like fonts)
    are copied and the necessary directory structure is created.
    """
    output_dir, static_dir, media_dir = exporter_setup

    exporter = ServerlessReportExporter(
        html_content="",
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        no_inline_files=True,
    )
    exporter.export()

    # Check for a specific, non-trivial directory and file
    font_file = FONTS[0]
    assert (output_dir / "webfonts" / font_file).exists()
    assert (output_dir / "webfonts" / font_file).read_text() == "fake_font_data"
    assert (output_dir / f"ansys{ANSYS_VERSION_FALLBACK}" / "nexus" / "utils").is_dir()


def test_missing_static_source_file_warning(exporter_setup, caplog):
    """
    Tests that a warning is logged if a special static file is missing from the source.
    """
    output_dir, static_dir, media_dir = exporter_setup

    # Intentionally remove a file that _copy_special_files will look for
    (static_dir / "website" / "webfonts" / FONTS[0]).unlink()

    with caplog.at_level(logging.WARNING):
        exporter = ServerlessReportExporter(
            html_content="",
            output_dir=output_dir,
            static_dir=static_dir,
            media_dir=media_dir,
            no_inline_files=True,
        )
        exporter.export()

    assert "Warning: Static source file not found" in caplog.text
    assert FONTS[0] in caplog.text


def test_path_with_no_surrounding_quotes_is_skipped(exporter_setup):
    """
    Tests that the regex match is skipped if it's not preceded by a quote,
    preventing replacement of text that isn't a valid file path attribute.
    This covers the `if quote not in ('"', "'"): continue` branch.
    """
    output_dir, static_dir, media_dir = exporter_setup
    # This text contains a valid path prefix but isn't a real asset path
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
    """
    Tests that a malformed HTML attribute with no closing quote does not
    cause an error and the exporter gracefully stops processing the string.
    This covers the `except ValueError` in `_replace_files`.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<img src="/media/user_image.png'  # Malformed HTML, no closing quote

    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
    )
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    # The content should remain unchanged as parsing would fail and return
    assert final_html_content == html_content


def test_static_file_no_inline_rewrite(exporter_setup):
    """
    Tests that a generic /static/ file is correctly copied and its path rewritten
    when no_inline_files is True.
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

    copied_file = output_dir / "static" / "website" / "content" / "site.css"
    assert copied_file.exists()
    assert copied_file.read_text() == "body {}"

    final_html_content = (output_dir / "index.html").read_text()
    assert 'href="./static/website/content/site.css"' in final_html_content
