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

"""Browser-fidelity HTML-to-PDF rendering for serverless ADR exports.

Architecture
------------
This renderer intentionally relies on two linked Chromium layout phases instead of
treating PDF export as a screenshot of already-painted viewport pixels:

    offline file:// HTML export
              |
              v
    +-----------------------------------------------+
    | Phase A: live browser / continuous-media pass |
    | - fixed viewport for deterministic JS layout  |
    | - execute ADR, Plotly, MathJax, viewers       |
    | - wait for readiness signals                  |
    | - inject capture CSS                          |
    | - measure content width from the live page    |
    +-----------------------------------------------+
              |
              v
    +-----------------------------------------------+
    | Phase B: paged PDF generation pass            |
    | - call page.pdf(width=measured, ...)          |
    | - Chromium generates paged output             |
    | - requested paper width defines page area     |
    | - auto-width nodes/divs can use that width    |
    | - wide legends/content avoid right clipping   |
    +-----------------------------------------------+

- Playwright documents ``page.pdf()`` as generating a PDF of the page, with print CSS
  media by default, unless ``page.emulate_media(media="screen")`` is used first (as in our case).
- MDN distinguishes the viewport used for continuous media from the page area used for
  paged media, and notes that the initial containing block changes accordingly.

That distinction matters for browser-PDF exports. Phase A stabilizes responsive
browser-rendered content such as Plotly against a fixed viewport so width measurements
are deterministic. Phase B then feeds the measured width back into ``page.pdf()`` so
the final paged layout has enough horizontal space to preserve content that would
otherwise overflow or be clipped at the right edge.
"""

import json
import re
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from ..adr_utils import get_logger
from ..exceptions import ADRException


