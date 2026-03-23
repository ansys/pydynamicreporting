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

"""Browser-fidelity HTML-to-PDF rendering for serverless ADR exports."""

import re
from pathlib import Path
from typing import Any

from ..adr_utils import get_logger
from ..exceptions import ADRException


class PlaywrightPDFRenderer:
    """Render an exported ADR HTML directory to PDF via headless Chromium.

    Parameters
    ----------
    html_dir : Path
        Directory containing the exported offline HTML report and its assets.
    filename : str, default: "index.html"
        HTML entry-point filename inside ``html_dir``.
    landscape : bool, default: False
        Whether to render the PDF in landscape orientation.
    logger : Any, optional
        Logger used for renderer lifecycle messages.
    """

    _DEFAULT_MARGINS: dict[str, str] = {
        "top": "10mm",
        "right": "10mm",
        "bottom": "10mm",
        "left": "10mm",
    }
    _CSS_UNIT_TO_PX: dict[str, float] = {
        "": 1.0,
        "px": 1.0,
        "pt": 96.0 / 72.0,
        "in": 96.0,
        "cm": 96.0 / 2.54,
        "mm": 96.0 / 25.4,
    }
    _DEFAULT_PAGE_HEIGHT: str = "297mm"
    _DEFAULT_BROWSER_VIEWPORT_WIDTH: int = 1600
    _DEFAULT_BROWSER_VIEWPORT_HEIGHT: int = 900
    _DEFAULT_RENDER_TIMEOUT: float = 30.0

    def __init__(
        self,
        html_dir: Path,
        filename: str = "index.html",
        *,
        landscape: bool = False,
        logger: Any = None,
    ) -> None:
        """Initialize the renderer with a self-contained HTML export directory."""
        self._html_dir = Path(html_dir)
        self._filename = filename
        self._landscape = landscape
        self._margins = dict(self._DEFAULT_MARGINS)
        self._render_timeout = self._DEFAULT_RENDER_TIMEOUT
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
            If Playwright is unavailable or the browser render/export flow fails.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ADRException(
                "Playwright is required for browser-fidelity PDF export. Install it with:\n"
                "  pip install ansys-dynamicreporting-core\n"
                "  playwright install chromium"
            ) from exc

        try:
            with sync_playwright() as playwright:
                self._logger.info("Launching headless Chromium for browser PDF export.")
                browser = playwright.chromium.launch(headless=True)

                try:
                    # Fix the responsive layout width up front so Plotly and other browser-rendered
                    # items lay themselves out deterministically before the PDF width is computed.
                    page = browser.new_page(
                        viewport={
                            "width": self._DEFAULT_BROWSER_VIEWPORT_WIDTH,
                            "height": self._DEFAULT_BROWSER_VIEWPORT_HEIGHT,
                        }
                    )
                    file_url = (self._html_dir / self._filename).as_uri()

                    # Load the exported offline report exactly as Chromium would see it from disk.
                    self._logger.info(f"Loading exported HTML for browser PDF export: {file_url}")
                    page.goto(file_url, wait_until="networkidle")

                    # Force screen media so the PDF matches the browser view instead of print CSS.
                    page.emulate_media(media="screen")
                    self._apply_pdf_capture_styles(page)
                    self._wait_for_render_ready(page)
                    pdf_width = self._compute_pdf_width(page)
                    pdf_options = {
                        # Keep page height explicit so pagination remains under ADR's control
                        # instead of depending entirely on Playwright's default page format.
                        "height": self._DEFAULT_PAGE_HEIGHT,
                        "landscape": self._landscape,
                        "margin": self._margins,
                        "print_background": True,
                    }
                    if pdf_width is not None:
                        pdf_options["width"] = pdf_width

                    pdf_bytes = page.pdf(**pdf_options)
                    self._logger.info(
                        f"Browser PDF generated successfully ({len(pdf_bytes)} bytes)."
                    )
                    return pdf_bytes
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
        page.add_style_tag(
            content="""
                @media print {
                    adr-data-item,
                    .nexus-plot,
                    .nexus-plot > .plot-container,
                    .js-plotly-plot,
                    .plot-container,
                    .svg-container {
                        break-inside: avoid !important;
                        page-break-inside: avoid !important;
                    }

                    adr-data-item,
                    .nexus-plot,
                    .plot-container,
                    .svg-container,
                    .main-svg,
                    .table-responsive {
                        overflow: visible !important;
                        max-height: none !important;
                    }

                    .adr-spinner-loader-container,
                    .modebar {
                        display: none !important;
                    }
                }
            """,
        )

    def _compute_pdf_width(self, page: Any) -> str | None:
        """Compute an explicit PDF page width when needed to preserve browser content."""
        margin_width_px = self._css_length_to_px(
            self._DEFAULT_MARGINS["left"]
        ) + self._css_length_to_px(self._DEFAULT_MARGINS["right"])
        content_width_px = self._measure_content_width_px(page)
        layout_width_px = self._measure_layout_width_px(page)
        if content_width_px <= 0:
            self._logger.info(
                "No visible report width was found; using Playwright's default PDF page width."
            )
            return None

        # The PDF page must preserve the same layout canvas that Chromium used while rendering
        # the report. If the PDF content area is narrower than the browser viewport, responsive
        # Plotly legends can still be clipped at the right edge even when the report root itself
        # appears narrower than the viewport.
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
                        if (node.getClientRects().length === 0) {
                            continue;
                        }
                        const rect = node.getBoundingClientRect();
                        const offsetLeft = rect.left - rootRect.left;
                        maxRight = Math.max(maxRight, rect.right - rootRect.left);
                        if ('scrollWidth' in node) {
                            maxRight = Math.max(maxRight, offsetLeft + (node.scrollWidth || 0));
                        }
                    }
                    return maxRight;
                }""",
            )
        )

    def _measure_layout_width_px(self, page: Any) -> float:
        """Measure the effective browser layout width in CSS pixels."""
        return float(
            page.evaluate(
                """() => {
                    return Math.max(
                        window.innerWidth || 0,
                        document.documentElement?.clientWidth || 0,
                        document.body?.clientWidth || 0
                    );
                }""",
            )
        )

    def _css_length_to_px(self, value: str) -> float:
        """Convert a CSS absolute length to CSS pixels."""
        match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*", value)
        if match is None:
            raise ADRException(f"Unsupported CSS length for PDF rendering: {value!r}")

        number = float(match.group(1))
        unit = match.group(2).lower()
        if unit not in self._CSS_UNIT_TO_PX:
            raise ADRException(f"Unsupported CSS length unit for PDF rendering: {value!r}")
        return number * self._CSS_UNIT_TO_PX[unit]

    def _wait_for_render_ready(self, page: Any) -> None:
        """Wait for browser rendering signals that indicate the page is ready to print."""
        timeout_ms = int(self._render_timeout * 1000)
        self._logger.info("Waiting for browser render readiness signals.")
        # Playwright's sync ``evaluate`` API uses the page's default timeout rather than a
        # per-call ``timeout=...`` keyword, so set the readiness budget once for this phase.
        page.set_default_timeout(timeout_ms)

        # 1. FOUC gate: ADR hides the report with ``body #report_root { opacity: 0 }``
        #    until all custom web-components are registered, which adds ``body.loaded``.
        #    Without this, the entire PDF is blank.
        page.evaluate(
            """() => new Promise((resolve) => {
                if (document.body.classList.contains('loaded')) { resolve(); return; }
                const observer = new MutationObserver(() => {
                    if (document.body.classList.contains('loaded')) {
                        observer.disconnect();
                        resolve();
                    }
                });
                observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
            })""",
        )

        # 2. FOUC transition: ``body.loaded #report_root`` triggers a 0.4s opacity
        #    transition. Wait for it to reach opacity 1 before capturing.
        page.evaluate(
            """() => new Promise((resolve) => {
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
            })""",
        )

        # 3. Web fonts (FontAwesome woff2 + MathJax woff2).
        page.evaluate("() => document.fonts.ready")

        # 4. MathJax renders equations asynchronously; wait only when the runtime is present.
        page.evaluate(
            """() => {
                return new Promise((resolve) => {
                    if (typeof MathJax !== 'undefined' && MathJax.startup) {
                        MathJax.startup.promise.then(resolve);
                    } else {
                        resolve();
                    }
                });
            }""",
        )

        # 5. Plotly charts: each .nexus-plot container gets class 'loaded' after
        #    Plotly.Plots.resize() resolves and the spinner hides.
        page.evaluate(
            """() => new Promise((resolve) => {
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
            })""",
        )

        # 6. Images: wait for every <img> to finish loading (covers static images,
        #    scene proxy thumbnails, file proxy images, animation thumbnails).
        page.evaluate(
            """() => new Promise((resolve) => {
                const imgs = document.querySelectorAll('img');
                if (imgs.length === 0) { resolve(); return; }
                let remaining = imgs.length;
                function done() { if (--remaining <= 0) resolve(); }
                imgs.forEach((img) => {
                    if (img.complete) { done(); return; }
                    img.addEventListener('load', done, { once: true });
                    img.addEventListener('error', done, { once: true });
                });
            })""",
        )

        # 7. Videos: wait for every <video> to reach HAVE_CURRENT_DATA (readyState >= 2)
        #    so the current frame is available before Chromium prints the page.
        page.evaluate(
            """() => new Promise((resolve) => {
                const videos = document.querySelectorAll('video');
                if (videos.length === 0) { resolve(); return; }
                let remaining = videos.length;
                function done() { if (--remaining <= 0) resolve(); }
                videos.forEach((vid) => {
                    if (vid.readyState >= 2) { done(); return; }
                    vid.addEventListener('loadeddata', done, { once: true });
                    vid.addEventListener('error', done, { once: true });
                });
            })""",
        )

        # 8. DataTables: each report table must be fully initialized.
        #    Use table[id^="table_"] selector because the "dataTable" class is added
        #    BY DataTables after init — table.dataTable would miss uninitialized tables.
        #    (analysis §3.2, §7.1, Appendix C #14).
        page.evaluate(
            """() => new Promise((resolve) => {
                if (typeof $ === 'undefined' || typeof $.fn.DataTable === 'undefined') {
                    resolve(); return;
                }
                const tables = document.querySelectorAll('table[id^="table_"]');
                if (tables.length === 0) { resolve(); return; }
                let remaining = tables.length;
                function done() { if (--remaining <= 0) resolve(); }
                tables.forEach((table) => {
                    if ($.fn.DataTable.isDataTable(table)) { done(); return; }
                    $(table).on('init.dt', function() { done(); });
                });
            })""",
        )

        # 9. Active 3D viewers: wait for each ansys-nexus-viewer spinner to hide.
        #    In the browser render path, viewers have active="true" and load scene
        #    data asynchronously. The #render-wait spinner hides on load complete.
        page.evaluate(
            """() => new Promise((resolve) => {
                const viewers = document.querySelectorAll('ansys-nexus-viewer');
                if (viewers.length === 0) { resolve(); return; }
                let remaining = viewers.length;
                function done() { if (--remaining <= 0) resolve(); }
                viewers.forEach((viewer) => {
                    const spinner = viewer.querySelector('#render-wait');
                    if (!spinner || spinner.style.display !== 'block') { done(); return; }
                    const observer = new MutationObserver(() => {
                        if (spinner.style.display !== 'block') {
                            observer.disconnect();
                            done();
                        }
                    });
                    observer.observe(spinner, { attributes: true, attributeFilter: ['style'] });
                });
            })""",
        )

        # 10. Double requestAnimationFrame waits for an actual composited frame
        #     after all preceding DOM/style work settles.
        page.evaluate(
            """() => new Promise((resolve) =>
                requestAnimationFrame(() => requestAnimationFrame(resolve))
            )""",
        )

        self._logger.info("Browser render readiness checks completed.")
