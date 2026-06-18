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

import os
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

import ansys.dynamicreporting.core.utils.pdf_renderer as pdf_renderer_module
from ansys.dynamicreporting.core.exceptions import ADRException
from ansys.dynamicreporting.core.utils.pdf_renderer import _PlaywrightReportURLPDFRenderer
from ansys.dynamicreporting.core.utils.pdf_renderer import PlaywrightPDFRenderer


def _write_html(tmp_path: Path, body: str) -> Path:
    """Write a minimal HTML file for renderer tests and return its directory."""
    html_path = tmp_path / "index.html"
    html_path.write_text(body, encoding="utf-8")
    return tmp_path


def _simple_renderer(
    tmp_path: Path,
    body: str,
    *,
    landscape: bool = False,
    render_timeout: float | None = None,
) -> PlaywrightPDFRenderer:
    """Create a renderer for a temporary HTML document with test-controlled options."""
    html_dir = _write_html(tmp_path, body)
    renderer = PlaywrightPDFRenderer(
        html_dir=html_dir,
        landscape=landscape,
        render_timeout=(
            PlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT
            if render_timeout is None
            else render_timeout
        ),
    )
    return renderer


@dataclass(frozen=True)
class _FakePlaywrightStack:
    """The mocked Playwright object graph that ``render_pdf`` walks, exposed for assertions."""

    playwright: Mock
    browser: Mock
    context: Mock
    page: Mock


def _stub_playwright_stack(monkeypatch: pytest.MonkeyPatch) -> _FakePlaywrightStack:
    """Build a fake Chromium stack and route ``sync_playwright`` to it without launching a browser."""
    page = Mock()
    page.pdf.return_value = b"%PDF-mock"
    context = Mock()
    context.new_page.return_value = page
    browser = Mock()
    browser.new_context.return_value = context
    playwright = Mock()
    playwright.chromium.launch.return_value = browser
    playwright_manager = MagicMock()
    playwright_manager.__enter__.return_value = playwright

    monkeypatch.setattr(pdf_renderer_module, "sync_playwright", lambda: playwright_manager)
    return _FakePlaywrightStack(
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
    )


def _stub_playwright_render(
    monkeypatch: pytest.MonkeyPatch,
    renderer: PlaywrightPDFRenderer,
    *,
    pdf_width: str | None = None,
) -> tuple[Mock, Mock, Mock]:
    """Stub the full render path (skipping readiness waits and width measurement) and return the page."""
    stack = _stub_playwright_stack(monkeypatch)
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)
    monkeypatch.setattr(renderer, "_compute_pdf_width", lambda page: pdf_width)
    return stack.page, stack.context, stack.browser


def _browser_binary_info(
    browser_binary_dir: Path,
) -> pdf_renderer_module.PlaywrightBrowserBinaryInfo:
    """Create validated product-binary metadata for renderer tests."""
    return pdf_renderer_module.PlaywrightBrowserBinaryInfo(
        path=browser_binary_dir,
        browser_name=pdf_renderer_module.PlaywrightBrowserBinaryInfo.EXPECTED_BROWSER_NAME,
        machine_arch="win64",
        packaged_binary_dir="chromium_headless_shell-1223",
    )


@pytest.mark.unit
def test_playwright_pdf_from_simple_html(tmp_path):
    renderer = _simple_renderer(tmp_path, "<html><body><h1>Hello</h1></body></html>")
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_landscape(tmp_path):
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Landscape content</p></body></html>",
        landscape=True,
    )
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_validates_missing_entrypoint_before_browser_start(tmp_path):
    renderer = PlaywrightPDFRenderer(html_dir=tmp_path)

    with pytest.raises(ADRException, match="entry-point file does not exist"):
        renderer.render_pdf()


@pytest.mark.unit
def test_playwright_pdf_uses_render_timeout_for_browser_launch_and_navigation(
    tmp_path, monkeypatch
):
    html_dir = _write_html(tmp_path, "<html><body><p>Navigation timeout</p></body></html>")
    renderer = PlaywrightPDFRenderer(html_dir=html_dir, render_timeout=12.5)
    stack = _stub_playwright_stack(monkeypatch)
    monotonic_values = iter([100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0])

    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)
    monkeypatch.setattr(renderer, "_compute_pdf_width", lambda page: None)

    assert renderer.render_pdf() == b"%PDF-mock"
    stack.playwright.chromium.launch.assert_called_once_with(headless=True, timeout=12500)
    stack.page.goto.assert_called_once_with(
        (html_dir / "index.html").resolve().as_uri(),
        wait_until="load",
        timeout=12500,
    )


@pytest.mark.unit
def test_playwright_pdf_rounds_tiny_browser_timeouts_up_to_one_millisecond(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Small timeout</p></body></html>")
    renderer = PlaywrightPDFRenderer(html_dir=html_dir, render_timeout=0.0001)
    stack = _stub_playwright_stack(monkeypatch)
    monotonic_values = iter([100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0])

    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)
    monkeypatch.setattr(renderer, "_compute_pdf_width", lambda page: None)

    renderer.render_pdf()

    # Playwright treats timeout=0 as "no timeout", so tiny positive ADR budgets round up to 1 ms
    # under the shared browser-phase deadline helper instead of truncating to 0.
    stack.playwright.chromium.launch.assert_called_once_with(headless=True, timeout=1)
    stack.page.goto.assert_called_once_with(
        (html_dir / "index.html").resolve().as_uri(),
        wait_until="load",
        timeout=1,
    )


@pytest.mark.unit
def test_playwright_pdf_reuses_one_browser_phase_deadline_for_readiness(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Shared deadline</p></body></html>")
    renderer = PlaywrightPDFRenderer(html_dir=html_dir, render_timeout=10.0)
    _stub_playwright_stack(monkeypatch)
    captured_deadline: dict[str, float] = {}
    monotonic_values = iter([100.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0])

    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))

    def capture_ready(page, deadline=None):
        captured_deadline["value"] = deadline

    monkeypatch.setattr(renderer, "_wait_for_render_ready", capture_ready)
    monkeypatch.setattr(renderer, "_compute_pdf_width", lambda page: None)

    renderer.render_pdf()

    # The readiness phase must spend from the original browser deadline instead of resetting a
    # fresh render_timeout window after navigation has already consumed part of the budget.
    assert captured_deadline["value"] == 110.0