class PlaywrightPDFRenderer:
    """Render an exported ADR HTML directory to PDF via headless Chromium.

    Parameters
    ----------
    html_dir : Path or str
        Directory containing the exported offline HTML report and its assets.
    filename : str, default: "index.html"
        HTML entry-point filename inside ``html_dir``.
    landscape : bool, default: False
        Whether to render the PDF in landscape orientation.
    margins : dict[str, str], optional
        Page margins with ``top``, ``right``, ``bottom``, and ``left`` Playwright PDF lengths.
        If omitted, 10 mm margins are used on every side.
    render_timeout : float, default: 30.0
        Maximum time, in seconds, to wait for browser readiness signals.
    logger : Any, optional
        Logger used for renderer lifecycle messages.
    """

    # 10mm on all sides. This is the default page margin if the caller doesn't specify custom margins.
    _DEFAULT_MARGINS: dict[str, str] = {
        "top": "10mm",
        "right": "10mm",
        "bottom": "10mm",
        "left": "10mm",
    }
    #  Playwright's page.pdf() accepts lengths in px, in, cm, and mm.
    # Map those units to CSS pixels for internal computations as per
    # the CSS specification standard.
    _PDF_UNIT_TO_PX: dict[str, float] = {
        "": 1.0,
        "px": 1.0,
        "in": 96.0,
        "cm": 96.0 / 2.54,
        "mm": 96.0 / 25.4,
    }
    # the width of an A4 page
    _DEFAULT_PAGE_WIDTH: str = "210mm"
    # the height of an A4 page
    _DEFAULT_PAGE_HEIGHT: str = "297mm"
    # the default virtual browser viewport width and height
    _DEFAULT_BROWSER_VIEWPORT_WIDTH: int = 1600
    _DEFAULT_BROWSER_VIEWPORT_HEIGHT: int = 900
    # Maximum time to wait for all JavaScript to finish rendering, in seconds.
    _DEFAULT_RENDER_TIMEOUT: float = 30.0
    # Network requests using these schemes are blocked to keep rendering offline.
    _BLOCKED_REQUEST_SCHEMES: set[str] = {"http", "https"}
    _BLOCKED_WEBSOCKET_SCHEMES: set[str] = {"ws", "wss"}

    def __init__(
        self,
        html_dir: Path | str,
        filename: str = "index.html",
        *,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = _DEFAULT_RENDER_TIMEOUT,
        logger: Any = None,
    ) -> None:
        """Initialize the renderer with a self-contained HTML export directory."""
        self._html_dir = Path(html_dir).expanduser().resolve()
        self._filename = filename
        self._landscape = landscape
        self._margins = self._validate_margins(margins)
        self._render_timeout = self._validate_render_timeout(render_timeout)
        self._logger = logger or get_logger()

    def render_pdf(self) -> bytes:
        """Render the exported HTML report to PDF bytes.

        Returns
        -------
        bytes
            PDF document bytes produced by headless Chromium.

        Raises
        ------
        ADRException
            If the browser render/export flow fails.
        """
        entrypoint_path = self._resolve_entrypoint_path()

        try:
            with sync_playwright() as playwright:
                self._logger.info("Launching headless Chromium for browser PDF export.")
                browser = playwright.chromium.launch(headless=True)

                try:
                    # Fix the responsive layout width up front so Plotly and other browser-rendered
                    # items lay themselves out deterministically before the PDF width is computed.
                    context = browser.new_context(
                        viewport={
                            "width": self._DEFAULT_BROWSER_VIEWPORT_WIDTH,
                            "height": self._DEFAULT_BROWSER_VIEWPORT_HEIGHT,
                        },
                        service_workers="block",
                        accept_downloads=False,
                        offline=True,
                    )
                    try:
                        self._block_external_requests(context)
                        page = context.new_page()
                        file_url = entrypoint_path.as_uri()

                        # Load the exported offline report exactly as Chromium would see it from disk.
                        self._logger.info(
                            f"Loading exported HTML for browser PDF export: {file_url}"
                        )
                        # Keep navigation under the caller-configured browser render budget.
                        # Playwright documents ``page.goto(timeout=...)`` in milliseconds, while
                        # ADR exposes ``render_timeout`` in seconds for the whole render workflow.
                        # Clamp to at least 1000 ms because Playwright treats ``timeout=0`` as
                        # disabling the timeout, which would invert a small positive ADR budget.
                        navigation_timeout_ms = max(int(self._render_timeout * 1000), 1000)
                        page.goto(
                            file_url,
                            wait_until="load",
                            timeout=navigation_timeout_ms,
                        )

                        # Force screen media so the PDF matches the browser view instead of print CSS.
                        page.emulate_media(media="screen")
                        self._apply_pdf_capture_styles(page)
                        self._wait_for_render_ready(page)
                        pdf_width = self._compute_pdf_width(page)
                        # Keep the fallback page size internally consistent. Playwright defaults
                        # unspecified PDF dimensions to Letter, so an explicit A4 width prevents a
                        # mixed Letter-width/A4-height page when no content width can be measured.
                        pdf_page_width = (
                            pdf_width if pdf_width is not None else self._DEFAULT_PAGE_WIDTH
                        )
                        pdf_options = {
                            # Keep page height explicit so pagination remains under ADR's control
                            # instead of depending entirely on Playwright's default page format.
                            "width": pdf_page_width,
                            "height": self._DEFAULT_PAGE_HEIGHT,
                            "landscape": self._landscape,
                            "margin": self._margins,
                            "print_background": True,
                        }

                        # Playwright describes page.pdf() as generating paged output, not a bitmap
                        # snapshot of the already-painted viewport. MDN's paged-media model also
                        # distinguishes the continuous-media viewport from the paged page area.
                        # Passing the measured width here therefore gives the PDF generation pass a
                        # wider page area even though the live browser pass already ran. Elements
                        # such as #report_root that remain auto-width can then lay out against that
                        # wider paged space without us assigning them an explicit width in the DOM.
                        pdf_bytes = page.pdf(**pdf_options)
                        self._logger.info(
                            f"Browser PDF generated successfully ({len(pdf_bytes)} bytes)."
                        )
                        return pdf_bytes
                    finally:
                        context.close()
                finally:
                    browser.close()
        except ADRException:
            raise
        except Exception as exc:
            raise ADRException(f"Browser PDF rendering failed: {exc}") from exc

    def _apply_pdf_capture_styles(self, page: Any) -> None:
        """Inject PDF-only overrides that keep browser-rendered content fully visible on pages."""
        # Chromium paginates based on the outer block formatting context. If a page-break rule is
        # applied too high in the ADR layout tree, an entire panel becomes unbreakable and content
        # can spill past the page boundary. Keep the override focused on the actual browser-rendered
        # items so plots stay intact while their parent sections can still paginate normally.
        #
        # The renderer forces ``screen`` media before calling ``page.pdf()`` so the exported PDF
        # matches the on-screen ADR layout. These capture overrides therefore must be unconditional
        # CSS rules rather than ``@media print`` blocks, or Chromium will ignore them while laying
        # out the PDF pages and large browser-rendered items can split across page boundaries.
        #
        # ADR exports section titles and panel headers as sibling blocks before the actual content.
        # Keep those heading blocks with the first chunk of following content so Chromium does not
        # leave a section title at the bottom of one page while pushing the table/plot to the next.
        #
        # TODO: Remove the collapsed-header workaround once ADR stops emitting empty
        # ``<thead style="visibility: collapse;">`` blocks for key/value tables. Chromium's
        # PDF table layout still reserves space for those hidden header groups, which paints a
        # blank top row even though the browser view looks correct.
        page.add_style_tag(
            content="""
                adr-data-item,
                .nexus-plot,
                .nexus-plot > .plot-container,
                .js-plotly-plot,
                .plot-container,
                .svg-container,
                .avz-viewer,
                ansys-nexus-viewer {
                    display: block !important;
                }

                adr-data-item,
                .nexus-plot,
                .nexus-plot > .plot-container,
                .js-plotly-plot,
                .plot-container,
                .svg-container,
                .avz-viewer,
                ansys-nexus-viewer,
                .table-responsive,
                table.table,
                table.tree,
                img.img-fluid,
                video.img-fluid,
                .ansys-nexus-proxy,
                canvas {
                    break-inside: avoid !important;
                    page-break-inside: avoid !important;
                }

                adr-data-item,
                .nexus-plot,
                .plot-container,
                .svg-container,
                .main-svg,
                .table-responsive,
                .avz-viewer,
                ansys-nexus-viewer {
                    overflow: visible !important;
                    max-height: none !important;
                }

                .adr-spinner-loader-container,
                .modebar {
                    display: none !important;
                }

                #report_root {
                    /* Wide browser-PDF pages can make 1px ADR borders look faint when PDF
                       viewers scale the page down. Override ADR's border design tokens for
                       capture instead of selecting individual report items or changing layout. */
                    --adr-border-color: #adb5bd !important;
                    --adr-border-color-translucent: rgba(0, 0, 0, 0.28) !important;
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                }

                h1:has(+ section.adr-container),
                h2:has(+ section.adr-container),
                h3:has(+ section.adr-container),
                h4:has(+ section.adr-container),
                h5:has(+ section.adr-container),
                h6:has(+ section.adr-container),
                header:has(+ section.adr-panel-body) {
                    break-after: avoid !important;
                    page-break-after: avoid !important;
                }

                table.table-fit-head > thead[style*="visibility: collapse"] {
                    display: none !important;
                    visibility: hidden !important;
                    height: 0 !important;
                }
            """,
        )

    def _compute_pdf_width(self, page: Any) -> str | None:
        """Compute an explicit PDF page width when needed to preserve browser content."""
        margin_width_px = self._pdf_length_to_px(self._margins["left"]) + self._pdf_length_to_px(
            self._margins["right"]
        )
        content_width_px = self._measure_content_width_px(page)
        layout_width_px = self._measure_layout_width_px(page)
        if content_width_px <= 0:
            self._logger.info(
                "No visible report width was found; using the default A4 PDF page width."
            )
            return None

        # The PDF page must preserve the same layout canvas that Chromium used while rendering
        # the report. If the PDF content area is narrower than the browser viewport, responsive
        # Plotly legends can still be clipped at the right edge even when the report root itself
        # appears narrower than the viewport.
        # if actual content is wider, use that
        # if the viewport/layout canvas is wider, use that instead
        fitted_content_width_px = max(content_width_px, layout_width_px)
        pdf_width_px = fitted_content_width_px + margin_width_px
        self._logger.info(
            "Computed browser PDF width fit: "
            f"content_width_px={content_width_px:.2f}, "
            f"layout_width_px={layout_width_px:.2f}, "
            f"fitted_width_px={pdf_width_px:.2f}"
        )
        return f"{pdf_width_px:.2f}px"

    def _measure_content_width_px(self, page: Any) -> float:
        """Measure the rightmost visible report content in CSS pixels."""
        # Limit the query to elements that actually paint user-visible content. This keeps the
        # probe close to O(number of rendered report objects) instead of walking the entire page.
        return float(
            page.evaluate(
                """() => {
                    const root = document.getElementById('report_root');
                    if (!root) {
                        return 0;
                    }

                    const rootRect = root.getBoundingClientRect();
                    // Measure a curated set of content-bearing descendants instead of walking the
                    // entire DOM. New ADR content types that can widen the report should update
                    // this list so the width probe keeps seeing the real rendered geometry.
                    const candidateSelectors = [
                        'adr-data-item',
                        '.nexus-plot',
                        '.js-plotly-plot',
                        '.js-plotly-plot .plot-container',
                        '.js-plotly-plot .svg-container',
                        '.js-plotly-plot .main-svg',
                        '.js-plotly-plot .legend',
                        '.js-plotly-plot .legend text',
                        '.table-responsive',
                        'table',
                        'img',
                        'video',
                        'canvas',
                        'ansys-nexus-viewer'
                    ];
                    const candidates = [root];
                    for (const selector of candidateSelectors) {
                        candidates.push(...root.querySelectorAll(selector));
                    }

                    const seen = new Set();
                    // Start with the report root's own visible width and scrollable width. The
                    // scrollWidth fallback helps when child content extends farther right than the
                    // root's immediate visible box.
                    let maxRight = Math.max(rootRect.width, root.scrollWidth);
                    for (const node of candidates) {
                        if (seen.has(node)) {
                            continue;
                        }
                        seen.add(node);

                        const style = window.getComputedStyle(node);
                        if (style.display === 'none' || style.visibility === 'hidden') {
                            continue;
                        }
                        // Skip elements that have no layout box of their own. For example,
                        // display: contents nodes do not produce client rects even though their
                        // children can still render and be measured separately.
                        if (node.getClientRects().length === 0) {
                            continue;
                        }
                        // Measure the node in viewport coordinates, then convert that geometry
                        // into #report_root-relative coordinates for width comparisons.
                        const rect = node.getBoundingClientRect();
                        // offsetLeft is how far this node starts from the left edge of the report
                        // root, which lets scrollWidth-based checks compute a root-relative
                        // rightmost extent.
                        const offsetLeft = rect.left - rootRect.left;
                        // Width is tracked as the farthest rightward extent reached by any
                        // measured node, relative to the left edge of #report_root. The
                        // right edge matters here because browser-rendered content can overflow
                        // past the root's nominal box, so "space remaining to the root edge"
                        // would under-measure the PDF width we actually need.
                        maxRight = Math.max(maxRight, rect.right - rootRect.left);
                        if ('scrollWidth' in node) {
                            // scrollWidth catches horizontally scrollable content that can extend
                            // beyond the node's current client box.
                            maxRight = Math.max(maxRight, offsetLeft + (node.scrollWidth || 0));
                        }
                    }
                    return maxRight;
                }""",
            )
        )

    def _measure_layout_width_px(self, page: Any) -> float:
        """Measure the effective browser layout width in CSS pixels.

        _measure_content_width_px() reports how far visible content extends to the right.
        Some responsive content may lay out relative to the viewport rather than the report
        root; so return the widest of both.
        """
        return float(
            page.evaluate(
                """() => {
                    // Use the widest of the common viewport/document width signals so the PDF
                    // preserves the layout canvas Chromium actually used while rendering.
                    return Math.max(
                        window.innerWidth || 0,  // The viewport width
                        document.documentElement?.clientWidth || 0,  // <html> element width
                        document.body?.clientWidth || 0  // <body> element width
                    );
                }""",
            )
        )

    def _pdf_length_to_px(self, value: str) -> float:
        """Convert a Playwright PDF length to CSS pixels."""
        match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*", value)
        if match is None:
            raise ADRException(f"Unsupported PDF length for browser PDF rendering: {value!r}")

        number = float(match.group(1))
        unit = match.group(2).lower()
        if unit not in self._PDF_UNIT_TO_PX:
            raise ADRException(f"Unsupported PDF length unit for browser PDF rendering: {value!r}")
        return number * self._PDF_UNIT_TO_PX[unit]

    def _resolve_entrypoint_path(self) -> Path:
        """Return the validated HTML entry-point path that Chromium can open."""
        entrypoint_path = (self._html_dir / self._filename).resolve()
        if not entrypoint_path.is_relative_to(self._html_dir):
            raise ADRException(
                "Browser PDF entry-point file must be inside the exported HTML directory."
            )
        if not entrypoint_path.is_file():
            raise ADRException(f"Browser PDF entry-point file does not exist: {entrypoint_path}")
        return entrypoint_path

    def _block_external_requests(self, context: Any) -> None:
        """Keep browser-PDF rendering offline while still allowing local export assets."""

        def route_request(route: Any) -> None:
            request_url = route.request.url
            scheme = urlsplit(request_url).scheme.lower()
            if scheme in self._BLOCKED_REQUEST_SCHEMES:
                route.abort()
                return
            route.continue_()

        def is_external_websocket(url: str) -> bool:
            return urlsplit(url).scheme.lower() in self._BLOCKED_WEBSOCKET_SCHEMES

        def route_websocket(websocket_route: Any) -> None:
            websocket_route.close()

        # ADR's HTML exporter writes a self-contained file:// bundle. Blocking network schemes
        # prevents report HTML from calling back to arbitrary hosts during PDF generation while
        # still allowing file:, data:, and blob: resources that are part of the offline export.
        # Playwright documents WebSocket routing separately from request routing, so handle ws/wss
        # connections through the dedicated route_web_socket API.
        context.route("**/*", route_request)
        context.route_web_socket(is_external_websocket, route_websocket)

    def _validate_margins(self, margins: dict[str, str] | None) -> dict[str, str]:
        """Validate Playwright PDF margins and return a private copy."""
        if margins is None:
            return dict(self._DEFAULT_MARGINS)

        expected_keys = self._DEFAULT_MARGINS.keys()
        margin_keys = margins.keys()
        missing_keys = expected_keys - margin_keys
        extra_keys = margin_keys - expected_keys
        if missing_keys or extra_keys:
            raise ADRException(
                "Browser PDF margins must contain exactly top, right, bottom, and left keys."
            )

        # Validate each margin now so width computation and Playwright rendering use the same
        # documented PDF length unit set.
        validated = {key: str(margins[key]) for key in expected_keys}
        for margin_value in validated.values():
            self._pdf_length_to_px(margin_value)
        return validated

    def _validate_render_timeout(self, render_timeout: float) -> float:
        """Validate the browser readiness timeout."""
        error_message = "Browser PDF render_timeout must be a positive number."
        try:
            timeout = float(render_timeout)
        except (TypeError, ValueError) as exc:
            raise ADRException(error_message) from exc

        if timeout <= 0:
            raise ADRException(error_message)
        return timeout

    def _evaluate_ready_step(
        self,
        page: Any,
        *,
        step_name: str,
        wait_script: str,
        deadline: float,
    ) -> None:
        """Run one readiness step while enforcing the remaining phase budget.

        Playwright's Python ``evaluate`` API waits for returned JavaScript promises but does
        not expose a per-call timeout argument. Each readiness promise therefore enforces the
        remaining browser-render deadline inside the page instead of using fixed sleeps.
        """
        remaining_ms = max(int((deadline - monotonic()) * 1000), 0)
        if remaining_ms <= 0:
            raise ADRException(
                f"Browser PDF rendering failed: {step_name} timed out after {self._render_timeout:.1f}s"
            )

        page.evaluate(
            f"""() => {{
                const timeoutMs = {remaining_ms};
                const stepName = {json.dumps(step_name)};
                const waitForReady = {wait_script};
                return new Promise((resolve, reject) => {{
                    const timeoutId = setTimeout(() => {{
                        reject(new Error(`${{stepName}} timed out after ${{timeoutMs}}ms`));
                    }}, timeoutMs);

                    Promise.resolve()
                        .then(() => waitForReady())
                        .then((value) => {{
                            clearTimeout(timeoutId);
                            resolve(value);
                        }})
                        .catch((error) => {{
                            clearTimeout(timeoutId);
                            reject(error);
                        }});
                }});
            }}""",
        )

    def _wait_for_render_ready(self, page: Any) -> None:
        """Wait for browser rendering signals that indicate the page is ready to print."""
        deadline = monotonic() + self._render_timeout
        self._logger.info("Waiting for browser render readiness signals.")

        # 1. FOUC gate: ADR hides the report with ``body #report_root { opacity: 0 }``
        #    until all custom web-components are registered, which adds ``body.loaded``.
        #    Skip this wait for non-ADR HTML that does not contain ``#report_root``.
        #
        #    FOUC (Flash Of Unstyled Content) is a brief flash of default/uninitialized
        #    styling that can occur before web components or framework styles apply.
        #    ADR intentionally avoids FOUC by keeping the root hidden until components
        #    finish initializing; the renderer waits for the ``body.loaded`` signal so
        #    the PDF captures the final, styled layout rather than an interim state.
        self._evaluate_ready_step(
            page,
            step_name="FOUC gate",
            deadline=deadline,
            wait_script="""() => {
                return new Promise((resolve) => {
                    const root = document.getElementById('report_root');
                    if (!root) { resolve(); return; }
                    if (document.body.classList.contains('loaded')) { resolve(); return; }
                    const observer = new MutationObserver(() => {
                        if (document.body.classList.contains('loaded')) {
                            observer.disconnect();
                            resolve();
                        }
                    });
                    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
                });
            }""",
        )

        # 2. FOUC transition: ``body.loaded #report_root`` triggers a 0.4s opacity
        #    transition. Wait for it to reach opacity 1 before capturing.
        self._evaluate_ready_step(
            page,
            step_name="FOUC transition",
            deadline=deadline,
            wait_script="""() => {
                return new Promise((resolve) => {
                    const root = document.getElementById('report_root');
                    if (!root) { resolve(); return; }
                    const style = getComputedStyle(root);
                    if (style.opacity === '1') { resolve(); return; }
                    root.addEventListener('transitionend', function handler(e) {
                        if (e.propertyName === 'opacity') {
                            root.removeEventListener('transitionend', handler);
                            resolve();
                        }
                    });
                });
            }""",
        )

        # 3. Web fonts (FontAwesome woff2 + MathJax woff2).
        # document.fonts.ready promise resolves when font loading for the document has finished.
        self._evaluate_ready_step(
            page,
            step_name="Web fonts",
            deadline=deadline,
            wait_script="""() => {
                return document.fonts.ready;
            }""",
        )

        # 4. MathJax renders equations asynchronously; wait only when the runtime is present.
        self._evaluate_ready_step(
            page,
            step_name="MathJax",
            deadline=deadline,
            wait_script="""() => {
                return new Promise((resolve, reject) => {
                    if (typeof MathJax === 'undefined') {
                        resolve();
                        return;
                    }

                    // MathJax 4.1 documents MathDocument.whenReady() for synchronizing
                    // with pending typesetting work. Keep the startup.promise fallback
                    // for v3/v4 initial typesetting because ADR can export either shape.
                    if (
                        MathJax.startup &&
                        MathJax.startup.document &&
                        typeof MathJax.startup.document.whenReady === 'function'
                    ) {
                        MathJax.startup.document.whenReady(() => undefined).then(resolve, reject);
                    } else if (
                        MathJax.startup &&
                        MathJax.startup.promise &&
                        typeof MathJax.startup.promise.then === 'function'
                    ) {
                        MathJax.startup.promise.then(resolve, reject);
                    } else if (
                        MathJax.Hub &&
                        typeof MathJax.Hub.Queue === 'function'
                    ) {
                        // PyDynamicReporting v1 compatibility shim: MathJax 2.0 uses
                        // Hub.Queue() for synchronization. Remove this branch in v2 after
                        // legacy MathJax 2 offline exports are no longer supported.
                        MathJax.Hub.Queue(resolve);
                    } else {
                        resolve();
                    }
                });
            }""",
        )

        # 5. Plotly charts: each .nexus-plot container gets class 'loaded' after
        #    Plotly.Plots.resize() resolves and the spinner hides.
        self._evaluate_ready_step(
            page,
            step_name="Plotly charts",
            deadline=deadline,
            wait_script="""() => {
                return new Promise((resolve) => {
                    const plots = document.querySelectorAll('.nexus-plot');
                    if (plots.length === 0) { resolve(); return; }
                    let remaining = plots.length;
                    function check() { if (--remaining <= 0) resolve(); }
                    plots.forEach((plot) => {
                        if (plot.classList.contains('loaded')) { check(); return; }
                        const observer = new MutationObserver(() => {
                            if (plot.classList.contains('loaded')) {
                                observer.disconnect();
                                check();
                            }
                        });
                        observer.observe(plot, { attributes: true, attributeFilter: ['class'] });
                    });
                });
            }""",
        )

        # 6. Images: wait for every <img> to finish loading (covers static images,
        #    scene proxy thumbnails, file proxy images, animation thumbnails).
        self._evaluate_ready_step(
            page,
            step_name="Images",
            deadline=deadline,
            wait_script="""() => {
                return new Promise((resolve) => {
                    const imgs = document.querySelectorAll('img');
                    if (imgs.length === 0) { resolve(); return; }
                    let remaining = imgs.length;
                    function done() { if (--remaining <= 0) resolve(); }
                    imgs.forEach((img) => {
                        // Require both a source and decoded image dimensions before fast-passing
                        // the image. ``img.complete`` alone is too weak because a src-less <img>
                        // can already report complete even though async product code has not yet
                        // populated the final image bytes.
                        const hasSource = Boolean(img.currentSrc || img.getAttribute('src'));
                        if (hasSource && img.complete && img.naturalWidth > 0) {
                            done();
                            return;
                        }
                        img.addEventListener('load', done, { once: true });
                        img.addEventListener('error', done, { once: true });
                    });
                });
            }""",
        )

        # 7. Videos: wait for every <video> to reach HAVE_CURRENT_DATA (readyState >= 2)
        #    so the current frame is available before Chromium prints the page.
        self._evaluate_ready_step(
            page,
            step_name="Videos",
            deadline=deadline,
            wait_script="""() => {
                return new Promise((resolve) => {
                    const videos = document.querySelectorAll('video');
                    if (videos.length === 0) { resolve(); return; }
                    let remaining = videos.length;
                    function done() { if (--remaining <= 0) resolve(); }
                    videos.forEach((vid) => {
                        if (vid.readyState >= 2) { done(); return; }
                        vid.addEventListener('loadeddata', done, { once: true });
                        vid.addEventListener('error', done, { once: true });
                    });
                });
            }""",
        )

        # 8. Double requestAnimationFrame waits for an actual composited frame
        #     after all preceding DOM/style work settles.
        self._evaluate_ready_step(
            page,
            step_name="Double requestAnimationFrame",
            deadline=deadline,
            wait_script="""() => {
                return new Promise((resolve) => {
                    requestAnimationFrame(() => requestAnimationFrame(resolve));
                });
            }""",
        )

        self._logger.info("Browser render readiness checks completed.")
