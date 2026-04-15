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

"""Shared MathJax detection helpers for HTML export paths.

The HTML export implementations need the same high-level decision:
determine which MathJax major version the rendered report page expects.
This module keeps that decision logic in one place while leaving the
filesystem- and HTTP-specific fallback probes in their respective
exporters.
"""

from __future__ import annotations

from html.parser import HTMLParser
import urllib.parse

from .html_export_constants import MATHJAX_VERSION_SENTINELS

# Map the documented top-level MathJax loader filenames to the major version
# they represent in ADR.  Keeping the mapping derived from the shared
# sentinel list avoids duplicating version-specific filenames in logic code.
_MATHJAX_SCRIPT_BASENAME_TO_VERSION = {
    sentinel.lower(): version for version, sentinel in MATHJAX_VERSION_SENTINELS
}


def _match_mathjax_script_src(script_src: str) -> str | None:
    """Return the MathJax major version implied by one script URL.

    Parameters
    ----------
    script_src : str
        The raw ``src`` attribute value from a ``<script>`` tag.

    Returns
    -------
    str | None
        ``"2"`` or ``"4"`` when the script path matches a known top-level
        MathJax loader, otherwise ``None``.
    """
    # Parse the URL instead of splitting on "?" manually so relative paths,
    # absolute URLs, and cache-busted URLs are all normalized the same way.
    script_path = urllib.parse.urlsplit(script_src).path
    script_basename = script_path.rsplit("/", 1)[-1].lower()
    return _MATHJAX_SCRIPT_BASENAME_TO_VERSION.get(script_basename)


class _MathJaxScriptDetector(HTMLParser):
    """Collect MathJax major versions referenced by explicit script tags.

    The rendered report HTML is the best source of truth for offline export:
    it tells the exporter which MathJax loader the page actually references.
    Restricting the scan to ``<script src=...>`` tags avoids false positives
    from comments, inline JavaScript strings, or unrelated text content.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.versions: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record the version for any MathJax loader referenced by ``src``."""
        if tag != "script":
            return

        for attr_name, attr_value in attrs:
            if attr_name != "src" or attr_value is None:
                continue

            version = _match_mathjax_script_src(attr_value)
            if version is not None:
                self.versions.add(version)
            return


def detect_mathjax_version_from_html(html: str) -> str:
    """Detect the MathJax major version referenced by rendered HTML.

    Parameters
    ----------
    html : str
        Rendered report HTML or HTML fragment.

    Returns
    -------
    str
        ``"2"`` when the page references ``MathJax.js``, ``"4"`` when it
        references ``tex-mml-chtml.js``, or ``"unknown"`` when the page does
        not reference a supported MathJax loader or references conflicting
        major versions.
    """
    detector = _MathJaxScriptDetector()
    detector.feed(html)
    detector.close()

    # ADR is expected to emit exactly one MathJax major version.  If the page
    # somehow references multiple major versions, treating that as unknown is
    # safer than exporting the wrong asset tree.
    if len(detector.versions) == 1:
        return next(iter(detector.versions))
    return "unknown"