@pytest.mark.unit
def test_playwright_pdf_normalizes_playwright_navigation_timeout(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Navigation timeout</p></body></html>")
    renderer = PlaywrightPDFRenderer(html_dir=html_dir, render_timeout=12.5)
    stack = _stub_playwright_stack(monkeypatch)
    stack.page.goto.side_effect = PlaywrightTimeoutError("Timeout 12500ms exceeded")
    monotonic_values = iter([100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0])

    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(
        ADRException,
        match=r"Browser PDF rendering failed: page navigation timed out after 12\.5s",
    ):
        renderer.render_pdf()

    stack.context.close.assert_called_once_with()
    stack.browser.close.assert_called_once_with()


@pytest.mark.unit
def test_playwright_pdf_closes_browser_when_new_context_creation_fails(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Context failure</p></body></html>")
    renderer = PlaywrightPDFRenderer(html_dir=html_dir)
    stack = _stub_playwright_stack(monkeypatch)
    stack.browser.new_context.side_effect = RuntimeError("new context boom")

    with pytest.raises(ADRException, match="Browser PDF rendering failed: new context boom"):
        renderer.render_pdf()

    stack.browser.close.assert_called_once_with()


@pytest.mark.unit
def test_live_report_url_renderer_navigates_to_report_url(monkeypatch):
    renderer = _PlaywrightReportURLPDFRenderer(
        url="http://127.0.0.1:8000/reports/report_display/?view=report-guid&print=pdf",
        auth_cookies=[
            {
                "name": "sessionid",
                "value": "abc123",
                "domain": "127.0.0.1",
                "path": "/",
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ],
        render_timeout=12.5,
    )
    page, context, browser = _stub_playwright_render(monkeypatch, renderer)

    assert renderer.render_pdf() == b"%PDF-mock"
    page.goto.assert_called_once_with(
        "http://127.0.0.1:8000/reports/report_display/?view=report-guid&print=pdf",
        wait_until="load",
        timeout=12500,
    )
    # The live report path must stay online so Chromium can fetch the report and assets directly
    # from the already-running ADR service instead of expecting a staged offline bundle.
    browser.new_context.assert_called_once_with(
        viewport={
            "width": PlaywrightPDFRenderer._DEFAULT_BROWSER_VIEWPORT_WIDTH,
            "height": PlaywrightPDFRenderer._DEFAULT_BROWSER_VIEWPORT_HEIGHT,
        },
        service_workers="block",
        accept_downloads=False,
    )
    context.add_cookies.assert_called_once_with(
        [
            {
                "name": "sessionid",
                "value": "abc123",
                "domain": "127.0.0.1",
                "path": "/",
                "httpOnly": True,
                "sameSite": "Lax",
            }
        ]
    )
    # The live path stays online and therefore must not install the offline-only network blocks
    # used by file:// exports.
    context.route.assert_not_called()
    context.route_web_socket.assert_not_called()


@pytest.mark.unit
def test_live_report_url_renderer_validates_absolute_urls():
    with pytest.raises(ADRException, match="report URL is not valid"):
        _PlaywrightReportURLPDFRenderer(url="/reports/report_display/?view=report-guid")


@pytest.mark.unit
def test_playwright_pdf_uses_a4_width_when_content_width_is_unavailable(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>No measured width</p></body></html>")
    page, _, _ = _stub_playwright_render(monkeypatch, renderer)

    renderer.render_pdf()

    # A missing measured width must still produce a consistent A4-sized page.
    pdf_options = page.pdf.call_args.kwargs
    assert pdf_options["width"] == PlaywrightPDFRenderer._DEFAULT_PAGE_WIDTH
    assert pdf_options["height"] == PlaywrightPDFRenderer._DEFAULT_PAGE_HEIGHT


@pytest.mark.unit
def test_playwright_pdf_uses_computed_width_when_content_width_is_available(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Measured width</p></body></html>")
    page, _, _ = _stub_playwright_render(monkeypatch, renderer, pdf_width="488.00px")

    renderer.render_pdf()

    # Measured content width takes priority so wide browser-rendered content is not clipped.
    pdf_options = page.pdf.call_args.kwargs
    assert pdf_options["width"] == "488.00px"
    assert pdf_options["height"] == PlaywrightPDFRenderer._DEFAULT_PAGE_HEIGHT


@pytest.mark.unit
def test_playwright_pdf_applies_capture_styles_before_readiness_and_width(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Ordering</p></body></html>")
    page, _, _ = _stub_playwright_render(monkeypatch, renderer, pdf_width="420.00px")
    call_order: list[str] = []

    # Width measurement depends on the capture CSS already being present, and readiness
    # waits must observe the same styled DOM that Chromium will later print to PDF.
    monkeypatch.setattr(
        renderer,
        "_apply_pdf_capture_styles",
        lambda observed_page: call_order.append("styles"),
    )
    monkeypatch.setattr(
        renderer,
        "_wait_for_render_ready",
        lambda observed_page, deadline=None: call_order.append("ready"),
    )

    def capture_width(observed_page):
        call_order.append("width")
        return "420.00px"

    monkeypatch.setattr(renderer, "_compute_pdf_width", capture_width)

    renderer.render_pdf()

    assert call_order == ["styles", "ready", "width"]
    page.pdf.assert_called_once()


@pytest.mark.unit
def test_playwright_pdf_with_mathjax_content(tmp_path):
    # The inline MathJax stub gives the readiness check a real startup promise to await.
    html = """
    <html>
    <body>
        <script>
            window.MathJax = {
                startup: {
                    promise: Promise.resolve()
                }
            };
        </script>
        <div>\\(x^2 + y^2 = z^2\\)</div>
    </body>
    </html>
    """
    renderer = _simple_renderer(tmp_path, html)
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_waits_for_mathjax_document_when_ready_api(tmp_path):
    # MathJax 4.1 exposes MathDocument.whenReady() for pending typesetting work. The
    # never-resolving startup promise proves that the renderer prefers that documented path.
    html = """
    <html>
    <body>
        <script>
            window.MathJax = {
                startup: {
                    document: {
                        whenReady: function(callback) {
                            return Promise.resolve().then(callback);
                        }
                    },
                    promise: new Promise(function() {})
                },
                whenReady: function() {
                    throw new Error('unsupported top-level MathJax.whenReady was called');
                }
            };
        </script>
        <div>\\(a^2 + b^2 = c^2\\)</div>
    </body>
    </html>
    """
    renderer = _simple_renderer(tmp_path, html)
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_waits_for_mathjax_hub_queue_api(tmp_path):
    # MathJax 2 exports still use Hub.Queue() to synchronize with the legacy renderer.
    html = """
    <html>
    <body>
        <script>
            window.MathJax = {
                Hub: {
                    Queue: function(callback) {
                        callback();
                    }
                }
            };
        </script>
        <div>\\(e^{i\\pi} + 1 = 0\\)</div>
    </body>
    </html>
    """
    renderer = _simple_renderer(tmp_path, html)
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_signal_timeout(tmp_path):
    # This mock Plotly container never gets class 'loaded', so the readiness MutationObserver
    # never fires and the promise times out.
    html = """
    <html>
    <body class="loaded">
        <section id="report_root" style="opacity:1">
            <div class="nexus-plot" id="plot"></div>
        </section>
    </body>
    </html>
    """
    renderer = _simple_renderer(tmp_path, html, render_timeout=0.5)

    # pytest.raises() can only capture the exception; it cannot assert two independent
    # message fragments and explicitly fail when no exception is raised. The try/except/else
    # pattern handles all three cases: correct failure, wrong message, and no failure.
    try:
        renderer.render_pdf()
    except ADRException as exc:
        error_text = str(exc)
        assert "Browser PDF rendering failed" in error_text
        # The shared browser-phase deadline can expire either during navigation or later
        # during the readiness wait, but the public API should expose one normalized
        # timeout shape either way.
        assert "timed out after 0.5s" in error_text
        assert "exceeded" not in error_text.lower()
    else:
        pytest.fail("Expected render_pdf() to fail due to readiness timeout.")


@pytest.mark.unit
def test_apply_pdf_capture_styles_targets_plot_containers(tmp_path):
    renderer = _simple_renderer(tmp_path, "<html><body><p>CSS injection</p></body></html>")
    page = Mock()

    renderer._apply_pdf_capture_styles(page)

    css = page.add_style_tag.call_args.kwargs["content"]
    assert "adr-data-item" in css
    assert ".nexus-plot" in css
    assert ".avz-viewer" in css
    assert "ansys-nexus-viewer" in css
    assert "table.tree" in css
    assert 'adr-slider-template > section[id^="slider_container_"]' in css
    assert 'adr-slider-template > section[id^="slider_container_"] > section.adr-row' in css
    assert "img.img-fluid" in css
    assert "video.img-fluid" in css
    assert ".ansys-nexus-proxy" in css
    assert "h2:has(+ section.adr-container)" in css
    assert "header:has(+ section.adr-panel-body)" in css
    assert 'table.table-fit-head > thead[style*="visibility: collapse"]' in css
    assert "--adr-border-color: #adb5bd !important;" in css
    assert "--adr-border-color-translucent: rgba(0, 0, 0, 0.28) !important;" in css
    assert "-webkit-print-color-adjust: exact !important;" in css
    assert "print-color-adjust: exact !important;" in css
    assert "display: block !important;" in css
    assert "@media print" not in css
    assert "[nexus_template]" not in css


@pytest.mark.unit
def test_apply_pdf_capture_styles_take_effect_under_screen_media(tmp_path):
    html = """
    <html>
    <head>
        <style>
            :root {
                --adr-border-color: #dee2e6;
                --adr-border-color-translucent: rgba(0, 0, 0, 0.175);
                --adr-border-width: 1px;
            }

            tbody,
            td,
            tfoot,
            th,
            thead,
            tr {
                border-color: inherit;
                border-style: solid;
                border-width: 0;
            }

            .table {
                border-color: var(--adr-border-color);
            }

            .table-bordered > :not(caption) > * {
                border-width: var(--adr-border-width) 0;
            }

            .table-bordered > :not(caption) > * > * {
                border-width: 0 var(--adr-border-width);
            }

            .table td,
            .table th {
                border-top: 1px solid var(--adr-border-color);
            }

            .adr-panel {
                border: var(--adr-border-width) solid var(--adr-border-color-translucent);
            }

            .adr-panel-header {
                border-bottom: var(--adr-border-width) solid var(--adr-border-color-translucent);
            }
        </style>
    </head>
    <body>
        <section id="report_root">
        <a id="TOC_item_tgt_1"></a>
        <br />
        <h2 id="section-heading">Material Properties</h2>
        <section class="adr-container" id="section-body">
        <adr-data-item id="item">
            <div class="nexus-plot" id="plot">
                <div class="plot-container">Plot content</div>
            </div>
            <div class="avz-viewer" id="scene-wrap">
                <ansys-nexus-viewer id="viewer"></ansys-nexus-viewer>
            </div>
            <img
                id="image"
                class="img img-fluid"
                alt="preview"
                src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
            />
            <table class="table table-bordered table-fit-head" id="kv-table">
                <thead id="collapsed-head" style="visibility: collapse;">
                    <tr>
                        <th></th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <th>Application</th>
                        <td id="table-cell">Fluent</td>
                    </tr>
                </tbody>
            </table>
        </adr-data-item>
        </section>
        <adr-slider-template>
            <section class="adr-container" id="slider_container_test">
                <section class="adr-row" id="slider_row">
                    <section class="adr-slider-panzoom-container">
                        <p>Controls</p>
                    </section>
                    <section>
                        <p>Slider content</p>
                    </section>
                </section>
            </section>
        </adr-slider-template>
        <section class="adr-panel" id="panel">
            <header class="adr-panel-header" id="panel-heading">
                <h2>System Information</h2>
            </header>
            <section class="adr-panel-body" id="panel-body">
                <p>Panel content</p>
            </section>
        </section>
        </section>
    </body>
    </html>
    """
    renderer = _simple_renderer(tmp_path, html)
    # Import at function scope: this test is the only caller and keeping it here makes the
    # Chromium dependency explicit and co-located with its use rather than a module-level side effect.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((renderer._html_dir / renderer._filename).as_uri(), wait_until="load")
        # The PDF renderer uses screen media so the captured PDF matches the browser layout.
        # The anti-splitting rules must still apply in that media mode or Plotly figures can
        # break across pages during PDF pagination.
        page.emulate_media(media="screen")
        renderer._apply_pdf_capture_styles(page)
        computed_styles = page.evaluate(
            """() => {
                    const sectionHeading = document.getElementById('section-heading');
                    const item = document.getElementById('item');
                    const plot = document.getElementById('plot');
                    const viewer = document.getElementById('viewer');
                    const image = document.getElementById('image');
                    const root = document.getElementById('report_root');
                    const panel = document.getElementById('panel');
                    const panelHeading = document.getElementById('panel-heading');
                    const sliderContainer = document.getElementById('slider_container_test');
                    const sliderRow = document.getElementById('slider_row');
                    const tableCell = document.getElementById('table-cell');
                    const collapsedHead = document.getElementById('collapsed-head');
                    const sectionHeadingStyle = getComputedStyle(sectionHeading);
                    const itemStyle = getComputedStyle(item);
                    const plotStyle = getComputedStyle(plot);
                    const viewerStyle = getComputedStyle(viewer);
                    const imageStyle = getComputedStyle(image);
                    const rootStyle = getComputedStyle(root);
                    const panelStyle = getComputedStyle(panel);
                    const panelHeadingStyle = getComputedStyle(panelHeading);
                    const sliderContainerStyle = getComputedStyle(sliderContainer);
                    const sliderRowStyle = getComputedStyle(sliderRow);
                    const tableCellStyle = getComputedStyle(tableCell);
                    const collapsedHeadStyle = getComputedStyle(collapsedHead);
                    return {
                        sectionHeading: {
                            breakAfter: sectionHeadingStyle.breakAfter,
                            pageBreakAfter: sectionHeadingStyle.pageBreakAfter,
                        },
                        item: {
                            display: itemStyle.display,
                            breakInside: itemStyle.breakInside,
                        },
                        plot: {
                            display: plotStyle.display,
                            breakInside: plotStyle.breakInside,
                            pageBreakInside: plotStyle.pageBreakInside,
                        },
                        viewer: {
                            display: viewerStyle.display,
                            breakInside: viewerStyle.breakInside,
                        },
                        image: {
                            breakInside: imageStyle.breakInside,
                            pageBreakInside: imageStyle.pageBreakInside,
                        },
                        root: {
                            borderColorToken:
                                rootStyle.getPropertyValue('--adr-border-color').trim(),
                            translucentBorderColorToken:
                                rootStyle.getPropertyValue(
                                    '--adr-border-color-translucent'
                                ).trim(),
                            printColorAdjust:
                                rootStyle.getPropertyValue('print-color-adjust'),
                            webkitPrintColorAdjust:
                                rootStyle.getPropertyValue('-webkit-print-color-adjust'),
                        },
                        panel: {
                            borderTopColor: panelStyle.borderTopColor,
                        },
                        panelHeading: {
                            breakAfter: panelHeadingStyle.breakAfter,
                            pageBreakAfter: panelHeadingStyle.pageBreakAfter,
                            borderBottomColor: panelHeadingStyle.borderBottomColor,
                        },
                        sliderContainer: {
                            breakInside: sliderContainerStyle.breakInside,
                            pageBreakInside: sliderContainerStyle.pageBreakInside,
                        },
                        sliderRow: {
                            breakInside: sliderRowStyle.breakInside,
                            pageBreakInside: sliderRowStyle.pageBreakInside,
                        },
                        tableCell: {
                            borderTopColor: tableCellStyle.borderTopColor,
                            borderRightColor: tableCellStyle.borderRightColor,
                        },
                        collapsedHead: {
                            display: collapsedHeadStyle.display,
                            visibility: collapsedHeadStyle.visibility,
                            height: collapsedHeadStyle.height,
                        },
                    };
                }"""
        )
        # sync_playwright()'s context manager stops the Playwright server but does not
        # close the browser; call close() explicitly before the with-block exits.
        browser.close()

    assert computed_styles["sectionHeading"]["breakAfter"] == "avoid"
    assert computed_styles["sectionHeading"]["pageBreakAfter"] == "avoid"
    assert computed_styles["item"]["display"] == "block"
    assert computed_styles["item"]["breakInside"] == "avoid"
    assert computed_styles["plot"]["display"] == "block"
    assert computed_styles["plot"]["breakInside"] == "avoid"
    assert computed_styles["plot"]["pageBreakInside"] == "avoid"
    assert computed_styles["viewer"]["display"] == "block"
    assert computed_styles["viewer"]["breakInside"] == "avoid"
    assert computed_styles["image"]["breakInside"] == "avoid"
    assert computed_styles["image"]["pageBreakInside"] == "avoid"
    assert computed_styles["root"]["borderColorToken"] == "#adb5bd"
    assert computed_styles["root"]["translucentBorderColorToken"] == "rgba(0, 0, 0, 0.28)"
    assert computed_styles["root"]["printColorAdjust"] == "exact"
    assert computed_styles["root"]["webkitPrintColorAdjust"] == "exact"
    assert computed_styles["panel"]["borderTopColor"] == "rgba(0, 0, 0, 0.28)"
    assert computed_styles["panelHeading"]["breakAfter"] == "avoid"
    assert computed_styles["panelHeading"]["pageBreakAfter"] == "avoid"
    assert computed_styles["panelHeading"]["borderBottomColor"] == "rgba(0, 0, 0, 0.28)"
    assert computed_styles["sliderContainer"]["breakInside"] == "avoid"
    assert computed_styles["sliderContainer"]["pageBreakInside"] == "avoid"
    assert computed_styles["sliderRow"]["breakInside"] == "avoid"
    assert computed_styles["sliderRow"]["pageBreakInside"] == "avoid"
    assert computed_styles["tableCell"]["borderTopColor"] == "rgb(173, 181, 189)"
    assert computed_styles["tableCell"]["borderRightColor"] == "rgb(173, 181, 189)"
    assert computed_styles["collapsedHead"]["display"] == "none"
    assert computed_styles["collapsedHead"]["visibility"] == "hidden"


@pytest.mark.unit
def test_pdf_length_to_px_supports_documented_pdf_units(tmp_path):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Units</p></body></html>")

    assert renderer._pdf_length_to_px("25.4mm") == pytest.approx(96.0)
    assert renderer._pdf_length_to_px("1in") == pytest.approx(96.0)
    assert renderer._pdf_length_to_px("96px") == pytest.approx(96.0)


@pytest.mark.unit
@pytest.mark.parametrize(
    "value, expected_error",
    [
        ("calc(10px + 1in)", "Unsupported PDF length"),
        ("1em", "Unsupported PDF length unit"),
        ("72pt", "Unsupported PDF length unit"),
    ],
)
def test_pdf_length_to_px_rejects_undocumented_or_malformed_units(tmp_path, value, expected_error):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Invalid units</p></body></html>")

    with pytest.raises(ADRException, match=expected_error):
        renderer._pdf_length_to_px(value)


@pytest.mark.unit
def test_evaluate_ready_step_rejects_expired_deadline_without_browser_call(tmp_path):
    logger = Mock()
    renderer = PlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body><p>Deadline</p></body></html>"),
        logger=logger,
    )
    page = Mock()

    with pytest.raises(ADRException, match="Expired step timed out"):
        renderer._evaluate_ready_step(
            page,
            step_name="Expired step",
            wait_script="() => Promise.resolve()",
            deadline=0.0,
        )

    page.evaluate.assert_not_called()
    logger.debug.assert_called_once_with(
        "Browser render readiness step failed before browser evaluation "
        "because the shared render budget was exhausted: Expired step"
    )


@pytest.mark.unit
def test_evaluate_ready_step_logs_duration_on_success(tmp_path, monkeypatch):
    logger = Mock()
    renderer = PlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Ready</body></html>"), logger=logger
    )
    page = Mock()
    monotonic_values = iter([100.0, 100.1, 100.35])
    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))

    renderer._evaluate_ready_step(
        page,
        step_name="Test step",
        wait_script="() => Promise.resolve()",
        deadline=101.0,
    )

    page.evaluate.assert_called_once()
    logger.debug.assert_called_once_with(
        "Browser render readiness step completed in 250.0 ms: Test step"
    )


@pytest.mark.unit
def test_evaluate_ready_step_logs_duration_on_failure(tmp_path, monkeypatch):
    logger = Mock()
    renderer = PlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Ready</body></html>"),
        logger=logger,
    )
    page = Mock()
    page.evaluate.side_effect = RuntimeError("step boom")
    monotonic_values = iter([200.0, 200.2, 200.45])
    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(RuntimeError, match="step boom"):
        renderer._evaluate_ready_step(
            page,
            step_name="Broken step",
            wait_script="() => Promise.resolve()",
            deadline=201.0,
        )

    logger.debug.assert_called_once_with(
        "Browser render readiness step failed in 250.0 ms: Broken step"
    )


@pytest.mark.unit
def test_evaluate_ready_step_normalizes_in_page_timeout_message(tmp_path):
    renderer = PlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Ready</body></html>"),
        render_timeout=5.0,
    )
    page = Mock()
    page.evaluate.return_value = {"__adrTimedOut": True}

    with pytest.raises(
        ADRException,
        match=r"Browser PDF rendering failed: Plotly charts timed out after 5\.0s",
    ):
        renderer._evaluate_ready_step(
            page,
            step_name="Plotly charts",
            wait_script="() => Promise.resolve()",
            deadline=999.0,
        )


