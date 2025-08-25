import base64
import os
from pathlib import Path
import re
from typing import Any

from ..adr_utils import get_logger

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
        no_inline_files: bool = False,
        ansys_version: str = None,
        dark_mode: bool = True,
        debug: bool = False,
        logger: Any = None,
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
        self._logger = logger or get_logger()
        self._no_inline = no_inline_files
        self._ansys_version = ansys_version
        self._dark_mode = dark_mode

        # State tracking properties, functionally identical to ReportDownloadHTML
        self._filemap: dict[str, str] = {}
        self._replaced_file_ext: str | None = None
        self._collision_count = 0
        self._total_data_uri_size = 0
        self._max_inline_size = 1024 * 1024 * 500  # 500MB
        self._inline_size_exception = False

    def _should_use_data_uri(self, size: int) -> bool:
        """Determines if an asset should be inlined based on settings and size limits."""
        self._inline_size_exception = False
        if self._no_inline:
            return False
        # Base64 adds ~33% overhead; `size` should already include that estimate from caller.
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

        # Always copy special files (parity with legacy so offline references never break)
        self._copy_special_files()

        html = self._html_content
        html = self._replace_blocks(html, "<link", ">")
        html = self._replace_blocks(html, "<img id='guiicon", ">")
        html = self._replace_blocks(html, "e.src = '", "';")
        html = self._replace_blocks(html, "<script src=", "</script>")
        html = self._replace_blocks(html, "<a href=", ">")
        html = self._replace_blocks(html, "<img src=", ">")
        html = self._replace_blocks(html, "<source src=", ">")
        html = self._replace_blocks(html, ".key_images = {", ".update();")
        # Always inline viewer/fetch payloads for portability
        html = self._replace_blocks(html, "GLTFViewer", ");", inline=True)
        html = self._inline_ansys_viewer(html)
        html = self._replace_blocks(html, "await fetch(", ");", inline=True)

        # If the template rendered a fragment (a <div>), wrap it into a full document
        final_html = self._wrap_full_document(html)

        (self._output_dir / self._filename).write_text(final_html, encoding="utf8")

    def _wrap_full_document(self, html_fragment_or_doc: str) -> str:
        """
        If `html_fragment_or_doc` already looks like a full HTML document, return it unchanged.
        Otherwise, wrap it in a legacy-compatible shell (doctype, html/head/body) including title & favicon.
        """
        text = html_fragment_or_doc.lstrip()

        # Already a full document? Return as-is.
        lowered = text[:2000].lower()
        if lowered.startswith("<!doctype") or "<html" in lowered:
            return html_fragment_or_doc

        # Build a minimal, legacy-compatible head. We do NOT move/duplicate the
        # <link>/<script> tags from the fragment; we keep them where they are.
        # The fragment already contains CSS/JS and MathJax config. Here we just
        # add meta, title, and favicon to match legacy expectations.
        head = f"""
            <!DOCTYPE html>\n
            <html data-bs-theme="{'dark' if self._dark_mode else 'light'}" xmlns="http://www.w3.org/1999/html">\n
            <head>\n
                <meta charset="UTF-8"/>\n
                <meta name="viewport" content="width=device-width, initial-scale=1.0">\n
                <title>Report - ADR</title>\n
                <link rel="shortcut icon" href="./media/favicon.ico"/>\n
            </head>\n
            """

        # Body: include the fragment as-is (it already contains <link>/<script> blocks in correct order)
        body_open = '    <body style="padding: 0;">\n'
        # If the fragment already uses a wrapper like <div class="body-content ..."> keep it; otherwise
        # we could optionally wrap with <main>. To avoid duplication, we just drop it in verbatim.
        body_content = text
        return_to_top = (
            '\n<a href="#" id="return_to_top"><i class="fas fa-chevron-up fa-2x"></i></a>\n'
        )
        body_close = "    </body>\n</html>\n"

        return head + body_open + body_content + return_to_top + body_close

    def _replace_files(self, text: str, inline: bool = False, size_check: bool = False) -> str:
        """
        Finds, processes, and replaces all asset references within a given block of text
        using a regular expression for cleaner parsing.
        """
        self._replaced_file_ext = None
        current = 0

        # Support absolute and "./" relative paths for the key prefixes.
        # Examples matched:
        #   /static/..., ./static/...
        #   /media/...,  ./media/...
        #   /ansys261/..., ./ansys261/...
        #   /static/ansys261/..., ./static/ansys261/...
        ver = re.escape(str(self._ansys_version)) if self._ansys_version is not None else r"\d+"
        path_prefix_pattern = re.compile(
            rf"(\.?/static/ansys{ver}/|\.?/static/|\.?/media/|\.?/ansys{ver}/)"
        )

        while True:
            match = path_prefix_pattern.search(text, current)
            if not match:
                return text

            idx1 = match.start()

            # Heuristic: path is inside an attribute if preceded by a quote
            quote = text[idx1 - 1]
            if quote not in ('"', "'"):
                current = match.end()
                continue

            try:
                idx2 = text.index(quote, idx1)
            except ValueError:
                # No closing quote -> stop processing this block safely
                return text

            path_in_html = text[idx1:idx2]  # As it appears in HTML (could be ./...)
            simple_path = path_in_html.split("?")[0]  # Strip query/cache-busters
            _, ext = os.path.splitext(simple_path)
            self._replaced_file_ext = ext

            new_path = self._process_file(path_in_html, simple_path, inline=inline)
            if size_check and self._inline_size_exception:
                new_path = "__SIZE_EXCEPTION__"

            text = text[:idx1] + new_path + text[idx2:]
            current = idx1 + len(new_path)

    def _copy_special_files(self):
        """
        Copies static assets that are referenced indirectly (inside JS) or expected
        by the legacy layout into the output directory.
        """
        # --- MathJax (core + fonts) ---
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
            "website/scripts/mathjax/MathJax.js",  # important: top-level loader
            "website/images/MenuArrow-15.png",
        ]
        for f in mathjax_files:
            target_path = "media/" + (
                f.split("mathjax/")[-1] if "mathjax/" in f else os.path.basename(f)
            )
            self._copy_static_file(f, target_path)

        # --- Favicon (legacy page expected ./media/favicon.ico) ---
        self._copy_static_file("website/images/favicon.ico", "media/favicon.ico")

        # --- Nexus + old viewer images ---
        # 1) Keep a copy in ./media (some templates refer there)
        for img in NEXUS_IMAGES + VIEWER_IMAGES_OLD:
            self._copy_static_file(f"website/images/{img}", f"media/{img}")

        # 2) Ensure they also exist under ./ansys{ver}/nexus/images (viewer expects this path)
        # primary -> ansys{ver}/nexus/images/<img>, fallback -> website/images/<img>
        def _copy_ansys_image_with_fallback(img_name: str):
            primary_src = f"ansys{self._ansys_version}/nexus/images/{img_name}"
            primary_src_file = self._static_dir / primary_src
            target = f"ansys{self._ansys_version}/nexus/images/{img_name}"

            if primary_src_file.is_file():
                self._copy_static_file(primary_src, target)
            else:
                # Fallback: copy from website/images into the ansys images target
                fallback_src = f"website/images/{img_name}"
                self._copy_static_file(fallback_src, target)

        for img in set(NEXUS_IMAGES + VIEWER_IMAGES_OLD + ["proxy_viewer.png", "play.png"]):
            _copy_ansys_image_with_fallback(img)

        # --- Modern viewer payload kept under ./ansys{ver}/... ---
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

        # --- Webfonts (kept in ./webfonts like legacy) ---
        self._copy_static_files(FONTS, "website/webfonts/", "webfonts/")

    def _copy_static_file(self, source_rel_path: str, target_rel_path: str):
        """Helper to copy a single file from the static source to the output directory."""
        source_file = self._static_dir / source_rel_path
        target_file = self._output_dir / target_rel_path
        if source_file.is_file():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            content = source_file.read_bytes()
            # Patch some viewer JS internals (loader/paths) if needed
            content = ReportDownloadHTML.fix_viewer_component_paths(
                str(target_file), content, self._ansys_version
            )
            target_file.write_bytes(content)
        else:
            self._logger.warning(f"Warning: Static source file not found: {source_file}")

    def _copy_static_files(self, files: list[str], source_prefix: str, target_prefix: str):
        """Helper to copy a list of files using prefixes."""
        for f in files:
            self._copy_static_file(source_prefix.lstrip("/") + f, target_prefix + f)

    def _make_unique_basename(self, name: str) -> str:
        """Ensures a unique filename in the target media directory to avoid collisions."""
        if not self._no_inline:
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

        # Normalize paths: accept './prefix/...' and absolute '/prefix/...'
        normalized = simple_path
        if normalized.startswith("./"):
            normalized = normalized[1:]  # -> '/static/...' or '/ansys...'
        if not normalized.startswith("/"):
            normalized = "/" + normalized

        # Collapse duplicate slashes early (prevents 'ansys261//nexus/...').
        normalized = re.sub(r"/{2,}", "/", normalized)

        relative_path = normalized.lstrip("/")

        # Resolve the source file based on the normalized prefix
        if normalized.startswith("/media/"):
            source_file = self._media_dir / relative_path.replace("media/", "", 1)
        elif normalized.startswith("/static/"):
            source_file = self._static_dir / relative_path.replace("static/", "", 1)
        elif normalized.startswith(f"/ansys{self._ansys_version}/"):
            source_file = self._static_dir / relative_path
        else:
            source_file = None

        if source_file is None or not source_file.is_file():
            self._logger.warning(f"Warning: Unable to find local file for path: {simple_path}")
            self._filemap[simple_path] = path_in_html
            return path_in_html

        try:
            content = source_file.read_bytes()
        except OSError as e:
            self._logger.warning(f"Warning: Unable to read file {source_file}: {e}")
            self._filemap[simple_path] = path_in_html
            return path_in_html

        basename = self._make_unique_basename(source_file.name)

        # Base64 encoding increases size by ~4/3 (estimate used for cap check)
        estimated_inline_size = int(len(content) * (4 / 3))

        if (inline or ReportDownloadHTML.is_scene_file(normalized)) and self._should_use_data_uri(
            estimated_inline_size
        ):
            encoded_content = base64.b64encode(content).decode("utf-8")
            result = f"data:application/octet-stream;base64,{encoded_content}"
            # Optional debug: persist the original bytes
            if "NEXUS_REPORT_DOWNLOAD_SAVE_DATAURI_SOURCE" in os.environ:
                filename = self._output_dir / "media" / basename
                filename.parent.mkdir(parents=True, exist_ok=True)
                filename.write_bytes(content)
        else:
            # Babylon.js scene files: inline internal binary blocks & namespace name by GUID folder
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

            # Where to write & how to reference:
            if normalized.startswith(
                f"/static/ansys{self._ansys_version}/"
            ) or normalized.startswith(f"/ansys{self._ansys_version}/"):
                # Keep the ansys{ver} tree as-is in the output (legacy)
                # IMPORTANT: strip the '/static/' prefix if present
                path_no_static = normalized.replace("/static/", "/", 1)
                local_pathname = Path(path_no_static).parent.as_posix().lstrip("/")
                local_pathname = re.sub(r"/{2,}", "/", local_pathname)

                result = f"./{local_pathname}/{basename}"
                result = "./" + re.sub(r"/{2,}", "/", result[2:])  # ensure no '//' in result
                target_file = self._output_dir / local_pathname / basename

            elif normalized.startswith("/static/"):
                # Legacy behavior: flatten other static assets into ./media/
                result = f"./media/{basename}"
                target_file = self._output_dir / "media" / basename
            else:  # /media/
                result = f"./media/{basename}"
                target_file = self._output_dir / "media" / basename

            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(content)

        self._filemap[simple_path] = result
        return result

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

            # Legacy parity: always inline viewer attributes
            text = self._replace_blocks(text_block, 'proxy_img="', '"', inline=True)
            text = self._replace_blocks(text, 'src="', '"', inline=True, size_check=True)

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

        dirs_to_create = [
            # MathJax (partial structure mirrored; files will ensure subfolders exist)
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
            # Viewer
            f"ansys{self._ansys_version}/nexus/images",
            f"ansys{self._ansys_version}/nexus/utils",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf",
            f"ansys{self._ansys_version}/nexus/novnc/vendor/jQuery-contextMenu",
        ]
        for d in dirs_to_create:
            (self._output_dir / d).mkdir(parents=True, exist_ok=True)
