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

from pathlib import Path
from unittest.mock import Mock

import pytest

from ansys.dynamicreporting.core.exceptions import ADRException
from ansys.dynamicreporting.core.serverless.pdf_renderer import PlaywrightPDFRenderer


def _write_html(tmp_path: Path, body: str) -> Path:
    """Write a minimal HTML file for renderer tests and return its directory."""
    html_path = tmp_path / "index.html"
    html_path.write_text(body, encoding="utf-8")
    return tmp_path


def _render_or_skip(renderer: PlaywrightPDFRenderer) -> bytes:
    """Render a PDF unless Playwright's Chromium binary is unavailable locally."""
    pytest.importorskip("playwright.sync_api")

    try:
        return renderer.render_pdf()
    except ADRException as exc:
        error_text = str(exc)
        if "Executable doesn't exist" in error_text or "playwright install chromium" in error_text:
            pytest.skip("Playwright Chromium is not installed in this environment.")
        raise


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


@pytest.mark.unit
def test_playwright_pdf_from_simple_html(tmp_path):
    renderer = _simple_renderer(tmp_path, "<html><body><h1>Hello</h1></body></html>")
    pdf_bytes = _render_or_skip(renderer)
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_landscape(tmp_path):
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Landscape content</p></body></html>",
        landscape=True,
    )
    pdf_bytes = _render_or_skip(renderer)
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_validates_missing_entrypoint_before_browser_start(tmp_path):
    renderer = PlaywrightPDFRenderer(html_dir=tmp_path)

    with pytest.raises(ADRException, match="entry-point file does not exist"):
        renderer.render_pdf()


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
    pdf_bytes = _render_or_skip(renderer)
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_skips_datatables_wait_without_init_handlers(tmp_path):
    # Print-mode browser exports can include DataTables assets and table IDs while intentionally
    # skipping DataTables initialization. The readiness gate must treat those tables as complete
    # instead of waiting forever for an init.dt event that will never be bound.
    html = """
    <html>
    <body class="loaded">
        <section id="report_root" style="opacity:1">
            <table id="table_example"><tbody><tr><td>Cell</td></tr></tbody></table>
        </section>
        <script>
            window.$ = function() {
                return {
                    on: function() {}
                };
            };
            window.$.fn = {
                DataTable: {
                    isDataTable: function() {
                        return false;
                    }
                }
            };
            window.$._data = function() {
                return {};
            };
        </script>
    </body>
    </html>
    """
    renderer = _simple_renderer(tmp_path, html)
    pdf_bytes = _render_or_skip(renderer)
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
    pytest.importorskip("playwright.sync_api")

    try:
        renderer.render_pdf()
    except ADRException as exc:
        error_text = str(exc)
        if "Executable doesn't exist" in error_text or "playwright install chromium" in error_text:
            pytest.skip("Playwright Chromium is not installed in this environment.")
        assert "Browser PDF rendering failed" in error_text
        assert "timed out" in error_text
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
    assert "img.img-fluid" in css
    assert "video.img-fluid" in css
    assert ".ansys-nexus-proxy" in css
    assert "h2:has(+ section.adr-container)" in css
    assert "header:has(+ section.adr-panel-body)" in css
    assert 'table.table-fit-head > thead[style*="visibility: collapse"]' in css
    assert "display: block !important;" in css
    assert "@media print" not in css
    assert "[nexus_template]" not in css


@pytest.mark.unit
def test_apply_pdf_capture_styles_take_effect_under_screen_media(tmp_path):
    html = """
    <html>
    <body>
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
            <table class="table table-fit-head" id="kv-table">
                <thead id="collapsed-head" style="visibility: collapse;">
                    <tr>
                        <th></th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <th>Application</th>
                        <td>Fluent</td>
                    </tr>
                </tbody>
            </table>
        </adr-data-item>
        </section>
        <header class="adr-panel-header" id="panel-heading">
            <h2>System Information</h2>
        </header>
        <section class="adr-panel-body" id="panel-body">
            <p>Panel content</p>
        </section>
    </body>
    </html>
    """
    renderer = _simple_renderer(tmp_path, html)
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    try:
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
                    const panelHeading = document.getElementById('panel-heading');
                    const collapsedHead = document.getElementById('collapsed-head');
                    const sectionHeadingStyle = getComputedStyle(sectionHeading);
                    const itemStyle = getComputedStyle(item);
                    const plotStyle = getComputedStyle(plot);
                    const viewerStyle = getComputedStyle(viewer);
                    const imageStyle = getComputedStyle(image);
                    const panelHeadingStyle = getComputedStyle(panelHeading);
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
                        panelHeading: {
                            breakAfter: panelHeadingStyle.breakAfter,
                            pageBreakAfter: panelHeadingStyle.pageBreakAfter,
                        },
                        collapsedHead: {
                            display: collapsedHeadStyle.display,
                            visibility: collapsedHeadStyle.visibility,
                            height: collapsedHeadStyle.height,
                        },
                    };
                }"""
            )
            browser.close()
    except Exception as exc:
        error_text = str(exc)
        if "Executable doesn't exist" in error_text or "playwright install chromium" in error_text:
            pytest.skip("Playwright Chromium is not installed in this environment.")
        raise

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
    assert computed_styles["panelHeading"]["breakAfter"] == "avoid"
    assert computed_styles["panelHeading"]["pageBreakAfter"] == "avoid"
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
    renderer = _simple_renderer(tmp_path, "<html><body><p>Deadline</p></body></html>")
    page = Mock()

    with pytest.raises(ADRException, match="Expired step timed out"):
        renderer._evaluate_ready_step(
            page,
            step_name="Expired step",
            wait_script="() => Promise.resolve()",
            deadline=0.0,
        )

    page.evaluate.assert_not_called()


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
        ({"margins": {"top": "10mm"}}, "margins must contain exactly"),
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