@pytest.mark.unit
def test_wait_for_render_ready_matches_print_pdf_step_set(tmp_path, monkeypatch):
    """Verify all readiness steps are executed in the expected order."""
    renderer = _simple_renderer(tmp_path, "<html><body><p>Steps</p></body></html>")
    step_names = []

    def capture_ready_step(page, step_name, wait_script, deadline):
        step_names.append(step_name)

    monkeypatch.setattr(renderer, "_evaluate_ready_step", capture_ready_step)

    renderer._wait_for_render_ready(Mock(), deadline=0.0)

    assert step_names == [
        "FOUC gate",
        "FOUC transition",
        "Web fonts",
        "MathJax",
        "Plotly charts",
        "Images",
        "Videos",
        "Double requestAnimationFrame",
    ]


def _capture_ready_step_scripts(
    monkeypatch: pytest.MonkeyPatch, renderer: PlaywrightPDFRenderer
) -> dict[str, str]:
    """Capture the JavaScript readiness script for each named step."""
    wait_scripts: dict[str, str] = {}

    def capture_ready_step(page, step_name, wait_script, deadline):
        wait_scripts[step_name] = wait_script

    monkeypatch.setattr(renderer, "_evaluate_ready_step", capture_ready_step)
    renderer._wait_for_render_ready(Mock(), deadline=0.0)
    return wait_scripts


