import base64
import os
from pathlib import Path
import re
from typing import Any

# Import the shared constants and file lists
from ..utils.html_export_constants import (
    CONTEXT_MENU_JS,
    DRACO_JS,
    FONTS,
    NEXUS_IMAGES,
    THREE_JS,
    VIEWER_IMAGES_OLD,
    VIEWER_JS,
    VIEWER_UTILS,
)
from ..utils.report_download_html import ReportDownloadHTML


class ServerlessReportExporter:
    """
    Handles the serverless exportation of an ADR report to a standalone HTML file or directory.

    This class is a serverless adaptation of the original ReportDownloadHTML class. It
    takes a rendered HTML string and local paths to assets, then processes the HTML to
    produce a self-contained report. It achieves this by either embedding assets as
    Base64 data URIs or by copying them to a structured output directory and rewriting
    paths to be relative.
    """

    def __init__(
        self,
        html_content: str,
        output_dir: Path,
        static_dir: Path,
        media_dir: Path,
        *,
        filename: str = "index.html",
        single_file: bool = False,
        ansys_version: str = None,
        debug: bool = False,
    ):
        """
        Initializes the serverless exporter.
        """
        self._html_content = html_content
        self._output_dir = output_dir
        self._static_dir = static_dir
        self._media_dir = media_dir
        self._filename = filename
        self._debug = debug
        self._single_file = single_file
        self._ansys_version = ansys_version

        # State tracking properties, functionally identical to ReportDownloadHTML
        self._filemap = {}
        self._replaced_file_ext = None
        self._collision_count = 0
        self._total_data_uri_size = 0
        self._max_inline_size = 1024 * 1024 * 500  # 500MB
        self._inline_size_exception = False

    def _should_use_data_uri(self, size: int) -> bool:
        """Determines if an asset should be inlined based on settings and size limits."""
        self._inline_size_exception = False
        if not self._single_file:
            return False
        if self._total_data_uri_size + size > self._max_inline_size:
            self._inline_size_exception = True
            return False
        self._total_data_uri_size += size
        return True

    def export(self) -> None:
        """Main method to start the export process."""
        self._filemap = {}
        if os.path.isfile(os.path.join(self._output_dir, "db.sqlite3")):
            raise ValueError("Cannot export into a Nexus database directory")

        self._make_output_dirs()

        if self._debug:
            (self._output_dir / "index.raw.html").write_text(self._html_content, encoding="utf8")

        if not self._single_file:
            self._copy_special_files()

        html = self._html_content
        html = self._replace_blocks(html, "<link", "/>")
        html = self._replace_blocks(html, "<img id='guiicon", ">")
        html = self._replace_blocks(html, "e.src = '", "';")
        html = self._replace_blocks(html, "<script src=", "</script>")
        html = self._replace_blocks(html, "<a href=", ">")
        html = self._replace_blocks(html, "<img src=", ">")
        html = self._replace_blocks(html, "<source src=", ">")
        html = self._replace_blocks(html, ".key_images = {", ".update();")
        html = self._replace_blocks(html, "GLTFViewer", ");", inline=self._single_file)
        html = self._inline_ansys_viewer(html)
        html = self._replace_blocks(html, "await fetch(", ");", inline=self._single_file)

        (self._output_dir / self._filename).write_text(html, encoding="utf8")

    def _replace_files(
        self, text: str, inline: bool = False, size_check: bool = False
    ) -> str | None:
        """
        Finds, processes, and replaces all asset references within a given block of text
        using a regular expression for cleaner parsing.
        """
        self._replaced_file_ext = None
        current = 0

        # This regex pattern finds any of the valid asset path prefixes.
        path_prefix_pattern = re.compile(
            f"(/static/ansys{self._ansys_version}/|/static/|/media/|/ansys{self._ansys_version}/)"
        )

        while True:
            # Search for the next asset path from the current position.
            match = path_prefix_pattern.search(text, current)

            # If no more matches are found, the processing is complete for this block.
            if not match:
                return text

            idx1 = match.start()

            # A simple heuristic to ensure we're processing a path inside an HTML attribute.
            # It checks if the character preceding the path is a quote.
            quote = text[idx1 - 1]
            if quote not in ('"', "'"):
                # This was likely not a real path; continue searching from after this match.
                current = match.end()
                continue

            try:
                # Find the corresponding closing quote to delimit the full path.
                idx2 = text.index(quote, idx1)
            except ValueError:
                # If there's no closing quote, the rest of the string is un-parseable.
                return text

            # Extract the path and process it.
            path_in_html = text[idx1:idx2]
            simple_path = path_in_html.split("?")[0]
            (_, ext) = os.path.splitext(simple_path)
            self._replaced_file_ext = ext

            new_path = self._process_file(path_in_html, simple_path, inline=inline)

            if size_check and self._inline_size_exception:
                new_path = "__SIZE_EXCEPTION__"

            # Rebuild the text with the new path.
            text = text[:idx1] + new_path + text[idx2:]
            # Update the search position to prevent re-processing the same block.
            current = idx1 + len(new_path)

    def _copy_special_files(self):
        """Copies all hardcoded static files required for the report to function offline."""
        # MathJax files
        mathjax_files = [
            "website/scripts/mathjax/jax/input/TeX/config.js",
            "website/scripts/mathjax/jax/input/MathML/config.js",
            "website/scripts/mathjax/jax/input/AsciiMath/config.js",
            "website/scripts/mathjax/extensions/tex2jax.js",
            "website/scripts/mathjax/extensions/mml2jax.js",
            "website/scripts/mathjax/extensions/asciimath2jax.js",
            "website/scripts/mathjax/extensions/MathZoom.js",
            "website/scripts/mathjax/extensions/MathMenu.js",
            "website/scripts/mathjax/extensions/MathEvents.js",
            "website/scripts/mathjax/jax/element/mml/jax.js",
            "website/scripts/mathjax/jax/input/TeX/jax.js",
            "website/scripts/mathjax/extensions/TeX/AMSmath.js",
            "website/scripts/mathjax/extensions/TeX/AMSsymbols.js",
            "website/scripts/mathjax/extensions/TeX/noErrors.js",
            "website/scripts/mathjax/extensions/TeX/noUndefined.js",
            "website/scripts/mathjax/config/TeX-AMS-MML_SVG.js",
            "website/scripts/mathjax/jax/output/SVG/jax.js",
            "website/scripts/mathjax/jax/output/SVG/fonts/TeX/fontdata.js",
            "website/scripts/mathjax/jax/output/SVG/fonts/TeX/Main/Regular/BasicLatin.js",
            "website/scripts/mathjax/jax/output/SVG/fonts/TeX/Size1/Regular/Main.js",
            "website/images/MenuArrow-15.png",
        ]
        for f in mathjax_files:
            # The target path is intentionally "mangled" to place MathJax assets in the
            # media directory
            target_path = "media/" + f.split("mathjax/")[-1]
            self._copy_static_file(f, target_path)

        # Nexus and old viewer images
        for img in NEXUS_IMAGES + VIEWER_IMAGES_OLD:
            self._copy_static_file(f"website/images/{img}", f"media/{img}")

        # Modern viewer assets
        viewer_images_new = VIEWER_IMAGES_OLD + ["proxy_viewer.png", "play.png"]
        self._copy_static_files(
            viewer_images_new,
            f"ansys{self._ansys_version}/nexus/images/",
            f"ansys{self._ansys_version}/nexus/images/",
        )
        self._copy_static_files(
            VIEWER_UTILS,
            f"ansys{self._ansys_version}/nexus/utils/",
            f"ansys{self._ansys_version}/nexus/utils/",
        )
        self._copy_static_files(
            VIEWER_JS, f"ansys{self._ansys_version}/nexus/", f"ansys{self._ansys_version}/nexus/"
        )
        self._copy_static_files(
            CONTEXT_MENU_JS,
            f"ansys{self._ansys_version}/nexus/novnc/vendor/jQuery-contextMenu/",
            f"ansys{self._ansys_version}/nexus/novnc/vendor/jQuery-contextMenu/",
        )
        self._copy_static_files(
            THREE_JS,
            f"ansys{self._ansys_version}/nexus/threejs/",
            f"ansys{self._ansys_version}/nexus/threejs/",
        )
        self._copy_static_files(
            DRACO_JS,
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/",
        )
        self._copy_static_files(
            DRACO_JS,
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf/",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf/",
        )

        # Fonts
        self._copy_static_files(FONTS, "website/webfonts/", "webfonts/")

    def _copy_static_file(self, source_rel_path: str, target_rel_path: str):
        """Helper to copy a single file from the static source to the output directory."""
        source_file = self._static_dir / source_rel_path
        target_file = self._output_dir / target_rel_path
        if source_file.is_file():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            content = source_file.read_bytes()
            # Use the imported utility to patch JS files for the viewer. This is
            # necessary to adjust internal asset paths within the viewer's code.
            content = ReportDownloadHTML.fix_viewer_component_paths(
                str(target_file), content, self._ansys_version
            )
            target_file.write_bytes(content)
        else:
            print(f"Warning: Static source file not found: {source_file}")

    def _copy_static_files(self, files: list, source_prefix: str, target_prefix: str):
        """Helper to copy a list of files using prefixes."""
        for f in files:
            self._copy_static_file(source_prefix.lstrip("/") + f, target_prefix + f)

    def _make_unique_basename(self, name: str) -> str:
        """Ensures a unique filename in the target media directory to avoid collisions."""
        if self._single_file:
            return name
        target_path = self._output_dir / "media" / name
        if not target_path.exists():
            return name
        self._collision_count += 1
        return f"{self._collision_count}_{name}"

    def _process_file(self, path_in_html: str, simple_path: str, inline: bool = False) -> str:
        """Reads a file from local disk and either inlines it or copies it."""
        if simple_path in self._filemap:
            return self._filemap[simple_path]

        source_file = None
        relative_path = simple_path.lstrip("/")
        if simple_path.startswith("/media/"):
            source_file = self._media_dir / relative_path.replace("media/", "", 1)
        elif simple_path.startswith("/static/"):
            source_file = self._static_dir / relative_path.replace("static/", "", 1)
        elif simple_path.startswith(f"/ansys{self._ansys_version}/"):
            source_file = self._static_dir / relative_path

        if source_file is None or not source_file.is_file():
            print(f"Warning: Unable to find local file for path: {simple_path}")
            self._filemap[simple_path] = path_in_html
            return path_in_html

        try:
            content = source_file.read_bytes()
        except OSError as e:
            print(f"Warning: Unable to read file {source_file}: {e}")
            self._filemap[simple_path] = path_in_html
            return path_in_html

        basename = self._make_unique_basename(source_file.name)

        # Base64 encoding increases file size by a factor of 4/3. This calculation
        # estimates the new size to check against the inlining limit. Using float
        # division is crucial for accuracy, as integer division would underestimate the size.
        estimated_inline_size = int(len(content) * (4 / 3))

        if (inline or ReportDownloadHTML.is_scene_file(simple_path)) and self._should_use_data_uri(
            estimated_inline_size
        ):
            encoded_content = base64.b64encode(content).decode("utf-8")
            results = f"data:application/octet-stream;base64,{encoded_content}"
            # This block adds the debug feature for saving data URI sources
            if "NEXUS_REPORT_DOWNLOAD_SAVE_DATAURI_SOURCE" in os.environ:
                filename = self._output_dir / "media" / basename
                filename.parent.mkdir(parents=True, exist_ok=True)
                filename.write_bytes(content)
        else:
            # Babylon.js scene files require special handling to inline their binary assets.
            if basename.endswith("scene.js"):
                content_str = self._replace_blocks(
                    content.decode("utf-8"), "load_binary_block(", ");", inline=True
                )
                content = content_str.encode("utf-8")
                basename = f"{source_file.parent.name}_{basename}"
            else:
                content = ReportDownloadHTML.fix_viewer_component_paths(
                    basename, content, self._ansys_version
                )

            if simple_path.startswith(f"/static/ansys{self._ansys_version}/"):
                local_pathname = Path(simple_path).parent.as_posix().replace("/static/", "./")
                results = f"{local_pathname}/{basename}"
                target_file = self._output_dir / local_pathname.lstrip("./") / basename
            elif simple_path.startswith("/static/"):
                local_pathname = Path(simple_path).parent.as_posix()
                results = f".{local_pathname}/{basename}"
                target_file = self._output_dir / local_pathname.lstrip("/") / basename
            else:  # /media/
                results = f"./media/{basename}"
                target_file = self._output_dir / "media" / basename

            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(content)

        self._filemap[simple_path] = results
        return results

    def _replace_blocks(
        self, html: str, prefix: str, suffix: str, inline: bool = False, size_check: bool = False
    ) -> str:
        """Iteratively finds and replaces all asset references within matching blocks."""
        current_pos = 0
        while True:
            start, end, text_block = ReportDownloadHTML.find_block(
                html, current_pos, prefix, suffix
            )
            if start < 0:
                break
            processed_text = self._replace_files(text_block, inline=inline, size_check=size_check)
            html = html[:start] + processed_text + html[end:]
            current_pos = start + len(processed_text)
        return html

    def _inline_ansys_viewer(self, html: str) -> str:
        """Handles the special case of inlining assets for the <ansys-nexus-viewer> component."""
        current_pos = 0
        while True:
            start, end, text_block = ReportDownloadHTML.find_block(
                html, current_pos, "<ansys-nexus-viewer", "</ansys-nexus-viewer>"
            )
            if start < 0:
                break

            text = self._replace_blocks(text_block, 'proxy_img="', '"', inline=self._single_file)
            text = self._replace_blocks(
                text, 'src="', '"', inline=self._single_file, size_check=True
            )

            if "__SIZE_EXCEPTION__" in text:
                msg = "3D geometry too large for stand-alone HTML file"
                text = text.replace('src="__SIZE_EXCEPTION__"', f'src="" proxy_only="{msg}"')

            if self._replaced_file_ext and "data:application/octet-stream;base64," in text:
                ext = self._replaced_file_ext.replace(".", "").upper()
                text = text.replace("<ansys-nexus-viewer", f'<ansys-nexus-viewer src_ext="{ext}"')

            html = html[:start] + text + html[end:]
            current_pos = start + len(text)
        return html

    def _make_output_dirs(self):
        """Creates the necessary directory structure in the output location."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        if self._single_file:
            return

        dirs_to_create = [
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
            f"ansys{self._ansys_version}/nexus/images",
            f"ansys{self._ansys_version}/nexus/utils",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf",
            f"ansys{self._ansys_version}/nexus/novnc/vendor/jQuery-contextMenu",
            "static/website/css",
            "static/website/images",
            "static/website/scripts",
            "static/website/webfonts",
        ]
        for d in dirs_to_create:
            (self._output_dir / d).mkdir(parents=True, exist_ok=True)
