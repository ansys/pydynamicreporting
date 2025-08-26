import base64
import os
from pathlib import Path
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
        html = self._replace_blocks(html, "<link", "/>")
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
        body_close = "    </body>\n</html>\n"

        return head + body_open + text + body_close

    def _replace_files(self, text: str, inline: bool = False, size_check: bool = False) -> str:
        """
        Finds, processes, and replaces all asset references within a given block of text.

        IMPORTANT: This mirrors the legacy behavior exactly:
          - Only these prefixes are recognized, in this strict priority order:
              /static/ansys{ver}/, /static/, /media/, /ansys{ver}/
          - It picks the FIRST pattern in that list that occurs anywhere at/after `current`
            (it does NOT choose the earliest occurrence across all patterns).
          - No './' variants, no generic normalization.
        """
        self._replaced_file_ext = None
        current = 0
        ver = str(self._ansys_version) if self._ansys_version is not None else ""

        patterns = (
            f"/static/ansys{ver}/",
            "/static/",
            "/media/",
            f"/ansys{ver}/",
        )

        while True:
            # Find the next match using the legacy priority order
            idx1 = -1
            for pat in patterns:
                idx1 = text.find(pat, current)
                if idx1 != -1:
                    break
            if idx1 == -1:
                return text  # nothing more to replace

            # Legacy heuristic: assume we're inside an attribute quoted by the char before the path
            quote = text[idx1 - 1]
            idx2 = text.find(quote, idx1)
            if idx2 == -1:
                return text  # no closing quote -> stop processing this block safely

            path_in_html = text[idx1:idx2]  # includes any query string
            # Strip query/cache-buster for filesystem lookups (legacy parity)
            simple_path = path_in_html.split("?", 1)[0]

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

        # --- Favicon ---
        # Legacy HTML links to favicon.ico, but only favicon.png exists in static.
        # Copy favicon.png and duplicate it as favicon.ico.
        self._copy_static_file("website/images/favicon.png", "media/favicon.png")
        self._copy_static_file("website/images/favicon.png", "media/favicon.ico")

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

        # --- Legacy parity: copy jquery.min.js into ansys{ver}/nexus/utils ---
        self._copy_static_file(
            "website/scripts/jquery.min.js", f"ansys{self._ansys_version}/nexus/utils/jquery.min.js"
        )

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

    def _process_file(self, path_in_html: str, pathname: str, inline: bool = False) -> str:
        """
        Reads a file from local disk and either inlines it or copies it.
        - Source resolution by prefix:
            /media/  -> self._media_dir
            /static/ -> self._static_dir
            /ansys{ver}/ -> self._static_dir
        - Output path rule:
            if pathname startswith /static/ansys{ver}/ :
                keep ansys tree (remove '/static/' -> './...'), else
                write to ./media/<basename>
        - Handles scene.js renaming & inlining of its binary blocks.
        """
        if pathname in self._filemap:
            return self._filemap[pathname]

        # Resolve source file location based on the raw pathname (no normalization)
        if pathname.startswith("/media/"):
            source_file = self._media_dir / pathname.replace("/media/", "", 1)
        elif pathname.startswith("/static/"):
            source_file = self._static_dir / pathname.replace("/static/", "", 1)
        elif pathname.startswith(f"/ansys{self._ansys_version}/"):
            # Legacy downloads these from the server root; serverless reads them from static dir
            source_file = self._static_dir / pathname.lstrip("/")
        else:
            source_file = None

        if source_file is None or not source_file.is_file():
            self._logger.warning(f"Warning: Unable to find local file for path: {pathname}")
            self._filemap[pathname] = path_in_html
            return path_in_html

        try:
            content = source_file.read_bytes()
        except OSError as e:
            self._logger.warning(f"Warning: Unable to read file {source_file}: {e}")
            self._filemap[pathname] = path_in_html
            return path_in_html

        basename = self._make_unique_basename(source_file.name)

        # 4/3 is roughly the expansion factor of base64 encoding (3 bytes -> 4 chars)
        estimated_inline_size = int(len(content) * (4.0 / 3.0))

        if (inline or ReportDownloadHTML.is_scene_file(pathname)) and self._should_use_data_uri(
            estimated_inline_size
        ):
            # Inline as data URI
            encoded = base64.b64encode(content).decode("utf-8")
            result = f"data:application/octet-stream;base64,{encoded}"

            if "NEXUS_REPORT_DOWNLOAD_SAVE_DATAURI_SOURCE" in os.environ:
                fn = self._output_dir / "media" / basename
                fn.parent.mkdir(parents=True, exist_ok=True)
                fn.write_bytes(content)

            self._filemap[pathname] = result
            return result

        # Not inlined: special case for Babylon scene.js to inline its binary blocks & rename
        if basename.endswith("scene.js"):
            text = content.decode("utf-8")
            text = self._replace_blocks(text, "load_binary_block(", ");", inline=True)
            content = text.encode("utf-8")
            # prefix with parent folder (GUID) like legacy
            basename = f"{source_file.parent.name}_{basename}"
        else:
            content = ReportDownloadHTML.fix_viewer_component_paths(
                basename, content, self._ansys_version
            )

        # Output path (exact legacy behavior):
        # - If /static/ansys{ver}/ -> keep ansys tree, remove '/static/' -> './ansys{ver}/.../<basename>'
        # - Else -> './media/<basename>'
        if pathname.startswith(f"/static/ansys{self._ansys_version}/"):
            local_pathname = os.path.dirname(pathname).replace("/static/", "./", 1)
            result = f"{local_pathname}/{basename}"

            target_file = self._output_dir / local_pathname.lstrip("./") / basename
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(content)
        else:
            result = f"./media/{basename}"

            target_file = self._output_dir / "media" / basename
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(content)

        self._filemap[pathname] = result
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

            if self._replaced_file_ext:
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
