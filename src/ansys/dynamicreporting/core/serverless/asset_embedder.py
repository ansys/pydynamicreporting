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

"""Embed ADR-managed assets in rendered serverless HTML."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
import re
import urllib.parse

from ..exceptions import ADRException, ImproperlyConfiguredError
from ..utils.html_export_constants import MATHJAX_VERSION_SENTINELS
from ..utils.html_export_mathjax import detect_mathjax_version_from_html


_MIME_TYPES: dict[str, str] = {
    ".aac": "audio/aac",
    ".avi": "video/x-msvideo",
    ".css": "text/css",
    ".cur": "image/x-icon",
    ".eot": "application/vnd.ms-fontobject",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript",
    ".json": "application/json",
    ".m4a": "audio/mp4",
    ".mjs": "text/javascript",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".oga": "audio/ogg",
    ".ogg": "audio/ogg",
    ".ogv": "video/ogg",
    ".otf": "font/otf",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ttf": "font/ttf",
    ".wasm": "application/wasm",
    ".wav": "audio/wav",
    ".webm": "video/webm",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}

_CSS_IMPORT_QUOTED_PATTERN: re.Pattern[str] = re.compile(
    r"@import\s+(?:url\(\s*)?(?P<quote>['\"])(?P<url>.*?)(?P=quote)"
    r"\s*\)?\s*(?P<media>[^;]*);",
    re.IGNORECASE | re.DOTALL,
)
_CSS_IMPORT_URL_PATTERN: re.Pattern[str] = re.compile(
    r"@import\s+url\(\s*(?P<url>[^)\s]+)\s*\)\s*(?P<media>[^;]*);",
    re.IGNORECASE | re.DOTALL,
)
_CSS_URL_PATTERN: re.Pattern[str] = re.compile(
    r"url\(\s*(?P<quote>['\"]?)(?P<url>.*?)(?P=quote)\s*\)",
    re.IGNORECASE | re.DOTALL,
)
_LINK_TAG_PATTERN: re.Pattern[str] = re.compile(r"<link\b[^>]*>", re.IGNORECASE | re.DOTALL)
_SCRIPT_TAG_PATTERN: re.Pattern[str] = re.compile(
    r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)
_STYLE_TAG_PATTERN: re.Pattern[str] = re.compile(
    r"<style\b(?P<attrs>[^>]*)>(?P<body>.*?)</style\s*>",
    re.IGNORECASE | re.DOTALL,
)
_ASSET_TAG_PATTERN: re.Pattern[str] = re.compile(
    r"<(?P<name>a|audio|embed|img|input|link|object|source|track|video|"
    r"ansys-nexus-viewer)\b[^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_STYLE_ATTRIBUTE_TAG_PATTERN: re.Pattern[str] = re.compile(
    r"<(?!/|!|\?)(?!script\b|style\b)(?P<name>[a-z][\w:-]*)\b"
    r"(?=(?:[^>\"']|\"[^\"]*\"|'[^']*')*\sstyle\s*=)"
    r"(?:[^>\"']|\"[^\"]*\"|'[^']*')*>",
    re.IGNORECASE | re.DOTALL,
)
_QUOTED_REFERENCE_PATTERN: re.Pattern[str] = re.compile(
    r"(?P<quote>['\"])(?P<url>.*?)(?P=quote)",
    re.DOTALL,
)
_ELEMENT_SOURCE_PATTERN: re.Pattern[str] = re.compile(
    r"(?P<prefix>\be\.src\s*=\s*)(?P<quote>['\"])(?P<url>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_DATA_URI_PATTERN: re.Pattern[str] = re.compile(
    r"data:[^\s'\"<>`)]*",
    re.IGNORECASE,
)


class ServerlessAssetEmbedder:
    """Embed the ADR-owned dependency closure of one rendered report.

    The embedder reads only from the configured ADR installation and media
    roots. It does not write files, download remote resources, or retain state
    beyond one :meth:`embed` call.

    Parameters
    ----------
    html_content : str
        Rendered report HTML or HTML fragment.
    static_dir : pathlib.Path
        Product static root from the ADR installation.
    media_dir : pathlib.Path
        ADR-managed report media root.
    static_url : str
        URL prefix that identifies ADR static assets.
    media_url : str
        URL prefix that identifies ADR media assets.
    ansys_version : str
        ADR product version used in versioned static URLs.
    logger : logging.Logger
        Logger used for pipeline diagnostics.
    """

    _html_content: str
    _static_dir: Path
    _media_dir: Path
    _static_url: str
    _media_url: str
    _ansys_version: str
    _logger: logging.Logger
    _asset_cache: dict[Path, bytes]
    _encoded_cache: dict[Path, str]
    _data_uri_cache: dict[tuple[Path, str], str]
    _css_cache: dict[Path, str]
    _source_bytes: int
    _encoded_bytes: int
    _mathjax_version: str | None

    def __init__(
        self,
        html_content: str,
        static_dir: Path,
        media_dir: Path,
        static_url: str,
        media_url: str,
        ansys_version: str,
        logger: logging.Logger,
    ) -> None:
        self._html_content = html_content
        self._static_dir = Path(static_dir).resolve()
        self._media_dir = Path(media_dir).resolve()
        self._static_url = static_url
        self._media_url = media_url
        self._ansys_version = ansys_version
        self._logger = logger
        self._asset_cache = {}
        self._encoded_cache = {}
        self._data_uri_cache = {}
        self._css_cache = {}
        self._source_bytes = 0
        self._encoded_bytes = 0
        self._mathjax_version = None

    def embed(self) -> str:
        """Return the rendered HTML with ADR-managed dependencies embedded."""
        self._logger.info("Embedding ADR assets in rendered serverless HTML.")
        try:
            self._reset_state()
            self._validate_roots()
            self._mathjax_version = self._detect_mathjax_version()
            self._logger.debug("Detected MathJax version '%s'.", self._mathjax_version)

            html = self._html_content
            html = self._inline_stylesheet_links(html)
            html = self._inline_style_elements(html)
            html = self._inline_style_attributes(html)
            html = self._inline_asset_tags(html)
            html = self._inline_script_elements(html)
            self._assert_no_unresolved_assets(html)

            self._logger.info(
                "Embedded %d ADR assets (%d source bytes, %d Base64 bytes).",
                len(self._asset_cache),
                self._source_bytes,
                self._encoded_bytes,
            )
            return html
        except ADRException:
            self._logger.debug("ADR asset embedding failed.", exc_info=True)
            raise
        except Exception as error:
            self._logger.debug("ADR asset embedding failed.", exc_info=True)
            raise ADRException("Report asset embedding failed.") from error

    def _reset_state(self) -> None:
        """Reset all state owned by a single embedding pass."""
        self._asset_cache.clear()
        self._encoded_cache.clear()
        self._data_uri_cache.clear()
        self._css_cache.clear()
        self._source_bytes = 0
        self._encoded_bytes = 0
        self._mathjax_version = None

    def _validate_roots(self) -> None:
        """Validate roots needed by the in-memory embedding path."""
        if not self._static_dir.is_dir():
            raise ImproperlyConfiguredError(
                f"The static files directory '{self._static_dir}' does not exist in the "
                "installation. Please check your Ansys installation and version."
            )
        if not self._media_dir.is_dir():
            raise ImproperlyConfiguredError(
                f"The media files directory '{self._media_dir}' does not exist."
            )

    def _detect_mathjax_version(self) -> str:
        """Detect the report's MathJax major, then probe installed sentinels."""
        # MathJax 2.x can select its configuration from the loader's `?config=` query.
        # Inlining drops that query, so product-backed verification remains required for this edge.
        html_version = detect_mathjax_version_from_html(self._html_content)
        if html_version != "unknown":
            return html_version

        mathjax_root = self._static_dir / "website/scripts/mathjax"
        for version, sentinel in MATHJAX_VERSION_SENTINELS:
            if (mathjax_root / sentinel).is_file():
                return version
        return "unknown"

    def _owned_path(self, reference: str) -> tuple[Path, Path] | None:
        """Resolve an ADR-owned URL to ``(path, allowed_root)``.

        For example, ``/static/website/site.css`` resolves below ``static_dir``;
        ``https://example.com/site.css`` is not ADR-owned and returns ``None``.
        Query strings and fragments are excluded from filesystem lookup.
        """
        raw_reference = reference.strip()
        if not raw_reference or raw_reference.startswith(("#", "//")):
            return None

        parsed = urllib.parse.urlsplit(raw_reference)
        if parsed.scheme or parsed.netloc:
            return None

        url_path = urllib.parse.unquote(parsed.path).replace("\\", "/")
        version_prefix = f"/ansys{self._ansys_version}/"

        if url_path.startswith(self._static_url):
            relative_path = url_path.removeprefix(self._static_url)
            root = self._static_dir
        elif url_path.startswith(self._media_url):
            relative_path = url_path.removeprefix(self._media_url)
            root = self._media_dir
        elif url_path.startswith(version_prefix):
            relative_path = url_path.lstrip("/")
            root = self._static_dir
        else:
            return None

        resolved_path = self._contained_path(root, root / relative_path, reference)
        self._logger.debug("Resolved ADR asset '%s' to '%s'.", reference, resolved_path)
        return resolved_path, root

    def _relative_path(self, reference: str, base_dir: Path) -> tuple[Path, Path] | None:
        """Resolve a CSS-relative reference under its owning ADR root.

        For example, ``url(../fonts/a.woff2)`` in ``content/site.css`` resolves
        beside the source stylesheet. Remote and existing data URLs stay external.
        """
        owned_path = self._owned_path(reference)
        if owned_path is not None:
            return owned_path

        raw_reference = reference.strip()
        if not raw_reference or raw_reference.startswith(("#", "/", "//")):
            return None
        parsed = urllib.parse.urlsplit(raw_reference)
        if parsed.scheme or parsed.netloc:
            return None

        if base_dir.is_relative_to(self._static_dir):
            root = self._static_dir
        elif base_dir.is_relative_to(self._media_dir):
            root = self._media_dir
        else:
            raise ADRException(f"Asset base directory '{base_dir}' is outside the ADR roots.")

        relative_path = urllib.parse.unquote(parsed.path).replace("\\", "/")
        resolved_path = self._contained_path(root, base_dir / relative_path, reference)
        self._logger.debug("Resolved relative ADR asset '%s' to '%s'.", reference, resolved_path)
        return resolved_path, root

    @staticmethod
    def _contained_path(root: Path, candidate: Path, reference: str) -> Path:
        """Resolve *candidate* and reject traversal or symlink escape from *root*."""
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve()
        if not resolved_candidate.is_relative_to(resolved_root):
            raise ADRException(f"Unsafe ADR asset reference '{reference}'.")
        return resolved_candidate

    def _read_bytes(self, path: Path, reference: str) -> bytes:
        """Read a required asset once during this render."""
        if path in self._asset_cache:
            self._logger.debug("Reused cached ADR asset '%s'.", path)
            return self._asset_cache[path]
        if not path.is_file():
            raise ADRException(f"Required ADR asset '{reference}' was not found.")
        try:
            content = path.read_bytes()
        except OSError as error:
            raise ADRException(f"Required ADR asset '{reference}' could not be read.") from error
        self._asset_cache[path] = content
        self._source_bytes += len(content)
        return content

    def _read_text(self, path: Path, reference: str) -> str:
        """Decode a required CSS or JavaScript asset as UTF-8 text."""
        try:
            return self._read_bytes(path, reference).decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ADRException(
                f"Required ADR text asset '{reference}' is not valid UTF-8."
            ) from error

    @staticmethod
    def _mime_type(path: Path) -> str:
        """Return a deterministic MIME type with a standard-library fallback."""
        explicit_type = _MIME_TYPES.get(path.suffix.lower())
        if explicit_type is not None:
            return explicit_type
        guessed_type, _ = mimetypes.guess_type(path.name)
        return guessed_type or "application/octet-stream"

    def _data_uri(
        self,
        path: Path,
        reference: str,
        *,
        mime_type: str | None = None,
    ) -> str:
        """Return a MIME-correct data URI while encoding each source only once."""
        selected_type = mime_type or self._mime_type(path)
        cache_key = (path, selected_type)
        if cache_key in self._data_uri_cache:
            self._logger.debug("Reused encoded ADR asset '%s'.", path)
            return self._data_uri_cache[cache_key]
        if path not in self._encoded_cache:
            encoded = base64.b64encode(self._read_bytes(path, reference)).decode("ascii")
            self._encoded_cache[path] = encoded
            self._encoded_bytes += len(encoded)
        data_uri = f"data:{selected_type};base64,{self._encoded_cache[path]}"
        self._data_uri_cache[cache_key] = data_uri
        return data_uri

    def _embed_stylesheet(
        self,
        stylesheet_path: Path,
        reference: str,
        import_stack: tuple[Path, ...] = (),
    ) -> str:
        """Return CSS with imports and asset URLs embedded recursively.

        ``@import "theme.css"`` becomes the imported stylesheet text. A
        relative reference such as ``url(../fonts/a.woff2)`` becomes
        ``url(data:font/woff2;base64,...)`` using the source stylesheet's
        directory as its base.
        """
        if stylesheet_path in import_stack:
            cycle = " -> ".join(str(path) for path in (*import_stack, stylesheet_path))
            raise ADRException(f"Cyclic ADR stylesheet import detected: {cycle}")
        if stylesheet_path in self._css_cache:
            self._logger.debug("Reused transformed ADR stylesheet '%s'.", stylesheet_path)
            return self._css_cache[stylesheet_path]

        css_text = self._read_text(stylesheet_path, reference)
        next_stack = (*import_stack, stylesheet_path)
        css_text = self._replace_css_imports(css_text, stylesheet_path.parent, next_stack)
        css_text = self._replace_css_urls(css_text, stylesheet_path.parent)
        self._css_cache[stylesheet_path] = css_text
        return css_text

    def _replace_css_imports(
        self,
        css_text: str,
        base_dir: Path,
        import_stack: tuple[Path, ...],
    ) -> str:
        """Inline quoted and ``url(...)`` CSS imports.

        For example, ``@import "print.css" print;`` becomes
        ``@media print { ...contents of print.css... }``. Remote imports stay
        unchanged.
        """

        def replace_import(match: re.Match[str]) -> str:
            reference = match.group("url").strip()
            resolved = self._relative_path(reference, base_dir)
            if resolved is None:
                return match.group(0)
            imported_path, _ = resolved
            imported_css = self._embed_stylesheet(imported_path, reference, import_stack)
            media = match.group("media").strip()
            if media:
                return f"@media {media} {{\n{imported_css}\n}}"
            return imported_css

        css_text = _CSS_IMPORT_QUOTED_PATTERN.sub(replace_import, css_text)
        return _CSS_IMPORT_URL_PATTERN.sub(replace_import, css_text)

    def _replace_css_urls(self, css_text: str, base_dir: Path) -> str:
        """Replace ADR-owned and stylesheet-relative CSS URLs with data URIs."""

        def replace_url(match: re.Match[str]) -> str:
            reference = match.group("url").strip()
            resolved = self._relative_path(reference, base_dir)
            if resolved is None:
                return match.group(0)
            asset_path, _ = resolved
            return f"url({self._data_uri(asset_path, reference)})"

        return _CSS_URL_PATTERN.sub(replace_url, css_text)

    @staticmethod
    def _attribute_pattern(attribute_name: str) -> re.Pattern[str]:
        """Return a pattern for one quoted or unquoted HTML attribute."""
        return re.compile(
            rf"(?P<leading>\s+){re.escape(attribute_name)}\s*=\s*"
            rf"(?:(?P<quote>['\"])(?P<quoted>.*?)(?P=quote)|(?P<plain>[^\s>]+))",
            re.IGNORECASE | re.DOTALL,
        )

    @classmethod
    def _attribute_value(cls, tag: str, attribute_name: str) -> str | None:
        """Return an attribute value without changing the source tag."""
        match = cls._attribute_pattern(attribute_name).search(tag)
        if match is None:
            return None
        return match.group("quoted") if match.group("quote") else match.group("plain")

    @classmethod
    def _remove_attribute(cls, tag: str, attribute_name: str) -> str:
        """Remove one attribute while preserving all surrounding tag text."""
        return cls._attribute_pattern(attribute_name).sub("", tag, count=1)

    @classmethod
    def _replace_attribute(cls, tag: str, attribute_name: str, value: str) -> str:
        """Replace one attribute value while preserving its original quote style."""

        def replace_value(match: re.Match[str]) -> str:
            quote = match.group("quote") or '"'
            return f"{match.group('leading')}{attribute_name}={quote}{value}{quote}"

        return cls._attribute_pattern(attribute_name).sub(replace_value, tag, count=1)

    @staticmethod
    def _escape_element_text(text: str, element_name: str) -> str:
        r"""Prevent embedded text from terminating its containing element.

        For example, ``value = "</script>"`` becomes
        ``value = "<\/script>"``. The equivalent replacement is used for
        ``</style>``. Escaping the slash preserves JavaScript and CSS string
        meaning while preventing the HTML parser from recognizing an end tag.
        """
        closing_tag = re.compile(rf"</{re.escape(element_name)}", re.IGNORECASE)
        return closing_tag.sub(lambda match: f"<\\/{match.group(0)[2:]}", text)

    def _inline_stylesheet_links(self, html: str) -> str:
        """Replace ADR stylesheet links with ordered inline style elements.

        For example, ``<link rel="stylesheet" href="/static/site.css">``
        becomes ``<style>...transformed CSS...</style>``. Non-ADR links stay
        unchanged.
        """

        def replace_link(match: re.Match[str]) -> str:
            tag = match.group(0)
            relation = self._attribute_value(tag, "rel")
            reference = self._attribute_value(tag, "href")
            if (
                relation is None
                or "stylesheet" not in relation.lower().split()
                or reference is None
            ):
                return tag
            resolved = self._owned_path(reference)
            if resolved is None:
                return tag
            stylesheet_path, _ = resolved
            css_text = self._embed_stylesheet(stylesheet_path, reference)
            style_attrs = self._remove_attribute(tag, "href")
            style_attrs = self._remove_attribute(style_attrs, "rel")
            style_attrs = re.sub(r"^<link\b", "<style", style_attrs, flags=re.IGNORECASE)
            style_attrs = re.sub(r"\s*/?>$", ">", style_attrs)
            return f"{style_attrs}{self._escape_element_text(css_text, 'style')}</style>"

        return _LINK_TAG_PATTERN.sub(replace_link, html)

    def _inline_style_elements(self, html: str) -> str:
        """Embed ADR URLs already present inside inline style elements."""

        def replace_style(match: re.Match[str]) -> str:
            css_text = self._replace_owned_css_urls(match.group("body"))
            return (
                f"<style{match.group('attrs')}>"
                f"{self._escape_element_text(css_text, 'style')}</style>"
            )

        return _STYLE_TAG_PATTERN.sub(replace_style, html)

    def _replace_owned_css_urls(self, css_text: str) -> str:
        """Replace only absolute ADR URLs in CSS without assuming a source file."""

        def replace_url(match: re.Match[str]) -> str:
            reference = match.group("url").strip()
            resolved = self._owned_path(reference)
            if resolved is None:
                return match.group(0)
            asset_path, _ = resolved
            return f"url({self._data_uri(asset_path, reference)})"

        return _CSS_URL_PATTERN.sub(replace_url, css_text)

    def _inline_style_attributes(self, html: str) -> str:
        """Embed absolute ADR URLs used in inline ``style`` attributes.

        For example, ``style="background:url('/static/a.png')"`` becomes a
        style attribute containing ``url(data:image/png;base64,...)``. Relative
        URLs stay unchanged because an HTML attribute has no stylesheet path
        against which to resolve them. The scan is limited to tags that contain
        a style attribute, excludes script and style elements, and preserves a
        literal ``>`` inside a quoted attribute value.
        """

        def replace_tag(match: re.Match[str]) -> str:
            tag = match.group(0)
            style = self._attribute_value(tag, "style")
            if style is None:
                return tag
            transformed = self._replace_owned_css_urls(style)
            if transformed == style:
                return tag
            return self._replace_attribute(tag, "style", transformed)

        return _STYLE_ATTRIBUTE_TAG_PATTERN.sub(replace_tag, html)

    @staticmethod
    def _insert_attribute(tag: str, attribute_name: str, value: str) -> str:
        """Insert one attribute immediately after an opening tag name."""
        name_match = re.match(r"<[^\s>]+", tag)
        if name_match is None:
            return tag
        insertion = f' {attribute_name}="{value}"'
        return f"{tag[: name_match.end()]}{insertion}{tag[name_match.end() :]}"

    def _inline_asset_tags(self, html: str) -> str:
        """Replace ADR-owned HTML asset attributes with data URIs.

        For example, ``<img src="/media/image.png">`` becomes an image whose
        ``src`` is ``data:image/png;base64,...``. Viewer geometry and download
        links use ``application/octet-stream`` to retain exporter compatibility.
        """
        attributes_by_tag: dict[str, tuple[str, ...]] = {
            "a": ("href",),
            "ansys-nexus-viewer": ("proxy_img", "src"),
            "audio": ("src",),
            "embed": ("src",),
            "img": ("src",),
            "input": ("src",),
            "link": ("href",),
            "object": ("data",),
            "source": ("src",),
            "track": ("src",),
            "video": ("src", "poster"),
        }

        def replace_tag(match: re.Match[str]) -> str:
            tag_name = match.group("name").lower()
            tag = match.group(0)
            viewer_source: str | None = None
            for attribute_name in attributes_by_tag[tag_name]:
                reference = self._attribute_value(tag, attribute_name)
                if reference is None:
                    continue
                resolved = self._owned_path(reference)
                if resolved is None:
                    continue
                asset_path, _ = resolved
                force_binary = (tag_name == "a" and attribute_name == "href") or (
                    tag_name == "ansys-nexus-viewer" and attribute_name == "src"
                )
                mime_type = "application/octet-stream" if force_binary else None
                data_uri = self._data_uri(asset_path, reference, mime_type=mime_type)
                tag = self._replace_attribute(tag, attribute_name, data_uri)
                if tag_name == "ansys-nexus-viewer" and attribute_name == "src":
                    viewer_source = reference

            if (
                viewer_source is not None
                and self._attribute_value(tag, "src_ext") is None
                and (suffix := Path(urllib.parse.urlsplit(viewer_source).path).suffix)
            ):
                tag = self._insert_attribute(tag, "src_ext", suffix.lstrip(".").upper())
            return tag

        return _ASSET_TAG_PATTERN.sub(replace_tag, html)

    def _inline_script_elements(self, html: str) -> str:
        """Inline ADR script sources and transform demonstrated script references.

        For example, ``<script defer src="/static/app.js"></script>`` becomes
        ``<script defer>...transformed app.js...</script>`` in the same position.
        Remote script elements stay unchanged.
        """

        def replace_script(match: re.Match[str]) -> str:
            full_tag = match.group(0)
            attrs = match.group("attrs")
            reference = self._attribute_value(f"<script{attrs}>", "src")
            if reference is None:
                body = self._replace_known_script_references(
                    match.group("body"),
                    None,
                )
                return f"<script{attrs}>{body}</script>"

            resolved = self._owned_path(reference)
            if resolved is None:
                return full_tag
            script_path, _ = resolved
            script_text = self._read_text(script_path, reference)
            script_text = self._replace_known_script_references(script_text, script_path.parent)
            open_tag = self._remove_attribute(f"<script{attrs}>", "src")
            return f"{open_tag}{self._escape_element_text(script_text, 'script')}</script>"

        return _SCRIPT_TAG_PATTERN.sub(replace_script, html)

    def _known_reference_path(
        self,
        reference: str,
        base_dir: Path | None,
    ) -> tuple[Path, Path] | None:
        """Resolve an ADR URL or file-like relative value in a known asset slot."""
        resolved = self._owned_path(reference)
        if resolved is not None:
            return resolved

        parsed = urllib.parse.urlsplit(reference.strip())
        if (
            not parsed.path
            or not Path(parsed.path).suffix
            or parsed.path.startswith("/")
            or parsed.scheme
            or parsed.netloc
        ):
            return None
        if base_dir is None:
            return None
        return self._relative_path(reference, base_dir)

    def _replace_quoted_references(
        self,
        text: str,
        base_dir: Path | None,
        *,
        mime_type: str | None,
    ) -> str:
        """Embed file references in one exporter-demonstrated script block."""

        def replace_reference(match: re.Match[str]) -> str:
            reference = match.group("url")
            resolved = self._known_reference_path(reference, base_dir)
            if resolved is None:
                return match.group(0)
            asset_path, _ = resolved
            data_uri = self._data_uri(asset_path, reference, mime_type=mime_type)
            quote = match.group("quote")
            return f"{quote}{data_uri}{quote}"

        return _QUOTED_REFERENCE_PATTERN.sub(replace_reference, text)

    def _replace_script_blocks(
        self,
        script_text: str,
        prefix: str,
        suffix: str,
        base_dir: Path | None,
    ) -> str:
        """Embed references inside repeated, bounded ADR script constructs."""
        current = 0
        while True:
            start = script_text.find(prefix, current)
            if start < 0:
                return script_text
            end = script_text.find(suffix, start + len(prefix))
            if end < 0:
                return script_text
            end += len(suffix)
            block = script_text[start:end]
            transformed = self._replace_quoted_references(
                block,
                base_dir,
                mime_type="application/octet-stream",
            )
            script_text = f"{script_text[:start]}{transformed}{script_text[end:]}"
            current = start + len(transformed)

    def _replace_known_script_references(
        self,
        script_text: str,
        base_dir: Path | None,
    ) -> str:
        """Port the existing exporter's bounded scene and viewer rewrites.

        ``await fetch('/media/scene.bin');`` and
        ``load_binary_block('/media/mesh.bin', mesh);`` receive octet-stream
        data URIs. The same rule is limited to ``GLTFViewer(...)`` calls and
        ``.key_images = {...}.update();`` blocks; arbitrary JavaScript strings
        are not inspected.
        """
        for prefix, suffix in (
            ("load_binary_block(", ");"),
            (".key_images = {", ".update();"),
            ("GLTFViewer", ");"),
            ("await fetch(", ");"),
        ):
            script_text = self._replace_script_blocks(
                script_text,
                prefix,
                suffix,
                base_dir,
            )

        def replace_element_source(match: re.Match[str]) -> str:
            reference = match.group("url")
            resolved = self._known_reference_path(reference, base_dir)
            if resolved is None:
                return match.group(0)
            asset_path, _ = resolved
            data_uri = self._data_uri(asset_path, reference)
            quote = match.group("quote")
            return f"{match.group('prefix')}{quote}{data_uri}{quote}"

        return _ELEMENT_SOURCE_PATTERN.sub(replace_element_source, script_text)

    def _assert_no_unresolved_assets(self, html: str) -> None:
        """Fail if any ADR-owned reference remains after the embedding passes."""
        scan_text = _DATA_URI_PATTERN.sub("data:", html)
        prefixes = sorted(
            {self._static_url, self._media_url, f"/ansys{self._ansys_version}/"},
            key=len,
            reverse=True,
        )
        owned_prefix = "|".join(re.escape(prefix) for prefix in prefixes if prefix)
        if not owned_prefix:
            return
        candidate_pattern = re.compile(
            rf"(?P<remote>(?:https?:)?//[^\s'\"<>`]+)|"
            rf"(?P<owned>(?:{owned_prefix})[^\s'\"<>`),;\]\}}]*)",
            re.IGNORECASE,
        )
        for match in candidate_pattern.finditer(scan_text):
            candidate = match.group("owned")
            if candidate is None:
                continue
            if self._owned_path(candidate) is not None:
                raise ADRException(
                    f"Rendered report contains unresolved ADR asset reference '{candidate}'."
                )
