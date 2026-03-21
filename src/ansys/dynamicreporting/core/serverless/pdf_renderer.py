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
    page_width : str, default: "210mm"
        CSS page width passed to Chromium's PDF generator.
    page_height : str, default: "297mm"
        CSS page height passed to Chromium's PDF generator.
    landscape : bool, default: False
        Whether to render the PDF in landscape orientation.
    margins : dict[str, str], optional
        Page margins with ``top``, ``right``, ``bottom``, and ``left`` keys.
        If omitted, 10 mm margins are used on every side.
    render_timeout : float, default: 30.0
        Per-signal timeout, in seconds, for asynchronous browser readiness checks.
    logger : Any, optional
        Logger used for renderer lifecycle messages.
    """

    _DEFAULT_MARGINS: dict[str, str] = {
        "top": "10mm",
        "right": "10mm",
        "bottom": "10mm",
        "left": "10mm",
    }

    def __init__(
        self,
        html_dir: Path,
        filename: str = "index.html",
        *,
        page_width: str = "210mm",
        page_height: str = "297mm",
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = 30.0,
        logger: Any = None,
    ) -> None:
        """Initialize the renderer with a self-contained HTML export directory."""
        self._html_dir = Path(html_dir)
        self._filename = filename
        self._page_width = page_width
        self._page_height = page_height
        self._landscape = landscape
        # Copy the caller-provided mapping so later mutations do not alter this renderer's state.
        self._margins = dict(margins) if margins is not None else dict(self._DEFAULT_MARGINS)
        self._render_timeout = render_timeout
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
                "  pip install ansys-dynamicreporting-core[pdf]\n"
                "  playwright install chromium"
            ) from exc

        try:
            with sync_playwright() as playwright:
                self._logger.info("Launching headless Chromium for browser PDF export.")
                browser = playwright.chromium.launch(headless=True)

                try:
                    page = browser.new_page()
                    file_url = (self._html_dir / self._filename).as_uri()

                    # Load the exported offline report exactly as Chromium would see it from disk.
                    self._logger.info(f"Loading exported HTML for browser PDF export: {file_url}")
                    page.goto(file_url, wait_until="networkidle")

                    # Force screen media so the PDF matches the browser view instead of print CSS.
                    page.emulate_media(media="screen")
                    self._wait_for_render_ready(page)

                    pdf_bytes = page.pdf(
                        width=self._page_width,
                        height=self._page_height,
                        landscape=self._landscape,
                        margin=self._margins,
                        print_background=True,
                    )
                    self._logger.info(f"Browser PDF generated successfully ({len(pdf_bytes)} bytes).")
                    return pdf_bytes
                finally:
                    browser.close()
        except ADRException:
            raise
        except Exception as exc:
            raise ADRException(f"Browser PDF rendering failed: {exc}") from exc

    def _wait_for_render_ready(self, page: Any) -> None:
        """Wait for browser rendering signals that indicate the page is ready to print."""
        timeout_ms = int(self._render_timeout * 1000)
        self._logger.info("Waiting for browser render readiness signals.")

        # Web fonts can shift layout after the initial network load, so wait for font completion first.
        page.evaluate("() => document.fonts.ready", timeout=timeout_ms)

        # MathJax renders equations asynchronously; wait only when the runtime is present.
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
            timeout=timeout_ms,
        )

        # Plotly charts publish an afterplot signal once their first full render is complete.
        page.evaluate(
            """() => {
                return new Promise((resolve) => {
                    const plots = document.querySelectorAll('.js-plotly-plot');
                    if (plots.length === 0) {
                        resolve();
                        return;
                    }
                    let remaining = plots.length;
                    plots.forEach((plot) => {
                        if (plot.data) {
                            remaining -= 1;
                        } else {
                            plot.on('plotly_afterplot', () => {
                                remaining -= 1;
                                if (remaining <= 0) {
                                    resolve();
                                }
                            });
                        }
                    });
                    if (remaining <= 0) {
                        resolve();
                    }
                });
            }""",
            timeout=timeout_ms,
        )

        # DataTables mutates table markup after startup, so wait for each managed table to initialize.
        page.evaluate(
            """() => {
                return new Promise((resolve) => {
                    if (typeof $ === 'undefined' || typeof $.fn.DataTable === 'undefined') {
                        resolve();
                        return;
                    }
                    const tables = document.querySelectorAll('table.dataTable');
                    if (tables.length === 0) {
                        resolve();
                        return;
                    }
                    let remaining = tables.length;
                    tables.forEach((table) => {
                        if ($.fn.DataTable.isDataTable(table)) {
                            remaining -= 1;
                        } else {
                            $(table).on('init.dt', () => {
                                remaining -= 1;
                                if (remaining <= 0) {
                                    resolve();
                                }
                            });
                        }
                    });
                    if (remaining <= 0) {
                        resolve();
                    }
                });
            }""",
            timeout=timeout_ms,
        )

        # Double requestAnimationFrame waits for an actual paint after the preceding DOM/style work settles.
        page.evaluate(
            """() => new Promise((resolve) =>
                requestAnimationFrame(() => requestAnimationFrame(resolve))
            )""",
            timeout=timeout_ms,
        )

        self._logger.info("Browser render readiness checks completed.")
