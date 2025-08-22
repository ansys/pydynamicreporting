import os
from pathlib import Path

import pytest

from ansys.dynamicreporting.core.serverless.html_exporter import ServerlessReportExporter
from ansys.dynamicreporting.core.utils.html_export_constants import (
    ANSYS_VERSION_FALLBACK,
)


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
    media_dir.mkdir()

    # Create dummy files in the correct locations
    (static_dir / "website" / "content" / "site.css").write_text("body {}")
    (versioned_static_dir / "play.png").write_text("fake_png_data")
    (media_dir / "user_image.png").write_text("fake_user_png_data")

    return output_dir, static_dir, media_dir


def test_export_into_db_directory_fails(exporter_setup):
    """
    Verifies that the export raises a ValueError if the output directory
    appears to be a Nexus database directory.
    """
    output_dir, static_dir, media_dir = exporter_setup
    # Create the marker file that indicates a database directory
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


def test_process_media_file(exporter_setup):
    """
    Tests that a file referenced from the /media/ path is correctly copied.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><body><img src="/media/user_image.png"></body></html>'

    exporter = ServerlessReportExporter(
        html_content=html_content, output_dir=output_dir, static_dir=static_dir, media_dir=media_dir
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
    Tests that a file with a versioned path is handled correctly.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = f'<html><body><img src="/ansys{ANSYS_VERSION_FALLBACK}/nexus/images/play.png"></body></html>'

    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        ansys_version=ANSYS_VERSION_FALLBACK,
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
    Tests that if two different files have the same name, the exporter avoids collision.
    """
    output_dir, static_dir, media_dir = exporter_setup
    (static_dir / "website" / "images").mkdir(parents=True)
    (static_dir / "website" / "images" / "user_image.png").write_text("different_fake_data")

    html_content = '<html><img src="/media/user_image.png"><img src="/static/website/images/user_image.png"></html>'

    exporter = ServerlessReportExporter(
        html_content=html_content, output_dir=output_dir, static_dir=static_dir, media_dir=media_dir
    )
    exporter.export()

    media_files = os.listdir(output_dir / "media")
    assert len(media_files) == 2
    assert "user_image.png" in media_files
    assert any(f.endswith("_user_image.png") for f in media_files)


def test_inline_size_limit(exporter_setup):
    """
    Tests that a file exceeding the inline size limit is not inlined, even in single_file mode.
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
        single_file=True,
    )
    exporter._max_inline_size = 0
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    assert "data:application/octet-stream;base64," not in final_html_content
    assert (output_dir / "media" / "large_file.bin").exists()


def test_inline_ansys_viewer(exporter_setup):
    """
    Tests the special handling for the ansys-nexus-viewer component in single-file mode.
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
        single_file=True,
    )
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    assert final_html_content.count("data:application/octet-stream;base64,") == 2
    assert 'src_ext="AVZ"' in final_html_content


def test_missing_file_handling(exporter_setup, capsys):
    """
    Tests that if a file in the HTML is not found on disk, it leaves the path as is.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/non_existent_file.png"></html>'

    exporter = ServerlessReportExporter(
        html_content=html_content, output_dir=output_dir, static_dir=static_dir, media_dir=media_dir
    )
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    assert 'src="/media/non_existent_file.png"' in final_html_content


def test_unreadable_source_file(exporter_setup, monkeypatch):
    """
    Tests that an OSError during file reading is handled gracefully.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/user_image.png"></html>'

    # Mock Path.read_bytes to raise an OSError
    def raise_os_error(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr(Path, "read_bytes", raise_os_error)

    exporter = ServerlessReportExporter(
        html_content=html_content, output_dir=output_dir, static_dir=static_dir, media_dir=media_dir
    )
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    # The original path should be preserved if the file is unreadable
    assert 'src="/media/user_image.png"' in final_html_content


def test_scene_file_forces_inline(exporter_setup):
    """
    Tests that a scene file (.avz) is inlined even when single_file is False.
    """
    output_dir, static_dir, media_dir = exporter_setup
    (media_dir / "scene.avz").write_text("scene_data")
    html_content = '<html><a href="/media/scene.avz">Scene</a></html>'

    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        single_file=False,  # Note: directory mode
    )
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    # The scene file should be inlined regardless of the single_file setting
    assert 'href="data:application/octet-stream;base64,' in final_html_content


def test_save_datauri_source_debug_env_var(exporter_setup, monkeypatch):
    """
    Tests the debug feature to save sources of inlined assets.
    """
    output_dir, static_dir, media_dir = exporter_setup
    html_content = '<html><img src="/media/user_image.png"></html>'

    # Set the environment variable to enable the debug feature
    monkeypatch.setenv("NEXUS_REPORT_DOWNLOAD_SAVE_DATAURI_SOURCE", "1")

    exporter = ServerlessReportExporter(
        html_content=html_content,
        output_dir=output_dir,
        static_dir=static_dir,
        media_dir=media_dir,
        single_file=True,
    )
    exporter.export()

    # Check that the inlined file was ALSO saved to the media directory
    assert (output_dir / "media" / "user_image.png").exists()


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
        single_file=False,
    )
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    # Check that the script path was rewritten correctly
    assert 'src="./media/a_guid_scene_scene.js"' in final_html_content

    # Check that the scene.js file was copied with the new name
    copied_scene_js = output_dir / "media" / "a_guid_scene_scene.js"
    assert copied_scene_js.exists()

    # Check that the content of scene.js was modified to inline the binary block
    scene_js_content = copied_scene_js.read_text()
    assert "load_binary_block('data:application/octet-stream;base64," in scene_js_content


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
        single_file=True,
    )
    # Trigger the size exception
    exporter._max_inline_size = 0
    exporter.export()

    final_html_content = (output_dir / "index.html").read_text()
    # Verify the src was replaced with the proxy_only attribute
    assert (
        'src="" proxy_only="3D geometry too large for stand-alone HTML file"' in final_html_content
    )


def test_filemap_cache(exporter_setup):
    """
    Tests that the filemap cache prevents processing the same file multiple times.
    """
    output_dir, static_dir, media_dir = exporter_setup
    # Reference the same file twice
    html_content = '<html><img src="/media/user_image.png"><img src="/media/user_image.png"></html>'

    exporter = ServerlessReportExporter(
        html_content=html_content, output_dir=output_dir, static_dir=static_dir, media_dir=media_dir
    )

    # Spy on the _process_file method to count its calls
    original_process_file = exporter._process_file
    call_count = 0

    def spy_process_file(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_process_file(*args, **kwargs)

    exporter._process_file = spy_process_file

    exporter.export()

    # _process_file should only have been called once due to caching
    assert call_count == 1
