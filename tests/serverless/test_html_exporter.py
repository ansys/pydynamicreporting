from pathlib import Path
import pytest

from ansys.dynamicreporting.core.serverless.html_exporter import ServerlessReportExporter

# Import the constant to make the test dynamic and avoid hardcoding
from ansys.dynamicreporting.core.serverless.utils.html_export_constants import (
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

    # FIX: The original test incorrectly counted subdirectories. This now correctly counts only files.
    files_in_media = [f for f in (output_dir / "media").iterdir() if f.is_file()]
    assert len(files_in_media) == 2
    assert (output_dir / "media" / "user_image.png").exists()
    assert (output_dir / "media" / "1_user_image.png").exists()


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
        single_file=False,
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
        single_file=False,
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
        html_content=html_content, output_dir=output_dir, static_dir=static_dir, media_dir=media_dir
    )

    # FIX: Spy on a lower-level function that is only called on a cache miss.
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