def _start_wait_script(page, wait_script: str) -> None:
    """Run one readiness step script on the page and expose its eventual result."""
    page.evaluate(
        f"""() => {{
            window.waitReadyDone = false;
            window.waitReadyError = null;
            const waitForReady = {wait_script};
            waitForReady()
                .then(() => {{
                    window.waitReadyDone = true;
                }})
                .catch((error) => {{
                    window.waitReadyError = String(error);
                }});
        }}"""
    )


@pytest.mark.unit
def test_wait_for_render_ready_fouc_gate_fast_passes_without_report_root(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>No report root</p></body></html>")
    wait_scripts = _capture_ready_step_scripts(monkeypatch, renderer)
    report_dir = tmp_path / "fouc-gate-no-root-report"
    report_dir.mkdir()
    _write_html(report_dir, "<html><body><p>No report root</p></body></html>")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_wait_script(page, wait_scripts["FOUC gate"])
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_fouc_gate_waits_for_body_loaded_class(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>FOUC gate</p></body></html>")
    wait_scripts = _capture_ready_step_scripts(monkeypatch, renderer)
    report_dir = tmp_path / "fouc-gate-loaded-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        "<html><body><section id='report_root'>Report</section></body></html>",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_wait_script(page, wait_scripts["FOUC gate"])

        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate("() => document.body.classList.add('loaded')")
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_fouc_transition_waits_for_opacity_transition(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>FOUC transition</p></body></html>")
    wait_scripts = _capture_ready_step_scripts(monkeypatch, renderer)
    report_dir = tmp_path / "fouc-transition-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        """<html><body>
        <section id="report_root" style="opacity: 0; transition: opacity 0.4s linear;">Report</section>
        </body></html>""",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_wait_script(page, wait_scripts["FOUC transition"])

        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate(
            """() => {
                const root = document.getElementById('report_root');
                root.style.opacity = '1';
                root.dispatchEvent(new TransitionEvent('transitionend', { propertyName: 'opacity' }));
            }"""
        )
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_plotly_step_waits_for_loaded_class_and_hidden_loader(
    tmp_path, monkeypatch
):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Plotly</p></body></html>")
    wait_scripts = _capture_ready_step_scripts(monkeypatch, renderer)
    report_dir = tmp_path / "plotly-ready-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        """<html><body>
        <adr-data-item>
            <section class='nexus-plot' id='plot'></section>
            <section class='adr-spinner-loader-container' id='loader'></section>
        </adr-data-item>
        </body></html>""",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_wait_script(page, wait_scripts["Plotly charts"])

        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate("() => document.getElementById('plot').classList.add('loaded')")
        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate("() => document.getElementById('loader').style.display = 'none'")
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_images_step_does_not_fast_pass_srcless_images(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Images</p></body></html>")
    wait_scripts = _capture_ready_step_scripts(monkeypatch, renderer)
    image_wait_script = wait_scripts["Images"]

    report_dir = tmp_path / "delayed-image-report"
    report_dir.mkdir()
    _write_html(report_dir, "<html><body><img id='delayed' alt='preview' /></body></html>")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_wait_script(page, image_wait_script)

        # Browsers report src-less images as complete, so the regression is that the
        # readiness step must still wait for a real source/load instead of resolving now.
        assert page.evaluate("() => document.getElementById('delayed').complete") is True
        assert page.evaluate("() => window.waitReadyDone") is False
        assert page.evaluate("() => window.waitReadyError") is None

        page.evaluate(
            """() => {
                document.getElementById('delayed').src =
                    'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';
            }"""
        )
        page.wait_for_function("() => window.waitReadyDone === true")
        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_images_step_waits_for_visible_companion_canvas(
    tmp_path, monkeypatch
):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Images</p></body></html>")
    wait_scripts = _capture_ready_step_scripts(monkeypatch, renderer)
    image_wait_script = wait_scripts["Images"]

    report_dir = tmp_path / "canvas-backed-image-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        """<html><body>
        <img
            id="enhanced"
            src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
            alt="preview"
        />
        <canvas id="enhanced_canvas" style="visibility: hidden;"></canvas>
        </body></html>""",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_wait_script(page, image_wait_script)

        # ADR slider/deep-image views can keep a completed <img> source around while the
        # visible companion canvas is still hidden during async TIFF/enhanced-image work.
        assert page.evaluate("() => document.getElementById('enhanced').complete") is True
        assert page.evaluate("() => window.waitReadyDone") is False
        assert page.evaluate("() => window.waitReadyError") is None

        page.evaluate(
            """() => {
                const canvas = document.getElementById('enhanced_canvas');
                canvas.style.visibility = 'visible';
                canvas.style.display = 'inline';
            }"""
        )
        page.wait_for_function("() => window.waitReadyDone === true")
        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_videos_step_waits_for_loadeddata(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Videos</p></body></html>")
    wait_scripts = _capture_ready_step_scripts(monkeypatch, renderer)
    report_dir = tmp_path / "video-ready-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        """<html><body>
        <video id="delayed-video"></video>
        <script>
            window.videoReadyState = 0;
            Object.defineProperty(document.getElementById('delayed-video'), 'readyState', {
                configurable: true,
                get() { return window.videoReadyState; }
            });
        </script>
        </body></html>""",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_wait_script(page, wait_scripts["Videos"])

        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate(
            """() => {
                window.videoReadyState = 2;
                document.getElementById('delayed-video').dispatchEvent(new Event('loadeddata'));
            }"""
        )
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_double_request_animation_frame_resolves(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Animation frame</p></body></html>")
    wait_scripts = _capture_ready_step_scripts(monkeypatch, renderer)
    report_dir = tmp_path / "double-raf-report"
    report_dir.mkdir()
    _write_html(report_dir, "<html><body><p>Animation frame</p></body></html>")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_wait_script(page, wait_scripts["Double requestAnimationFrame"])

        # The double-RAF step can resolve within the first repaint cycle on fast runners, so
        # assert only the observable contract that it eventually resolves without an error.
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_renderer_normalizes_relative_html_dir(tmp_path, monkeypatch):
    report_dir = tmp_path / "relative-report"
    report_dir.mkdir()
    html_dir = _write_html(report_dir, "<html><body>Relative</body></html>")
    monkeypatch.chdir(tmp_path)

    renderer = PlaywrightPDFRenderer(html_dir=html_dir.name)

    assert renderer._html_dir == html_dir.resolve()
    assert renderer._resolve_entrypoint_path() == (html_dir / "index.html").resolve()


@pytest.mark.unit
def test_renderer_requires_html_dir_for_offline_entrypoint_resolution():
    renderer = PlaywrightPDFRenderer(html_dir=None)

    with pytest.raises(ADRException, match="HTML directory is not configured"):
        renderer._resolve_entrypoint_path()


@pytest.mark.unit
def test_resolve_entrypoint_path_rejects_parent_traversal(tmp_path):
    html_dir = _write_html(tmp_path, "<html><body>Traversal</body></html>")
    renderer = PlaywrightPDFRenderer(html_dir=html_dir, filename="../../etc/passwd")

    # Entry-point validation must reject filenames that escape the exported HTML bundle.
    with pytest.raises(ADRException, match="entry-point file must be inside"):
        renderer._resolve_entrypoint_path()


@pytest.mark.unit
def test_compute_pdf_width_uses_configured_margins(tmp_path, monkeypatch):
    renderer = PlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Margins</body></html>"),
        margins={"top": "10mm", "right": "2in", "bottom": "10mm", "left": "1in"},
    )
    monkeypatch.setattr(renderer, "_measure_content_width_px", lambda page: 100.0)
    monkeypatch.setattr(renderer, "_measure_layout_width_px", lambda page: 200.0)

    # The width uses the larger layout width plus the caller-provided left/right margins.
    assert renderer._compute_pdf_width(Mock()) == "488.00px"


@pytest.mark.unit
@pytest.mark.parametrize(
    "url, should_block",
    [
        ("https://example.com/asset.js", True),
        ("http://example.com/image.png", True),
        ("//example.com/asset.js", True),
        ("file://example.com/asset.js", True),
        ("file:///tmp/report/index.html", False),
        ("data:image/gif;base64,AAAA", False),
        ("blob:null/1234", False),
    ],
)
def test_block_external_requests_keeps_browser_export_offline(tmp_path, url, should_block):
    renderer = PlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Requests</body></html>")
    )
    context = Mock()

    renderer._block_external_requests(context)

    pattern, route_handler = context.route.call_args.args
    route = Mock()
    route.request.url = url
    route_handler(route)

    assert pattern == "**/*"
    context.route_web_socket.assert_called_once()
    if should_block:
        route.abort.assert_called_once_with()
        route.continue_.assert_not_called()
    else:
        route.continue_.assert_called_once_with()
        route.abort.assert_not_called()


@pytest.mark.unit
def test_block_file_urls_with_authority_component():
    renderer = PlaywrightPDFRenderer(html_dir=Path("."))
    context = Mock()
    renderer._block_external_requests(context)
    _, route_handler = context.route.call_args.args

    for url in ("file://example.com/path", "file://example.com:8080/path"):
        route = Mock()
        route.request.url = url
        route_handler(route)
        route.abort.assert_called_once_with()
        route.continue_.assert_not_called()

    route = Mock()
    route.request.url = "file:///path/to/local/file"
    route_handler(route)
    route.continue_.assert_called_once_with()
    route.abort.assert_not_called()


@pytest.mark.unit
def test_block_external_websockets_keeps_browser_export_offline(tmp_path):
    renderer = PlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>WebSockets</body></html>")
    )
    context = Mock()

    renderer._block_external_requests(context)

    predicate, websocket_handler = context.route_web_socket.call_args.args
    assert predicate("ws://example.com/socket") is True
    assert predicate("wss://example.com/socket") is True
    assert predicate("file:///tmp/report/index.html") is False

    websocket_route = Mock()
    websocket_handler(websocket_route)

    websocket_route.close.assert_called_once_with()


@pytest.mark.unit
@pytest.mark.parametrize(
    "kwargs, expected_error",
    [
        ({"render_timeout": 0}, "render_timeout must be a positive number"),
        ({"render_timeout": "abc"}, "render_timeout must be a positive number"),
        ({"render_timeout": None}, "render_timeout must be a positive number"),
        ({"render_timeout": []}, "render_timeout must be a positive number"),
        ({"margins": {"top": "10mm"}}, "margins must contain exactly"),
        (
            {
                "margins": {
                    "top": "10mm",
                    "right": "10mm",
                    "bottom": "10mm",
                    "left": "10mm",
                    "extra": "5mm",
                }
            },
            "margins must contain exactly",
        ),
        (
            {
                "margins": {
                    "top": "1em",
                    "right": "10mm",
                    "bottom": "10mm",
                    "left": "10mm",
                }
            },
            "Unsupported PDF length unit",
        ),
    ],
)
def test_renderer_constructor_rejects_invalid_options(tmp_path, kwargs, expected_error):
    html_dir = _write_html(tmp_path, "<html><body>Invalid options</body></html>")

    with pytest.raises(ADRException, match=expected_error):
        PlaywrightPDFRenderer(html_dir=html_dir, **kwargs)


@pytest.mark.unit
def test_playwright_pdf_uses_product_browser_binary_when_user_env_is_unset(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Shared binary</p></body></html>")
    browser_binary_dir = tmp_path / "playwright-browsers"
    browser_binary_dir.mkdir()
    renderer = PlaywrightPDFRenderer(
        html_dir=html_dir,
        ansys_installation=r"C:\Program Files\ANSYS Inc\v271\ADR",
        ansys_version=271,
    )
    env_seen: dict[str, str | None] = {}
    page = Mock()
    page.pdf.return_value = b"%PDF-mock"
    context = Mock()
    context.new_page.return_value = page
    browser = Mock()
    browser.new_context.return_value = context
    playwright = Mock()
    playwright.chromium.launch.return_value = browser
    playwright_manager = MagicMock()
    preserved_download_host = "https://playwright-downloads.example.invalid"
    runtime_override_envs = {
        env_var: f"{env_var.lower()}-value"
        for env_var in PlaywrightPDFRenderer._TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS
    }

    def fake_enter():
        # Playwright resolves the browser registry when the driver starts, so the
        # environment must already be pointing at the shipped binary by this point.
        env_seen["playwright_browsers_path"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        env_seen["transient_override_envs"] = {
            env_var: os.environ.get(env_var) for env_var in runtime_override_envs
        }
        env_seen["download_host"] = os.environ.get("PLAYWRIGHT_DOWNLOAD_HOST")
        return playwright

    playwright_manager.__enter__.side_effect = fake_enter
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("PLAYWRIGHT_DOWNLOAD_HOST", preserved_download_host)
    for env_var, env_value in runtime_override_envs.items():
        monkeypatch.setenv(env_var, env_value)
    monkeypatch.setattr(
        pdf_renderer_module,
        "resolve_playwright_browser_binary_info",
        lambda ansys_installation=None, ansys_version=None: _browser_binary_info(
            browser_binary_dir
        ),
    )
    monkeypatch.setattr(pdf_renderer_module, "sync_playwright", lambda: playwright_manager)
    # render_pdf() calls _wait_for_render_ready(page, deadline=...); the stub must accept the
    # keyword-only deadline or the call raises TypeError and the render is reported as failed.
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)
    monkeypatch.setattr(renderer, "_compute_pdf_width", lambda page: None)

    assert renderer.render_pdf() == b"%PDF-mock"
    assert env_seen["playwright_browsers_path"] == str(browser_binary_dir)
    assert all(value is None for value in env_seen["transient_override_envs"].values())
    assert env_seen["download_host"] == preserved_download_host
    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ
    assert os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] == preserved_download_host
    for env_var, env_value in runtime_override_envs.items():
        assert os.environ[env_var] == env_value


@pytest.mark.unit
def test_playwright_pdf_overrides_user_browser_path_env_with_product_binary(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>User browser path</p></body></html>")
    renderer = PlaywrightPDFRenderer(
        html_dir=html_dir,
        ansys_installation=r"C:\Program Files\ANSYS Inc\v271\ADR",
        ansys_version=271,
    )
    user_browser_path = str(tmp_path / "user-browser-path")
    browser_binary_dir = tmp_path / "product-browser-path"
    env_seen: dict[str, str | None] = {}
    resolver_args: dict[str, object] = {}
    page = Mock()
    page.pdf.return_value = b"%PDF-mock"
    context = Mock()
    context.new_page.return_value = page
    browser = Mock()
    browser.new_context.return_value = context
    playwright = Mock()
    playwright.chromium.launch.return_value = browser
    playwright_manager = MagicMock()
    runtime_override_envs = {
        env_var: f"{env_var.lower()}-value"
        for env_var in PlaywrightPDFRenderer._TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS
    }

    def fake_enter():
        # Browser-PDF must force the product-shipped browser cache during the
        # render even if the ambient environment points somewhere else.
        env_seen["playwright_browsers_path"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        env_seen["transient_override_envs"] = {
            env_var: os.environ.get(env_var) for env_var in runtime_override_envs
        }
        return playwright

    playwright_manager.__enter__.side_effect = fake_enter
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", user_browser_path)
    for env_var, env_value in runtime_override_envs.items():
        monkeypatch.setenv(env_var, env_value)
    monkeypatch.setattr(
        pdf_renderer_module,
        "resolve_playwright_browser_binary_info",
        lambda ansys_installation=None, ansys_version=None: resolver_args.update(
            {
                "ansys_installation": ansys_installation,
                "ansys_version": ansys_version,
            }
        )
        or _browser_binary_info(browser_binary_dir),
    )
    monkeypatch.setattr(pdf_renderer_module, "sync_playwright", lambda: playwright_manager)
    # render_pdf() calls _wait_for_render_ready(page, deadline=...); the stub must accept the
    # keyword-only deadline or the call raises TypeError and the render is reported as failed.
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)
    monkeypatch.setattr(renderer, "_compute_pdf_width", lambda page: None)

    assert renderer.render_pdf() == b"%PDF-mock"
    assert env_seen["playwright_browsers_path"] == str(browser_binary_dir)
    assert all(value is None for value in env_seen["transient_override_envs"].values())
    assert resolver_args == {
        "ansys_installation": r"C:\Program Files\ANSYS Inc\v271\ADR",
        "ansys_version": 271,
    }
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == user_browser_path
    for env_var, env_value in runtime_override_envs.items():
        assert os.environ[env_var] == env_value


@pytest.mark.unit
def test_playwright_pdf_rejects_product_line_26_before_browser_start(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Unsupported line</p></body></html>")
    renderer = PlaywrightPDFRenderer(
        html_dir=html_dir,
        ansys_installation=r"C:\Program Files\ANSYS Inc\v261\ADR",
        ansys_version=261,
    )
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "external-browser-path"))
    monkeypatch.setattr(
        pdf_renderer_module,
        "sync_playwright",
        lambda: pytest.fail("unsupported product line should not launch Playwright"),
    )

    with pytest.raises(
        ADRException,
        match="not supported for Ansys 2026 R1.*Use Ansys 2027 R1 or newer",
    ):
        renderer.render_pdf()


@pytest.mark.unit
def test_playwright_pdf_rejects_missing_product_browser_binary_before_browser_start(
    tmp_path, monkeypatch
):
    html_dir = _write_html(tmp_path, "<html><body><p>Missing binary</p></body></html>")
    renderer = PlaywrightPDFRenderer(
        html_dir=html_dir,
        ansys_installation=r"C:\Program Files\ANSYS Inc\v271\ADR",
        ansys_version=271,
    )
    monkeypatch.setattr(
        pdf_renderer_module,
        "resolve_playwright_browser_binary_info",
        lambda ansys_installation=None, ansys_version=None: None,
    )
    monkeypatch.setattr(
        pdf_renderer_module,
        "sync_playwright",
        lambda: pytest.fail("missing product browser binary should not launch Playwright"),
    )

    with pytest.raises(
        ADRException,
        match="requires a valid product-shipped Playwright browser binary",
    ):
        renderer.render_pdf()


@pytest.mark.unit
def test_browser_pdf_product_line_returns_none_for_invalid_install_version(tmp_path):
    renderer = PlaywrightPDFRenderer(html_dir=tmp_path, ansys_version=270)

    assert renderer._browser_pdf_product_line() is None


@pytest.mark.unit
def test_playwright_pdf_surfaces_playwright_launch_error_for_product_browser_binary(
    tmp_path, monkeypatch
):
    html_dir = _write_html(tmp_path, "<html><body><p>Launch failure</p></body></html>")
    browser_binary_dir = tmp_path / "playwright-browsers"
    browser_binary_dir.mkdir()
    renderer = PlaywrightPDFRenderer(
        html_dir=html_dir,
        ansys_installation=r"C:\Program Files\ANSYS Inc\v271\ADR",
        ansys_version=271,
    )
    user_browser_path = str(tmp_path / "user-browser-path")
    env_seen: dict[str, str | None] = {}
    playwright = Mock()
    playwright.chromium.launch.side_effect = RuntimeError("missing product browser revision")
    playwright_manager = MagicMock()

    def fake_enter():
        env_seen["playwright_browsers_path"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        return playwright

    playwright_manager.__enter__.side_effect = fake_enter
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", user_browser_path)
    monkeypatch.setattr(
        pdf_renderer_module,
        "resolve_playwright_browser_binary_info",
        lambda ansys_installation=None, ansys_version=None: _browser_binary_info(
            browser_binary_dir
        ),
    )
    monkeypatch.setattr(pdf_renderer_module, "sync_playwright", lambda: playwright_manager)

    with pytest.raises(
        ADRException, match="Browser PDF rendering failed: missing product browser revision"
    ) as exc_info:
        renderer.render_pdf()
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert env_seen["playwright_browsers_path"] == str(browser_binary_dir)
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == user_browser_path
