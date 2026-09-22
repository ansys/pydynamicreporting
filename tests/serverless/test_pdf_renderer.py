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
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pypdf import PdfReader

import ansys.dynamicreporting.core.utils.pdf_renderer as pdf_renderer_module
from ansys.dynamicreporting.core import DEFAULT_ANSYS_VERSION, PDFPageSize, common_utils
from ansys.dynamicreporting.core.common_utils import resolve_install_info
from ansys.dynamicreporting.core.exceptions import ADRException
from ansys.dynamicreporting.core.utils._browser_pdf import browser_pdf_invocation_script
from ansys.dynamicreporting.core.utils._browser_pdf import browser_pdf_runtime_script
from ansys.dynamicreporting.core.utils.pdf_renderer import _ReportURLPlaywrightPDFRenderer
from ansys.dynamicreporting.core.utils.pdf_renderer import _OfflinePlaywrightPDFRenderer

_EXPECTED_TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS = ("PLAYWRIGHT_HOST_PLATFORM_OVERRIDE",)
_PACKAGED_BROWSER_DIR_NAME = "packaged-browser-dir"
_STUBBED_BROWSER_DIR = Path("mock-product-browser")
_OVERSIZED_PLOT_HTML = """
<html>
<head>
    <style>
        body { margin: 0; }
        adr-data-item, section { display: block; }
        .nexus-plot { display: block; width: 320px; height: 1400px; }
    </style>
</head>
<body>
    <main id="report_root">
        <div data-layout-type="basic">
            <h2>Async Plotly resize</h2>
            <section class="adr-container">
                <adr-data-item data-item-type="table">
                    <section id="plot" class="nexus-plot loaded"></section>
                </adr-data-item>
            </section>
        </div>
    </main>
</body>
</html>
"""


def _fake_ansys_installation(version: int) -> str:
    """Return a synthetic install path for the requested test install version."""
    return rf"C:\Program Files\ANSYS Inc\v{version}\ADR"


def _browser_metadata_kwargs(ansys_version: int | None = None) -> dict[str, object]:
    """Return synthetic product-browser metadata for renderer tests."""
    resolved_version = int(DEFAULT_ANSYS_VERSION) if ansys_version is None else ansys_version
    return {
        "ansys_installation": _fake_ansys_installation(resolved_version),
        "ansys_version": resolved_version,
    }


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
    margins: dict[str, str] | None = None,
    page_size: PDFPageSize | None = PDFPageSize.A3,
    width: str | float | None = None,
    height: str | float | None = None,
    render_timeout: float | None = None,
    ansys_installation: str | None = None,
    ansys_version: int | None = None,
) -> _OfflinePlaywrightPDFRenderer:
    """Create a renderer for a temporary HTML document with test-controlled options."""
    html_dir = _write_html(tmp_path, body)
    resolved_version = int(DEFAULT_ANSYS_VERSION) if ansys_version is None else ansys_version
    resolved_installation = (
        _fake_ansys_installation(resolved_version)
        if ansys_installation is None
        else ansys_installation
    )
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=html_dir,
        landscape=landscape,
        margins=margins,
        page_size=page_size,
        width=width,
        height=height,
        render_timeout=(
            _OfflinePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT
            if render_timeout is None
            else render_timeout
        ),
        ansys_installation=resolved_installation,
        ansys_version=resolved_version,
    )
    return renderer


@dataclass(frozen=True)
class MockPlaywrightPDFFlow:
    """The mocked Playwright PDF object graph that ``render_pdf`` walks."""

    manager: MagicMock
    playwright: Mock
    browser: Mock
    context: Mock
    page: Mock

    def sync_playwright(self):
        """Return the mocked context manager used by ``sync_playwright()``."""
        # ``render_pdf()`` calls ``sync_playwright()`` as a factory, so expose the manager directly.
        return self.manager


def _mock_playwright_pdf_flow(
    *,
    pdf_bytes: bytes = b"%PDF-mock",
    launch_side_effect: Exception | None = None,
) -> MockPlaywrightPDFFlow:
    """Create the mocked Playwright PDF flow used by renderer tests."""
    page = Mock()
    # Pagination helpers share one page.evaluate mock. Return every result key
    # consumed by logging so render-pipeline tests can focus on their own phase.
    page.evaluate.return_value = {
        "__adrTimedOut": False,
        "cappedVisualCount": 0,
        "resizedVisuals": [],
        "keptLayouts": [],
        "keptPanels": [],
        "breakableSliders": [],
        "breakableItems": [],
        "widthPx": 0.0,
        "source": "mock page",
    }
    page.pdf.return_value = pdf_bytes
    context = Mock()
    context.new_page.return_value = page
    browser = Mock()
    browser.new_context.return_value = context
    playwright = Mock()
    if launch_side_effect is None:
        playwright.chromium.launch.return_value = browser
    else:
        playwright.chromium.launch.side_effect = launch_side_effect
    playwright_manager = MagicMock()
    playwright_manager.__enter__.return_value = playwright

    return MockPlaywrightPDFFlow(
        manager=playwright_manager,
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
    )


@dataclass(frozen=True)
class _ProductPlaywrightContext:
    """Resolved product install metadata for this module's real-browser tests."""

    ansys_installation: str
    ansys_version: int
    playwright_browsers_path: str


@pytest.fixture(scope="module")
def product_playwright_context(request, pytestconfig) -> _ProductPlaywrightContext:
    """Return a product browser path that matches the host platform running this test module."""

    # Priority 1: explicit install path when --use-local-launcher is active.
    if pytestconfig.getoption("use_local_launcher"):
        explicit_resolution = resolve_install_info(
            ansys_installation=pytestconfig.getoption("install_path")
        )
        if explicit_resolution.install_dir is not None:
            binary_info = pdf_renderer_module.resolve_playwright_browser_binary_info(
                ansys_installation=explicit_resolution.install_dir,
                ansys_version=explicit_resolution.version,
            )
            if binary_info is not None:
                return _ProductPlaywrightContext(
                    ansys_installation=explicit_resolution.install_dir,
                    ansys_version=explicit_resolution.version,
                    playwright_browsers_path=str(binary_info.path),
                )

    # Priority 2: live ADR server fixture.
    adr_init = request.getfixturevalue("adr_init")
    binary_info = pdf_renderer_module.resolve_playwright_browser_binary_info(
        ansys_installation=adr_init.ansys_installation,
        ansys_version=adr_init.ansys_version,
    )
    if binary_info is not None:
        return _ProductPlaywrightContext(
            ansys_installation=adr_init.ansys_installation,
            ansys_version=adr_init.ansys_version,
            playwright_browsers_path=str(binary_info.path),
        )

    # Priority 3: auto-detected local product install.
    local_resolution = resolve_install_info()
    if local_resolution.install_dir is not None:
        binary_info = pdf_renderer_module.resolve_playwright_browser_binary_info(
            ansys_installation=local_resolution.install_dir,
            ansys_version=local_resolution.version,
        )
        if binary_info is not None:
            return _ProductPlaywrightContext(
                ansys_installation=local_resolution.install_dir,
                ansys_version=local_resolution.version,
                playwright_browsers_path=str(binary_info.path),
            )

    pytest.fail(
        "Expected either the resolved ADR installation or the local product install to provide "
        "a product-shipped Playwright browser."
    )


@pytest.fixture(scope="module", autouse=True)
def _use_product_playwright_browser(product_playwright_context: _ProductPlaywrightContext):
    """Run this module's real-browser paths against the product-shipped Playwright browser."""
    restored_browser_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = product_playwright_context.playwright_browsers_path
    try:
        yield
    finally:
        if restored_browser_path is None:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        else:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = restored_browser_path


def _stub_playwright_stack(monkeypatch: pytest.MonkeyPatch) -> MockPlaywrightPDFFlow:
    """Build a fake Chromium stack and route ``sync_playwright`` to it without launching a browser."""
    flow = _mock_playwright_pdf_flow()
    # Most mocked unit tests do not exercise the product-browser discovery path directly, so
    # keep their setup focused on downstream render behavior by stubbing the resolver as well.
    monkeypatch.setattr(
        pdf_renderer_module,
        "resolve_playwright_browser_binary_info",
        lambda ansys_installation=None, ansys_version=None: _browser_binary_info(
            _STUBBED_BROWSER_DIR
        ),
    )
    monkeypatch.setattr(pdf_renderer_module, "sync_playwright", flow.sync_playwright)
    return flow


def _arrange_product_browser_renderer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    launch_side_effect: Exception | None = None,
) -> tuple[_OfflinePlaywrightPDFRenderer, MockPlaywrightPDFFlow, Path]:
    """Create a renderer wired to a stubbed product browser and Playwright flow."""
    html_dir = _write_html(tmp_path, "<html><body><p>Shared binary</p></body></html>")
    browser_binary_dir = tmp_path / "playwright-browsers"
    browser_binary_dir.mkdir()
    ansys_version = int(DEFAULT_ANSYS_VERSION)
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=html_dir,
        ansys_installation=_fake_ansys_installation(ansys_version),
        ansys_version=ansys_version,
    )
    flow = _mock_playwright_pdf_flow(launch_side_effect=launch_side_effect)

    def resolve_browser_binary_info(ansys_installation=None, ansys_version=None):
        """Return the fake product browser metadata needed by most product-browser tests."""
        return _browser_binary_info(browser_binary_dir)

    monkeypatch.setattr(
        pdf_renderer_module,
        "resolve_playwright_browser_binary_info",
        resolve_browser_binary_info,
    )
    monkeypatch.setattr(pdf_renderer_module, "sync_playwright", flow.sync_playwright)
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)

    return renderer, flow, browser_binary_dir


def _capture_render_start_env(flow: MockPlaywrightPDFFlow, env_seen: dict[str, object]) -> None:
    """Capture the effective render-scope environment at Playwright startup time."""

    def fake_enter():
        """Snapshot render-scope env vars when the mocked Playwright context starts."""
        # Playwright resolves its browser registry on context-manager entry, so capture env state here.
        env_seen["playwright_browsers_path"] = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        env_seen["transient_override_envs"] = {
            env_var: os.environ.get(env_var)
            for env_var in _EXPECTED_TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS
        }
        return flow.playwright

    flow.manager.__enter__.side_effect = fake_enter


def _stub_playwright_render(
    monkeypatch: pytest.MonkeyPatch,
    renderer: _OfflinePlaywrightPDFRenderer,
) -> tuple[Mock, Mock, Mock]:
    """Stub browser preparation and return the rendered page."""
    stack = _stub_playwright_stack(monkeypatch)
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)
    monkeypatch.setattr(
        renderer,
        "_prepare_content_for_pagination",
        lambda page, deadline=None: None,
    )
    return stack.page, stack.context, stack.browser


def _browser_binary_info(
    browser_binary_dir: Path,
) -> pdf_renderer_module._PlaywrightBrowserBinaryInfo:
    """Create validated product-binary metadata for renderer tests."""
    return pdf_renderer_module._PlaywrightBrowserBinaryInfo(
        path=browser_binary_dir,
        browser_name=pdf_renderer_module._PlaywrightBrowserBinaryInfo.EXPECTED_BROWSER_NAME,
        machine_arch="win64",
        packaged_binary_dir=_PACKAGED_BROWSER_DIR_NAME,
    )


@pytest.mark.unit
def test_playwright_pdf_from_simple_html(tmp_path, product_playwright_context):
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><h1>Hello</h1></body></html>",
        ansys_installation=product_playwright_context.ansys_installation,
        ansys_version=product_playwright_context.ansys_version,
    )
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_landscape(tmp_path, product_playwright_context):
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Landscape content</p></body></html>",
        landscape=True,
        ansys_installation=product_playwright_context.ansys_installation,
        ansys_version=product_playwright_context.ansys_version,
    )
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_has_no_blank_pages(tmp_path, product_playwright_context):
    page_markers = ("PDF page one", "PDF page two", "PDF page three")
    layouts = "".join(
        f"""
        <div data-layout-type="basic">
            <br>
            <h2>{page_marker}</h2>
            <section class="adr-container">Visible report content</section>
        </div>
        """
        for page_marker in page_markers
    )
    renderer = _simple_renderer(
        tmp_path,
        f"""
        <html>
        <head>
            <style>
                * {{ box-sizing: border-box; }}
                #report_root > div[data-layout-type="basic"] {{
                    break-after: page;
                    height: 968px;
                }}
                #report_root > div[data-layout-type="basic"]:last-child {{
                    break-after: auto;
                }}
            </style>
        </head>
        <body class="loaded">
            <main id="report_root">{layouts}</main>
        </body>
        </html>
        """,
        landscape=True,
        margins={"top": "20mm", "right": "15mm", "bottom": "20mm", "left": "15mm"},
        page_size=PDFPageSize.A3,
        ansys_installation=product_playwright_context.ansys_installation,
        ansys_version=product_playwright_context.ansys_version,
    )

    reader = PdfReader(BytesIO(renderer.render_pdf()))
    page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    blank_pages = [page_number for page_number, text in enumerate(page_text, start=1) if not text]

    assert not blank_pages, f"Generated blank PDF pages: {blank_pages}"
    assert len(page_text) == len(page_markers)
    for page_number, (text, page_marker) in enumerate(zip(page_text, page_markers), start=1):
        assert page_marker in text, f"PDF page {page_number} does not contain {page_marker!r}"


@pytest.mark.unit
def test_playwright_pdf_validates_missing_entrypoint_before_browser_start(tmp_path):
    renderer = _OfflinePlaywrightPDFRenderer(html_dir=tmp_path, **_browser_metadata_kwargs())

    with pytest.raises(ADRException, match="entry-point file does not exist"):
        renderer.render_pdf()


@pytest.mark.unit
def test_offline_renderer_adds_offline_context_delta(tmp_path):
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body><p>Offline context</p></body></html>"),
        **_browser_metadata_kwargs(),
    )
    browser = Mock()

    renderer._new_browser_context(browser)

    expected_context_kwargs = renderer._shared_browser_context_kwargs()
    expected_context_kwargs["offline"] = True
    browser.new_context.assert_called_once_with(**expected_context_kwargs)


@pytest.mark.unit
def test_playwright_pdf_uses_render_timeout_for_browser_launch_and_navigation(
    tmp_path, monkeypatch
):
    html_dir = _write_html(tmp_path, "<html><body><p>Navigation timeout</p></body></html>")
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=html_dir,
        render_timeout=12.5,
        **_browser_metadata_kwargs(),
    )
    stack = _stub_playwright_stack(monkeypatch)

    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: 100.0)
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)

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
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=html_dir,
        render_timeout=0.0001,
        **_browser_metadata_kwargs(),
    )
    stack = _stub_playwright_stack(monkeypatch)

    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: 100.0)
    monkeypatch.setattr(renderer, "_wait_for_render_ready", lambda page, deadline=None: None)

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
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=html_dir,
        render_timeout=10.0,
        **_browser_metadata_kwargs(),
    )
    _stub_playwright_stack(monkeypatch)
    captured_deadline: dict[str, float] = {}
    monotonic_values = iter([100.0, 100.0, 100.0, 100.0, 101.0])

    monkeypatch.setattr(
        pdf_renderer_module,
        "monotonic",
        lambda: next(monotonic_values, 101.0),
    )

    def capture_ready(page, deadline=None):
        captured_deadline["value"] = deadline

    monkeypatch.setattr(renderer, "_wait_for_render_ready", capture_ready)

    renderer.render_pdf()

    # The readiness phase must spend from the original browser deadline instead of resetting a
    # fresh render_timeout window after navigation has already consumed part of the budget.
    assert captured_deadline["value"] == 110.0


@pytest.mark.unit
def test_playwright_pdf_normalizes_playwright_navigation_timeout(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Navigation timeout</p></body></html>")
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=html_dir,
        render_timeout=12.5,
        **_browser_metadata_kwargs(),
    )
    stack = _stub_playwright_stack(monkeypatch)
    stack.page.goto.side_effect = PlaywrightTimeoutError("Timeout 12500ms exceeded")
    monotonic_values = iter([100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0])

    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(
        ADRException,
        match=r"Browser PDF rendering failed: page navigation timed out after 12\.5s",
    ) as exc_info:
        renderer.render_pdf()

    # The surfaced error stays ADR-owned while preserving the underlying Playwright timeout.
    assert isinstance(exc_info.value.__cause__, PlaywrightTimeoutError)
    assert "12500ms exceeded" in str(exc_info.value.__cause__)
    stack.context.close.assert_called_once_with()
    stack.browser.close.assert_called_once_with()


@pytest.mark.unit
def test_playwright_pdf_closes_browser_when_new_context_creation_fails(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Context failure</p></body></html>")
    renderer = _OfflinePlaywrightPDFRenderer(html_dir=html_dir, **_browser_metadata_kwargs())
    stack = _stub_playwright_stack(monkeypatch)
    stack.browser.new_context.side_effect = RuntimeError("new context boom")

    # The caller-facing message stays generic while preserving the underlying browser failure.
    with pytest.raises(ADRException, match=r"Browser PDF rendering failed\.$") as exc_info:
        renderer.render_pdf()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert str(exc_info.value.__cause__) == "new context boom"
    stack.browser.close.assert_called_once_with()


@pytest.mark.unit
def test_live_report_url_renderer_navigates_to_report_url(monkeypatch):
    renderer = _ReportURLPlaywrightPDFRenderer(
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
        **_browser_metadata_kwargs(),
    )
    page, context, browser = _stub_playwright_render(monkeypatch, renderer)

    assert renderer.render_pdf() == b"%PDF-mock"
    page.goto.assert_called_once()
    goto_args, goto_kwargs = page.goto.call_args
    assert goto_args == (
        "http://127.0.0.1:8000/reports/report_display/?view=report-guid&print=pdf",
    )
    assert goto_kwargs["wait_until"] == "load"
    # Navigation spends from the shared browser-phase deadline, so setup work can consume a small
    # slice of the raw budget before Playwright receives the timeout value.
    assert 0 < goto_kwargs["timeout"] <= int(renderer._render_timeout * 1000)
    expected_context_kwargs = renderer._shared_browser_context_kwargs()
    browser.new_context.assert_called_once_with(**expected_context_kwargs)
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
        _ReportURLPlaywrightPDFRenderer(url="/reports/report_display/?view=report-guid")


@pytest.mark.unit
def test_live_report_url_renderer_forwards_product_browser_install_metadata():
    """The live-URL renderer forwards the Ansys install metadata used to locate the packed browser."""
    renderer = _ReportURLPlaywrightPDFRenderer(
        url="http://127.0.0.1:8000/reports/report_display/?view=report-guid&print=pdf",
        ansys_installation="/opt/ansys/v271",
        ansys_version=271,
    )

    assert renderer._ansys_installation == Path("/opt/ansys/v271").expanduser()
    assert renderer._ansys_version == 271


@pytest.mark.unit
def test_pdf_page_size_is_exported_from_common_utils():
    """Expose one enum identity and the exact Chromium format spellings."""
    assert common_utils.PDFPageSize is PDFPageSize
    assert tuple(page_size.value for page_size in PDFPageSize) == (
        "Letter",
        "Legal",
        "Tabloid",
        "Ledger",
        "A0",
        "A1",
        "A2",
        "A3",
        "A4",
        "A5",
        "A6",
    )


# Fixed formats and custom dimensions are mutually exclusive Playwright option
# shapes. These tests pin the public precedence rules as well as their values.
@pytest.mark.unit
def test_playwright_pdf_uses_a3_format_when_content_fits(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Fitting content</p></body></html>")
    page, _, _ = _stub_playwright_render(monkeypatch, renderer)

    renderer.render_pdf()

    pdf_options = page.pdf.call_args.kwargs
    assert pdf_options["format"] == PDFPageSize.A3.value
    assert pdf_options["landscape"] is False
    assert "width" not in pdf_options
    assert "height" not in pdf_options


@pytest.mark.unit
@pytest.mark.parametrize(
    "page_size",
    [
        PDFPageSize.LETTER,
        PDFPageSize.LEGAL,
        PDFPageSize.TABLOID,
        PDFPageSize.LEDGER,
        PDFPageSize.A0,
        PDFPageSize.A1,
        PDFPageSize.A2,
        PDFPageSize.A3,
        PDFPageSize.A5,
        PDFPageSize.A6,
    ],
)
def test_playwright_pdf_uses_selected_fixed_page_size(tmp_path, monkeypatch, page_size):
    # Deliberately wide content must not replace the caller-selected format with
    # a content-derived width; capture CSS owns overflow handling.
    renderer = _simple_renderer(
        tmp_path,
        '<html><body><table style="width: 12000px"><tr><td>Wide</td></tr></table></body></html>',
        page_size=page_size,
    )
    page, _, _ = _stub_playwright_render(monkeypatch, renderer)

    renderer.render_pdf()

    pdf_options = page.pdf.call_args.kwargs
    assert pdf_options["format"] == page_size.value
    assert pdf_options["landscape"] is False
    assert "width" not in pdf_options
    assert "height" not in pdf_options


@pytest.mark.unit
def test_playwright_landscape_pdf_rotates_selected_fixed_page(tmp_path, monkeypatch):
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Landscape A3</p></body></html>",
        landscape=True,
        page_size=PDFPageSize.A3,
    )
    page, _, _ = _stub_playwright_render(monkeypatch, renderer)

    renderer.render_pdf()

    pdf_options = page.pdf.call_args.kwargs
    assert pdf_options["format"] == PDFPageSize.A3.value
    assert pdf_options["landscape"] is True
    assert "width" not in pdf_options
    assert "height" not in pdf_options


@pytest.mark.unit
def test_playwright_pdf_uses_custom_dimensions_when_page_size_is_none(tmp_path, monkeypatch):
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Custom dimensions</p></body></html>",
        page_size=None,
        width="12in",
        height=1728.0,
    )
    page, _, _ = _stub_playwright_render(monkeypatch, renderer)

    renderer.render_pdf()

    pdf_options = page.pdf.call_args.kwargs
    assert pdf_options["width"] == "12in"
    assert pdf_options["height"] == 1728.0
    assert pdf_options["landscape"] is False
    assert "format" not in pdf_options


@pytest.mark.unit
def test_playwright_pdf_fixed_format_overrides_custom_dimensions(tmp_path, monkeypatch):
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Fixed format wins</p></body></html>",
        page_size=PDFPageSize.LEDGER,
        width="1px",
        height="1px",
    )
    page, _, _ = _stub_playwright_render(monkeypatch, renderer)

    renderer.render_pdf()

    pdf_options = page.pdf.call_args.kwargs
    assert pdf_options["format"] == PDFPageSize.LEDGER.value
    assert "width" not in pdf_options
    assert "height" not in pdf_options


@pytest.mark.unit
def test_playwright_pdf_uses_a3_when_all_sizing_is_omitted(tmp_path, monkeypatch):
    # ``page_size=None`` is also the custom-size switch. With no complete custom
    # pair, it falls back to A3 instead of producing no size.
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Default dimensions</p></body></html>",
        page_size=None,
    )
    page, _, _ = _stub_playwright_render(monkeypatch, renderer)

    renderer.render_pdf()

    assert page.pdf.call_args.kwargs["format"] == PDFPageSize.A3.value


@pytest.mark.unit
@pytest.mark.parametrize(
    "page_size, landscape, expected_width",
    [
        (PDFPageSize.LETTER, False, 740),
        (PDFPageSize.LETTER, True, 980),
        (PDFPageSize.LEGAL, False, 740),
        (PDFPageSize.LEGAL, True, 1268),
        (PDFPageSize.TABLOID, False, 980),
        (PDFPageSize.TABLOID, True, 1556),
        (PDFPageSize.LEDGER, False, 1556),
        (PDFPageSize.LEDGER, True, 980),
        (PDFPageSize.A0, False, 3102),
        (PDFPageSize.A0, True, 4417),
        (PDFPageSize.A1, False, 2170),
        (PDFPageSize.A1, True, 3102),
        (PDFPageSize.A2, False, 1512),
        (PDFPageSize.A2, True, 2170),
        (PDFPageSize.A3, False, 1047),
        (PDFPageSize.A3, True, 1512),
        (PDFPageSize.A4, False, 718),
        (PDFPageSize.A4, True, 1047),
        (PDFPageSize.A5, False, 484),
        (PDFPageSize.A5, True, 718),
        (PDFPageSize.A6, False, 320),
        (PDFPageSize.A6, True, 484),
    ],
)
def test_browser_context_uses_selected_printable_width(
    tmp_path, page_size, landscape, expected_width
):
    # Expected values are portrait/landscape physical widths converted to CSS
    # pixels, minus both default margins, then floored for a valid viewport.
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Responsive content</p></body></html>",
        landscape=landscape,
        page_size=page_size,
    )

    context_options = renderer._shared_browser_context_kwargs()

    assert context_options["viewport"]["width"] == expected_width
    assert context_options["viewport"]["height"] == renderer._DEFAULT_BROWSER_VIEWPORT_HEIGHT


@pytest.mark.unit
@pytest.mark.parametrize("landscape, expected_width", [(False, 1076), (True, 1652)])
def test_browser_context_uses_custom_printable_width(tmp_path, landscape, expected_width):
    # Orientation swaps the custom physical dimensions before margin subtraction.
    renderer = _simple_renderer(
        tmp_path,
        "<html><body><p>Custom responsive width</p></body></html>",
        landscape=landscape,
        page_size=None,
        width="12in",
        height="18in",
    )

    assert renderer._shared_browser_context_kwargs()["viewport"]["width"] == expected_width


@pytest.mark.unit
def test_playwright_pdf_prepares_pagination_before_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Ordering</p></body></html>")
    page, _, _ = _stub_playwright_render(monkeypatch, renderer)
    call_order: list[str] = []
    phase_deadlines: dict[str, float | None] = {}

    def capture_ready(_observed_page: Mock, deadline: float | None = None) -> None:
        phase_deadlines["ready"] = deadline
        call_order.append("ready")

    def capture_helpers(_observed_page: Mock, *, deadline: float | None = None) -> None:
        phase_deadlines["helpers"] = deadline
        call_order.append("helpers")

    def capture_styles(_observed_page: Mock, *, deadline: float | None = None) -> None:
        phase_deadlines["styles"] = deadline
        call_order.append("styles")

    def capture_pagination(_observed_page: Mock, deadline: float | None = None) -> None:
        phase_deadlines["pagination"] = deadline
        call_order.append("pagination")

    # Install the packaged helper runtime in the loaded document before readiness uses it.
    # Capture styles then establish print geometry, and pagination mutates that final geometry.
    monkeypatch.setattr(renderer, "_install_browser_pdf_helpers", capture_helpers)
    monkeypatch.setattr(renderer, "_wait_for_render_ready", capture_ready)
    monkeypatch.setattr(renderer, "_apply_pdf_capture_styles", capture_styles)
    monkeypatch.setattr(renderer, "_prepare_content_for_pagination", capture_pagination)

    renderer.render_pdf()

    assert call_order == ["helpers", "ready", "styles", "pagination"]
    assert phase_deadlines["helpers"] is not None
    assert phase_deadlines["ready"] is not None
    assert phase_deadlines["ready"] == phase_deadlines["helpers"]
    assert phase_deadlines["styles"] == phase_deadlines["ready"]
    assert phase_deadlines["pagination"] == phase_deadlines["ready"]
    page.pdf.assert_called_once()


@pytest.mark.unit
def test_playwright_pdf_with_mathjax_content(tmp_path, product_playwright_context):
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
    renderer = _simple_renderer(
        tmp_path,
        html,
        ansys_installation=product_playwright_context.ansys_installation,
        ansys_version=product_playwright_context.ansys_version,
    )
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_waits_for_mathjax_document_when_ready_api(
    tmp_path, product_playwright_context
):
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
    renderer = _simple_renderer(
        tmp_path,
        html,
        ansys_installation=product_playwright_context.ansys_installation,
        ansys_version=product_playwright_context.ansys_version,
    )
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_waits_for_mathjax_hub_queue_api(tmp_path, product_playwright_context):
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
    renderer = _simple_renderer(
        tmp_path,
        html,
        ansys_installation=product_playwright_context.ansys_installation,
        ansys_version=product_playwright_context.ansys_version,
    )
    pdf_bytes = renderer.render_pdf()
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.unit
def test_playwright_pdf_signal_timeout(tmp_path, product_playwright_context):
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
    renderer = _simple_renderer(
        tmp_path,
        html,
        render_timeout=0.5,
        ansys_installation=product_playwright_context.ansys_installation,
        ansys_version=product_playwright_context.ansys_version,
    )

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
def test_browser_pdf_runtime_loads_packaged_modules_once() -> None:
    first_runtime = browser_pdf_runtime_script()
    second_runtime = browser_pdf_runtime_script()

    # The joined runtime must preserve dependency order: bootstrap creates the namespace,
    # readiness registers steps, and the remaining modules add callable operations.
    assert first_runtime is second_runtime
    assert first_runtime.index("registerReadyStep") < first_runtime.index("foucGate")
    assert first_runtime.index("foucGate") < first_runtime.index("applyPanelCaptureStyles")
    assert first_runtime.index("applyPanelCaptureStyles") < first_runtime.index(
        "fitVisualsForPagination"
    )
    assert "setPaginationCohesion" in first_runtime
    assert "makeOversizedStructuresFragmentable" in first_runtime
    assert "__ansysDynamicReportingBrowserPdf" in browser_pdf_invocation_script()


@pytest.mark.unit
def test_install_browser_pdf_helpers_spends_deadline_and_evaluates_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Runtime</p></body></html>")
    page = Mock()
    checkpoints: list[tuple[float, str]] = []

    def capture_remaining_timeout(deadline: float, phase_name: str) -> int:
        checkpoints.append((deadline, phase_name))
        return 100

    monkeypatch.setattr(
        renderer,
        "_remaining_browser_phase_timeout_ms",
        capture_remaining_timeout,
    )

    renderer._install_browser_pdf_helpers(page, deadline=123.0)

    assert checkpoints == [(123.0, "browser PDF helper installation")] * 2
    page.evaluate.assert_called_once_with(browser_pdf_runtime_script())


@pytest.mark.unit
def test_browser_pdf_helper_invocation_uses_packaged_bridge(tmp_path: Path) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Bridge</p></body></html>")
    page = Mock()
    page.evaluate.return_value = {"value": "done"}

    result = renderer._evaluate_browser_pdf_helper(page, "exampleMethod", {"value": 3})

    assert result == {"value": "done"}
    page.evaluate.assert_called_once_with(
        browser_pdf_invocation_script(),
        {"method": "exampleMethod", "argument": {"value": 3}},
    )


@pytest.mark.unit
def test_browser_pdf_bridge_rejects_invalid_dispatch_in_browser(tmp_path: Path) -> None:
    """Exercise bridge and readiness-registry failures in Chromium."""
    renderer = _simple_renderer(tmp_path, "<html><body><p>Bridge errors</p></body></html>")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((renderer._html_dir / renderer._ENTRYPOINT_FILENAME).as_uri())

        with pytest.raises(
            PlaywrightError,
            match="The browser PDF runtime has not been installed on this page",
        ):
            renderer._evaluate_browser_pdf_helper(page, "applyPanelCaptureStyles")

        renderer._install_browser_pdf_helpers(page)
        with pytest.raises(
            PlaywrightError,
            match="Unknown browser PDF runtime method: missingMethod",
        ):
            renderer._evaluate_browser_pdf_helper(page, "missingMethod")
        with pytest.raises(
            PlaywrightError,
            match="Unknown browser PDF readiness step: missingStep",
        ):
            renderer._evaluate_browser_pdf_helper(
                page,
                "waitForReadyStep",
                {"stepKey": "missingStep", "timeoutMs": 1000},
            )
        browser.close()


@pytest.mark.unit
def test_plotly_resize_pending_promise_respects_browser_timeout(tmp_path: Path) -> None:
    """Return the timeout sentinel when Plotly never settles its resize promise."""
    renderer = _simple_renderer(tmp_path, _OVERSIZED_PLOT_HTML, page_size=PDFPageSize.A4)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=renderer._shared_browser_context_kwargs()["viewport"])
        page.goto((renderer._html_dir / renderer._ENTRYPOINT_FILENAME).as_uri())
        renderer._install_browser_pdf_helpers(page)
        page.evaluate(
            """() => {
                window.__plotlyResizeCount = 0;
                window.Plotly = {
                    Plots: {
                        resize: () => {
                            window.__plotlyResizeCount += 1;
                            return new Promise(() => {});
                        },
                    },
                };
            }"""
        )

        result = renderer._fit_visuals_for_pagination(
            page,
            renderer._printable_page_height_px(),
            timeout_ms=50,
        )
        resize_count = page.evaluate("() => window.__plotlyResizeCount")
        browser.close()

    assert result == {"__adrTimedOut": True}
    assert resize_count == 1


@pytest.mark.unit
def test_plotly_resize_rejection_propagates_from_browser(tmp_path: Path) -> None:
    """Propagate a rejected asynchronous Plotly resize promise to Python."""
    renderer = _simple_renderer(tmp_path, _OVERSIZED_PLOT_HTML, page_size=PDFPageSize.A4)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=renderer._shared_browser_context_kwargs()["viewport"])
        page.goto((renderer._html_dir / renderer._ENTRYPOINT_FILENAME).as_uri())
        renderer._install_browser_pdf_helpers(page)
        page.evaluate(
            """() => {
                window.Plotly = {
                    Plots: {
                        resize: () => Promise.reject(
                            new Error('resize rejection regression probe')
                        ),
                    },
                };
            }"""
        )

        with pytest.raises(PlaywrightError, match="resize rejection regression probe"):
            renderer._fit_visuals_for_pagination(
                page,
                renderer._printable_page_height_px(),
                timeout_ms=1000,
            )
        browser.close()


@pytest.mark.unit
def test_apply_pdf_capture_styles_targets_plot_containers(tmp_path: Path) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>CSS injection</p></body></html>")
    page = Mock()

    renderer._apply_pdf_capture_styles(page)

    # Capture styles are injected in separate global and panel-layout blocks;
    # inspect the combined contract rather than relying on call order.
    css = "\n".join(call.kwargs["content"] for call in page.add_style_tag.call_args_list)
    assert "adr-data-item" in css
    assert ".nexus-plot" in css
    assert ".avz-viewer" in css
    assert "ansys-adr-viewer" in css
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
    assert "overflow-x: clip !important;" in css
    assert "display: block !important;" in css
    assert "@media print" not in css
    assert "[nexus_template]" not in css


@pytest.mark.unit
def test_apply_pdf_capture_styles_spends_shared_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>CSS deadline</p></body></html>")
    page = Mock()
    checkpoints: list[tuple[float, str]] = []

    def capture_remaining_timeout(deadline: float, phase_name: str) -> int:
        checkpoints.append((deadline, phase_name))
        return 100

    monkeypatch.setattr(
        renderer,
        "_remaining_browser_phase_timeout_ms",
        capture_remaining_timeout,
    )

    renderer._apply_pdf_capture_styles(page, deadline=123.0)

    # Styling checks the same shared deadline before starting and after each of its three
    # browser operations, so none of that preparation can silently escape render_timeout.
    assert checkpoints == [(123.0, "PDF capture styling")] * 4


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
            <ansys-nexus-viewer id="viewer"></ansys-nexus-viewer>
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
        page.goto(
            (renderer._html_dir / renderer._ENTRYPOINT_FILENAME).as_uri(),
            wait_until="load",
        )
        # The PDF renderer uses screen media so the captured PDF matches the browser layout.
        # The anti-splitting rules must still apply in that media mode or Plotly figures can
        # break across pages during PDF pagination.
        page.emulate_media(media="screen")
        renderer._install_browser_pdf_helpers(page)
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
                    // Chromium may use either root element as the scrolling box;
                    // both must clip horizontal overflow before PDF generation.
                    const documentStyle = getComputedStyle(document.documentElement);
                    const bodyStyle = getComputedStyle(document.body);
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
                        document: {
                            htmlOverflowX: documentStyle.overflowX,
                            bodyOverflowX: bodyStyle.overflowX,
                        },
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
                            overflow: viewerStyle.overflow,
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

    # Root clipping prevents Chromium from scaling all report content to fit a
    # single over-width descendant.
    assert computed_styles["document"]["htmlOverflowX"] == "clip"
    assert computed_styles["document"]["bodyOverflowX"] == "clip"
    # Cohesion rules keep headings and indivisible visuals with their content.
    assert computed_styles["sectionHeading"]["breakAfter"] == "avoid"
    assert computed_styles["sectionHeading"]["pageBreakAfter"] == "avoid"
    assert computed_styles["item"]["display"] == "block"
    assert computed_styles["item"]["breakInside"] == "avoid"
    assert computed_styles["plot"]["display"] == "block"
    assert computed_styles["plot"]["breakInside"] == "avoid"
    assert computed_styles["plot"]["pageBreakInside"] == "avoid"
    assert computed_styles["viewer"]["display"] == "block"
    assert computed_styles["viewer"]["breakInside"] == "avoid"
    assert computed_styles["viewer"]["overflow"] == "hidden"
    assert computed_styles["image"]["breakInside"] == "avoid"
    assert computed_styles["image"]["pageBreakInside"] == "avoid"
    # PDF capture overrides border tokens at the report root so descendants
    # inherit printable contrast without selector-by-selector color patches.
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
@pytest.mark.parametrize("landscape", [False, True])
def test_prepare_content_for_pagination_handles_core_media_and_fragmentation(tmp_path, landscape):
    """Exercise visual fitting, layout cohesion, and oversized fragmentation together."""
    html = """
    <html>
    <head>
        <style>
            * {
                box-sizing: border-box;
            }
            body {
                margin: 0;
            }
            adr-panel,
            adr-slider-template,
            adr-data-item,
            ansys-adr-viewer,
            ansys-nexus-viewer,
            section,
            img,
            video,
            canvas {
                display: block;
            }
            div[data-layout-type] {
                padding: 4px;
            }
            .oversized-visual {
                height: 1400px;
                width: 320px;
            }
            .scene-visual {
                height: 720px;
                width: 960px;
            }
            .multi-media {
                display: flex;
                gap: 8px;
            }
            .multi-media img {
                height: 100px;
                width: 120px;
            }
            #responsive-image {
                height: 120px;
                width: 100%;
            }
        </style>
        <script>
            customElements.define('adr-panel', class extends HTMLElement {
                connectedCallback() {
                    if (this.shadowRoot) {
                        return;
                    }
                    const shadowRoot = this.attachShadow({mode: 'open'});
                    shadowRoot.innerHTML = `
                        <style>
                            :host, section { display: block; }
                            header { height: 40px; }
                            section.adr-panel-body { padding: 0 20px 4px; }
                        </style>
                        <section class="adr-panel">
                            <header class="adr-panel-header">${this.dataset.title}</header>
                            <section class="adr-panel-body"><slot></slot></section>
                        </section>
                    `;
                }
            });
            window.__plotlyResizeCount = 0;
            window.Plotly = {
                Plots: {
                    resize: () => {
                        window.__plotlyResizeCount += 1;
                    }
                }
            };
        </script>
    </head>
    <body>
        <main id="report_root">
            <div id="explicit-layout" data-layout-type="basic">
                <h2>Explicit image</h2>
                <section class="adr-container">
                    <adr-data-item data-item-type="image">
                        <img
                            id="explicit-image"
                            class="oversized-visual"
                            alt="explicit"
                            src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
                        />
                    </adr-data-item>
                </section>
            </div>
            <div data-layout-type="basic">
                <h2>Slider video</h2>
                <section class="adr-container">
                    <adr-slider-template id="video-slider" data-guid="video-slider">
                        <section id="slider_container_video">
                            <section class="adr-row">
                                <video id="slider-video" class="oversized-visual"></video>
                            </section>
                        </section>
                    </adr-slider-template>
                </section>
            </div>
            <div data-layout-type="basic">
                <h2>Canvas</h2>
                <section class="adr-container">
                    <adr-data-item data-item-type="image">
                        <canvas id="canvas" class="oversized-visual"></canvas>
                    </adr-data-item>
                </section>
            </div>
            <div data-layout-type="basic">
                <h2>Plot</h2>
                <section class="adr-container">
                    <adr-data-item data-item-type="table">
                        <section id="plot" class="nexus-plot oversized-visual loaded">
                            <canvas id="plot-canvas"></canvas>
                        </section>
                    </adr-data-item>
                </section>
            </div>
            <div id="scene-panel-layout" data-layout-type="panel">
                <adr-panel data-title="Scene panel">
                    <div data-layout-type="basic">
                        <h2>Scene</h2>
                        <section class="adr-container">
                            <adr-data-item id="viewer-item" data-item-type="scene">
                                <div id="viewer-wrapper" class="scene-visual">
                                    <ansys-adr-viewer id="viewer" aspect_ratio="1.333333">
                                    </ansys-adr-viewer>
                                </div>
                            </adr-data-item>
                        </section>
                    </div>
                </adr-panel>
            </div>
            <div data-layout-type="basic">
                <h2>Direct scene</h2>
                <section class="adr-container">
                    <adr-data-item id="direct-viewer-item" data-item-type="scene">
                        <ansys-nexus-viewer
                            id="direct-viewer"
                            class="scene-visual"
                            aspect_ratio="1.333333"
                        ></ansys-nexus-viewer>
                    </adr-data-item>
                </section>
            </div>
            <div data-layout-type="basic">
                <h2>Multiple media</h2>
                <section class="adr-container">
                    <adr-data-item class="multi-media" data-item-type="image">
                        <img
                            id="multi-image-a"
                            alt="first"
                            src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
                        />
                        <img
                            id="multi-image-b"
                            alt="second"
                            src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
                        />
                    </adr-data-item>
                </section>
            </div>
            <div data-layout-type="basic">
                <h2>Responsive image</h2>
                <section class="adr-container">
                    <adr-data-item data-item-type="image">
                        <img
                            id="responsive-image"
                            alt="responsive"
                            src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
                        />
                    </adr-data-item>
                </section>
            </div>
            <img
                id="hidden-image"
                alt="hidden"
                src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
                style="display: none"
            />
            <div id="fitting-panel-layout" data-layout-type="panel">
                <adr-panel data-title="Fitting panel">
                    <adr-data-item style="height: 120px" data-item-type="table">
                        Fitting table
                    </adr-data-item>
                </adr-panel>
            </div>
            <div id="oversized-panel-layout" data-layout-type="panel">
                <adr-panel data-title="Oversized panel">
                    <adr-data-item style="height: 1400px" data-item-type="table">
                        Oversized panel table
                    </adr-data-item>
                </adr-panel>
            </div>
            <adr-slider-template id="oversized-slider" data-guid="oversized-slider">
                <section id="slider_container_oversized" style="height: 1400px">
                    <section id="oversized-slider-row" class="adr-row" style="height: 1400px">
                        Oversized slider content
                    </section>
                </section>
            </adr-slider-template>
            <div id="oversized-layout" data-layout-type="basic">
                <h2>Oversized table</h2>
                <section class="adr-container">
                    <adr-data-item id="oversized-item" data-item-type="table">
                        <div class="table-responsive" style="height: 1400px">
                            <table id="oversized-table"><tbody><tr><td>Value</td></tr></tbody></table>
                        </div>
                    </adr-data-item>
                </section>
            </div>
        </main>
    </body>
    </html>
    """
    # Pin A4 so the 1,400 px fixtures remain taller than the printable page.
    renderer = _simple_renderer(tmp_path, html, landscape=landscape, page_size=PDFPageSize.A4)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport=renderer._shared_browser_context_kwargs()["viewport"])
        page.goto((renderer._html_dir / renderer._ENTRYPOINT_FILENAME).as_uri(), wait_until="load")
        page.emulate_media(media="screen")

        renderer._install_browser_pdf_helpers(page)
        renderer._apply_pdf_capture_styles(page)
        renderer._prepare_content_for_pagination(page)
        state = page.evaluate(
            """async () => {
                const inlineState = id => {
                    const element = document.getElementById(id);
                    return {
                        breakInside: element.style.getPropertyValue('break-inside'),
                        breakPriority: element.style.getPropertyPriority('break-inside'),
                        height: element.style.getPropertyValue('height'),
                        maxHeight: element.style.getPropertyValue('max-height'),
                        maxHeightPriority: element.style.getPropertyPriority('max-height'),
                        maxWidth: element.style.getPropertyValue('max-width'),
                        maxWidthPriority: element.style.getPropertyPriority('max-width'),
                        width: element.style.getPropertyValue('width'),
                        aspectRatio: element.style.getPropertyValue('aspect-ratio'),
                        display: element.style.getPropertyValue('display'),
                        overflow: element.style.getPropertyValue('overflow'),
                    };
                };
                const fittingPanel = document.querySelector(
                    '#fitting-panel-layout > adr-panel'
                );
                const responsiveImage = document.getElementById('responsive-image');
                const responsiveWidthCap = Number.parseFloat(
                    responsiveImage.style.getPropertyValue('max-width')
                );
                const viewerWrapper = document.getElementById('viewer-wrapper');
                const directViewer = document.getElementById('direct-viewer');
                const fitsPanelBody = visual => {
                    const panelBody = visual.closest('adr-panel').shadowRoot.querySelector(
                        'section.adr-panel-body'
                    );
                    const panelBodyRect = panelBody.getBoundingClientRect();
                    const panelBodyStyle = getComputedStyle(panelBody);
                    const contentLeft = panelBodyRect.left
                        + Number.parseFloat(panelBodyStyle.paddingLeft);
                    const contentRight = panelBodyRect.right
                        - Number.parseFloat(panelBodyStyle.paddingRight);
                    const visualRect = visual.getBoundingClientRect();
                    return visualRect.left >= contentLeft - 0.5
                        && visualRect.right <= contentRight + 0.5;
                };
                const fitsContainer = visual => {
                    const visualRect = visual.getBoundingClientRect();
                    const containerRect = visual.closest(
                        'section.adr-container'
                    ).getBoundingClientRect();
                    return visualRect.left >= containerRect.left - 0.5
                        && visualRect.right <= containerRect.right + 0.5;
                };
                const viewerWrapperFitsPanelBody = fitsPanelBody(viewerWrapper);
                const directViewerFitsContainer = fitsContainer(directViewer);
                // Widen the ancestor after fitting to prove each visual received
                // a stable inline cap rather than relying on transient layout width.
                document.getElementById('report_root').style.width = '5000px';
                await new Promise(resolve => requestAnimationFrame(
                    () => requestAnimationFrame(resolve)
                ));
                return {
                    explicitImage: inlineState('explicit-image'),
                    explicitLayout: inlineState('explicit-layout'),
                    sliderVideo: inlineState('slider-video'),
                    canvas: inlineState('canvas'),
                    plot: inlineState('plot'),
                    viewerWrapper: inlineState('viewer-wrapper'),
                    viewer: inlineState('viewer'),
                    viewerItem: inlineState('viewer-item'),
                    viewerWrapperFitsPanelBody,
                    viewerWrapperWidth: viewerWrapper.getBoundingClientRect().width,
                    directViewer: inlineState('direct-viewer'),
                    directViewerItem: inlineState('direct-viewer-item'),
                    directViewerFitsContainer,
                    directViewerWidth: directViewer.getBoundingClientRect().width,
                    multiImageA: inlineState('multi-image-a'),
                    multiImageB: inlineState('multi-image-b'),
                    responsiveImage: inlineState('responsive-image'),
                    responsiveImageWidth: responsiveImage.getBoundingClientRect().width,
                    responsiveWidthCap,
                    hiddenImage: inlineState('hidden-image'),
                    fittingPanel: inlineState('fitting-panel-layout'),
                    oversizedPanel: inlineState('oversized-panel-layout'),
                    oversizedSlider: inlineState('slider_container_oversized'),
                    oversizedSliderRow: inlineState('oversized-slider-row'),
                    oversizedLayout: inlineState('oversized-layout'),
                    oversizedItem: inlineState('oversized-item'),
                    oversizedTable: inlineState('oversized-table'),
                    panelPaginationStyle: Boolean(
                        fittingPanel.shadowRoot.querySelector(
                            'style[data-adr-pdf-pagination]'
                        )
                    ),
                    panelHeaderBreakAfter: getComputedStyle(
                        fittingPanel.shadowRoot.querySelector('header.adr-panel-header')
                    ).breakAfter,
                    plotlyResizeCount: window.__plotlyResizeCount,
                };
            }"""
        )
        browser.close()

    # Every visible indivisible visual receives explicit page-height and
    # observed-width caps, regardless of its owning ADR component.
    for visual_name in (
        "explicitImage",
        "sliderVideo",
        "canvas",
        "plot",
        "viewerWrapper",
        "directViewer",
    ):
        visual = state[visual_name]
        assert visual["maxHeight"].endswith("px")
        assert 0 < float(visual["maxHeight"][:-2]) <= renderer._printable_page_height_px()
        assert visual["maxHeightPriority"] == "important"
        assert visual["maxWidth"].endswith("px")
        assert visual["maxWidthPriority"] == "important"

    # Native replaced media preserve aspect ratio through auto dimensions;
    # plots and scene viewers use their component-specific resize paths below.
    for replaced_visual_name in ("explicitImage", "sliderVideo", "canvas"):
        assert state[replaced_visual_name]["height"] == "auto"
        assert state[replaced_visual_name]["width"] == "auto"

    # Scene wrappers stay inside their owning content boxes while both current
    # and compatibility tags retain the component dimensions they require.
    assert state["plot"]["height"].endswith("px")
    assert state["viewerWrapper"]["aspectRatio"]
    assert state["viewerWrapper"]["display"] == "block"
    assert state["viewerWrapper"]["overflow"] == "hidden"
    assert state["viewerWrapperWidth"] <= 960
    assert state["viewerWrapperFitsPanelBody"] is True
    assert state["viewer"]["height"] == "100%"
    assert state["viewer"]["width"] == "100%"
    assert state["viewer"]["overflow"] == "hidden"
    if state["viewerItem"]["height"]:
        assert state["viewerItem"]["height"] == state["viewerWrapper"]["height"]
    assert state["directViewer"]["aspectRatio"]
    assert state["directViewer"]["display"] == "block"
    assert state["directViewer"]["overflow"] == "hidden"
    assert state["directViewerWidth"] <= 960
    assert state["directViewerFitsContainer"] is True
    if state["directViewerItem"]["height"]:
        assert state["directViewerItem"]["height"] == state["directViewer"]["height"]
    # Hidden visuals remain untouched, while every visible visual is capped
    # independently, including multiple media in one item.
    assert state["hiddenImage"]["maxWidth"] == ""
    assert state["multiImageA"]["maxWidth"].endswith("px")
    assert state["multiImageB"]["maxWidth"].endswith("px")
    assert state["responsiveImage"]["maxWidth"].endswith("px")
    assert state["responsiveImageWidth"] <= state["responsiveWidthCap"] + 0.5
    # Fitting groups stay cohesive; structures taller than a page are released
    # so Chromium can fragment them instead of clipping or leaving blank pages.
    assert state["explicitLayout"]["breakInside"] == "avoid"
    assert state["fittingPanel"]["breakInside"] == "avoid"
    assert state["fittingPanel"]["breakPriority"] == "important"
    assert state["oversizedPanel"]["breakInside"] == "auto"
    assert state["oversizedSlider"]["breakInside"] == "auto"
    assert state["oversizedSliderRow"]["breakInside"] == "auto"
    assert state["oversizedLayout"]["breakInside"] == "auto"
    assert state["oversizedItem"]["breakInside"] == "auto"
    assert state["oversizedTable"]["breakInside"] == "auto"
    assert state["panelPaginationStyle"] is True
    assert state["panelHeaderBreakAfter"] == "avoid"
    assert state["plotlyResizeCount"] == 1


@pytest.mark.unit
def test_pdf_length_to_px_supports_documented_pdf_units(tmp_path):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Units</p></body></html>")

    # Strings follow CSS absolute-unit conversion; numeric values already mean
    # CSS pixels and therefore pass through unchanged.
    assert renderer._pdf_length_to_px("25.4mm") == pytest.approx(96.0)
    assert renderer._pdf_length_to_px("1in") == pytest.approx(96.0)
    assert renderer._pdf_length_to_px("96px") == pytest.approx(96.0)
    assert renderer._pdf_length_to_px(96.0) == pytest.approx(96.0)


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
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body><p>Deadline</p></body></html>"),
        logger=logger,
        **_browser_metadata_kwargs(),
    )
    page = Mock()

    with pytest.raises(ADRException, match="Expired step timed out"):
        renderer._evaluate_ready_step(
            page,
            step_name="Expired step",
            step_key="expiredStep",
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
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Ready</body></html>"),
        logger=logger,
        **_browser_metadata_kwargs(),
    )
    page = Mock()
    monotonic_values = iter([100.0, 100.1, 100.35])
    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))

    renderer._evaluate_ready_step(
        page,
        step_name="Test step",
        step_key="testStep",
        deadline=101.0,
    )

    page.evaluate.assert_called_once()
    logger.debug.assert_called_once_with(
        "Browser render readiness step completed in 250.0 ms: Test step"
    )


@pytest.mark.unit
def test_evaluate_ready_step_logs_duration_on_failure(tmp_path, monkeypatch):
    logger = Mock()
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Ready</body></html>"),
        logger=logger,
        **_browser_metadata_kwargs(),
    )
    page = Mock()
    page.evaluate.side_effect = RuntimeError("step boom")
    monotonic_values = iter([200.0, 200.2, 200.45])
    monkeypatch.setattr(pdf_renderer_module, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(RuntimeError, match="step boom"):
        renderer._evaluate_ready_step(
            page,
            step_name="Broken step",
            step_key="brokenStep",
            deadline=201.0,
        )

    logger.debug.assert_called_once_with(
        "Browser render readiness step failed in 250.0 ms: Broken step"
    )


@pytest.mark.unit
def test_evaluate_ready_step_normalizes_in_page_timeout_message(tmp_path):
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Ready</body></html>"),
        render_timeout=5.0,
        **_browser_metadata_kwargs(),
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
            step_key="plotlyCharts",
            deadline=999.0,
        )


@pytest.mark.unit
def test_wait_for_render_ready_matches_print_pdf_step_set(tmp_path, monkeypatch):
    """Verify all readiness steps are executed in the expected order."""
    renderer = _simple_renderer(tmp_path, "<html><body><p>Steps</p></body></html>")
    step_names = []

    def capture_ready_step(page, step_name, step_key, deadline):
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


def _start_ready_step(renderer: _OfflinePlaywrightPDFRenderer, page, step_name: str) -> None:
    """Start one packaged readiness step and expose its eventual result to the test page."""
    step_keys = dict(renderer._READINESS_STEPS)
    renderer._install_browser_pdf_helpers(page)
    page.evaluate(
        """(stepKey) => {
            window.waitReadyDone = false;
            window.waitReadyError = null;
            globalThis.__ansysDynamicReportingBrowserPdf.waitForReadyStep({
                stepKey,
                timeoutMs: 10000,
            })
                .then((result) => {
                    if (result.__adrTimedOut) {
                        throw new Error('Readiness step timed out in its browser test.');
                    }
                    window.waitReadyDone = true;
                })
                .catch((error) => {
                    window.waitReadyError = String(error);
                });
        }""",
        step_keys[step_name],
    )


@pytest.mark.unit
def test_wait_for_render_ready_fouc_gate_fast_passes_without_report_root(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>No report root</p></body></html>")
    report_dir = tmp_path / "fouc-gate-no-root-report"
    report_dir.mkdir()
    _write_html(report_dir, "<html><body><p>No report root</p></body></html>")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_ready_step(renderer, page, "FOUC gate")
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_fouc_gate_waits_for_body_loaded_class(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>FOUC gate</p></body></html>")
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

        _start_ready_step(renderer, page, "FOUC gate")

        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate("() => document.body.classList.add('loaded')")
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_fouc_transition_waits_for_opacity_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>FOUC transition</p></body></html>")
    report_dir = tmp_path / "fouc-transition-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        """<html><body>
        <section id="report_root" style="opacity: 0; transition: opacity 0.4s linear;">
            Report<span id="child">Child</span>
        </section>
        </body></html>""",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_ready_step(renderer, page, "FOUC transition")

        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate(
            """() => {
                document.getElementById('child').dispatchEvent(
                    new TransitionEvent('transitionend', {
                        propertyName: 'opacity',
                        bubbles: true
                    })
                );
            }"""
        )
        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate(
            """() => {
                document.getElementById('report_root').dispatchEvent(
                    new TransitionEvent('transitionend', { propertyName: 'opacity' })
                );
            }"""
        )
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Plotly</p></body></html>")
    report_dir = tmp_path / "plotly-ready-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        """<html><body>
        <adr-data-item>
            <section class='nexus-plot' id='plot'>
                <div
                    class='plot-container'
                    id='plot-container'
                    style='opacity: 0; transition: opacity 0.4s linear;'
                ></div>
            </section>
            <section class='adr-spinner-loader-container' id='loader'></section>
        </adr-data-item>
        </body></html>""",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_ready_step(renderer, page, "Plotly charts")

        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate("() => document.getElementById('plot').classList.add('loaded')")
        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate("() => document.getElementById('loader').style.display = 'none'")
        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate(
            """() => {
                const container = document.getElementById('plot-container');
                container.style.opacity = '1';
                container.dispatchEvent(
                    new TransitionEvent('transitionend', { propertyName: 'opacity' })
                );
            }"""
        )
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_plotly_step_observes_late_plot_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Late Plotly container</p></body></html>")
    report_dir = tmp_path / "late-plotly-container-report"
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

        _start_ready_step(renderer, page, "Plotly charts")

        assert page.evaluate("() => window.waitReadyDone") is False
        page.evaluate(
            """() => {
                const plot = document.getElementById('plot');
                const container = document.createElement('div');
                container.className = 'plot-container';
                container.style.opacity = '0';
                plot.appendChild(container);

                plot.classList.add('loaded');
                document.getElementById('loader').style.display = 'none';
                container.style.opacity = '1';
                container.dispatchEvent(
                    new TransitionEvent('transitionend', {
                        propertyName: 'opacity',
                        bubbles: true
                    })
                );
            }"""
        )
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_images_step_does_not_fast_pass_srcless_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Images</p></body></html>")

    report_dir = tmp_path / "delayed-image-report"
    report_dir.mkdir()
    _write_html(report_dir, "<html><body><img id='delayed' alt='preview' /></body></html>")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_ready_step(renderer, page, "Images")

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
def test_wait_for_render_ready_images_step_accepts_already_failed_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Failed image</p></body></html>")
    report_dir = tmp_path / "failed-image-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        "<html><body><img id='failed' src='data:image/png;base64,not-valid' /></body></html>",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        # The load failure occurred before readiness listeners are installed. A sourced image
        # with complete=true and no decoded width must fast-pass instead of awaiting a lost event.
        assert page.evaluate("() => document.getElementById('failed').complete") is True
        assert page.evaluate("() => document.getElementById('failed').naturalWidth") == 0

        _start_ready_step(renderer, page, "Images")
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_images_step_waits_for_visible_companion_canvas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Images</p></body></html>")

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

        _start_ready_step(renderer, page, "Images")

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
def test_wait_for_render_ready_videos_step_waits_for_loadeddata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Videos</p></body></html>")
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

        _start_ready_step(renderer, page, "Videos")

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
def test_wait_for_render_ready_videos_step_accepts_already_failed_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Failed video</p></body></html>")
    report_dir = tmp_path / "failed-video-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        """<html><body>
        <video id="failed-video"></video>
        <script>
            const video = document.getElementById('failed-video');
            Object.defineProperty(video, 'readyState', {
                configurable: true,
                get() { return 0; }
            });
            Object.defineProperty(video, 'error', {
                configurable: true,
                get() { return { code: 4 }; }
            });
        </script>
        </body></html>""",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_ready_step(renderer, page, "Videos")
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_videos_step_settles_each_video_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    renderer = _simple_renderer(tmp_path, "<html><body><p>Two videos</p></body></html>")
    report_dir = tmp_path / "two-video-report"
    report_dir.mkdir()
    _write_html(
        report_dir,
        """<html><body>
        <video id="first-video"></video>
        <video id="second-video"></video>
        <script>
            window.firstVideoReadyState = 0;
            window.secondVideoReadyState = 0;
            Object.defineProperty(document.getElementById('first-video'), 'readyState', {
                configurable: true,
                get() { return window.firstVideoReadyState; }
            });
            Object.defineProperty(document.getElementById('second-video'), 'readyState', {
                configurable: true,
                get() { return window.secondVideoReadyState; }
            });
        </script>
        </body></html>""",
    )

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_ready_step(renderer, page, "Videos")
        assert page.evaluate("() => window.waitReadyDone") is False

        page.evaluate(
            """() => {
                window.firstVideoReadyState = 2;
                const first = document.getElementById('first-video');
                first.dispatchEvent(new Event('loadeddata'));
                first.dispatchEvent(new Event('error'));
            }"""
        )
        # Both events belong to the same video, so they must consume only one counter slot.
        assert page.evaluate("() => window.waitReadyDone") is False

        page.evaluate(
            """() => {
                window.secondVideoReadyState = 2;
                document.getElementById('second-video').dispatchEvent(new Event('loadeddata'));
            }"""
        )
        page.wait_for_function("() => window.waitReadyDone === true")

        assert page.evaluate("() => window.waitReadyError") is None
        browser.close()


@pytest.mark.unit
def test_wait_for_render_ready_double_request_animation_frame_resolves(tmp_path, monkeypatch):
    renderer = _simple_renderer(tmp_path, "<html><body><p>Animation frame</p></body></html>")
    report_dir = tmp_path / "double-raf-report"
    report_dir.mkdir()
    _write_html(report_dir, "<html><body><p>Animation frame</p></body></html>")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto((report_dir / "index.html").as_uri(), wait_until="load")

        _start_ready_step(renderer, page, "Double requestAnimationFrame")

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

    renderer = _OfflinePlaywrightPDFRenderer(html_dir=html_dir.name, **_browser_metadata_kwargs())

    assert renderer._html_dir == html_dir.resolve()
    assert renderer._resolve_entrypoint_path() == (html_dir / "index.html").resolve()


@pytest.mark.unit
def test_renderer_requires_html_dir_for_offline_entrypoint_resolution():
    renderer = _OfflinePlaywrightPDFRenderer(html_dir=None, **_browser_metadata_kwargs())

    with pytest.raises(ADRException, match="HTML directory is not configured"):
        renderer._resolve_entrypoint_path()


@pytest.mark.unit
def test_renderer_rejects_non_enum_page_size(tmp_path):
    # Raw strings are ambiguous with custom dimensions and bypass the supported
    # public value set, so only enum members are accepted as fixed formats.
    with pytest.raises(ADRException, match="page_size must be a PDFPageSize member"):
        _OfflinePlaywrightPDFRenderer(
            html_dir=_write_html(tmp_path, "<html><body>Invalid page size</body></html>"),
            page_size="A3",
            **_browser_metadata_kwargs(),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "width, height",
    [("12in", None), (None, "18in")],
)
def test_renderer_requires_custom_width_and_height_together(tmp_path, width, height):
    # A complete pair keeps page orientation and printable-area calculations deterministic.
    with pytest.raises(ADRException, match="width and height must be provided together"):
        _OfflinePlaywrightPDFRenderer(
            html_dir=_write_html(tmp_path, "<html><body>Incomplete dimensions</body></html>"),
            page_size=None,
            width=width,
            height=height,
            **_browser_metadata_kwargs(),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "width, height, expected_error",
    [
        ("0px", "18in", "width must be a positive PDF length"),
        ("12in", -1.0, "height must be a positive PDF length"),
        ("1em", "18in", "Unsupported PDF length unit"),
    ],
)
def test_renderer_rejects_invalid_custom_dimensions(tmp_path, width, height, expected_error):
    # Validate values with the same converter used by viewport and pagination math.
    with pytest.raises(ADRException, match=expected_error):
        _OfflinePlaywrightPDFRenderer(
            html_dir=_write_html(tmp_path, "<html><body>Invalid dimensions</body></html>"),
            page_size=None,
            width=width,
            height=height,
            **_browser_metadata_kwargs(),
        )


@pytest.mark.unit
def test_renderer_rejects_margins_that_consume_custom_page_height(tmp_path):
    # Validation happens during construction, before Chromium or staging work starts.
    with pytest.raises(ADRException, match="leave at least one CSS pixel"):
        _OfflinePlaywrightPDFRenderer(
            html_dir=_write_html(tmp_path, "<html><body>No printable height</body></html>"),
            page_size=None,
            width="8in",
            height="1in",
            margins={"top": "0.5in", "right": "0", "bottom": "0.5in", "left": "0"},
            **_browser_metadata_kwargs(),
        )


@pytest.mark.unit
def test_renderer_rejects_horizontal_margins_that_consume_selected_page_width(tmp_path):
    # Pin A4 because two 105 mm margins consume its 210 mm portrait width.
    with pytest.raises(ADRException, match="leave at least one CSS pixel"):
        _OfflinePlaywrightPDFRenderer(
            html_dir=_write_html(tmp_path, "<html><body>No printable width</body></html>"),
            page_size=PDFPageSize.A4,
            margins={
                "top": "10mm",
                "right": "105mm",
                "bottom": "10mm",
                "left": "105mm",
            },
            **_browser_metadata_kwargs(),
        )


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
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>Requests</body></html>"),
        **_browser_metadata_kwargs(),
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
    renderer = _OfflinePlaywrightPDFRenderer(html_dir=Path("."), **_browser_metadata_kwargs())
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
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=_write_html(tmp_path, "<html><body>WebSockets</body></html>"),
        **_browser_metadata_kwargs(),
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
        ({"render_timeout": float("nan")}, "render_timeout must be a positive number"),
        ({"render_timeout": float("inf")}, "render_timeout must be a positive number"),
        ({"render_timeout": float("-inf")}, "render_timeout must be a positive number"),
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
def test_renderer_constructor_rejects_invalid_options(
    tmp_path: Path, kwargs: dict[str, object], expected_error: str
) -> None:
    html_dir = _write_html(tmp_path, "<html><body>Invalid options</body></html>")

    with pytest.raises(ADRException, match=expected_error):
        _OfflinePlaywrightPDFRenderer(
            html_dir=html_dir,
            **_browser_metadata_kwargs(),
            **kwargs,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "ansys_installation, ansys_version",
    [
        (None, int(DEFAULT_ANSYS_VERSION)),
        (_fake_ansys_installation(int(DEFAULT_ANSYS_VERSION)), None),
        (None, None),
    ],
)
def test_renderer_constructor_requires_product_browser_metadata(
    tmp_path, ansys_installation, ansys_version
):
    html_dir = _write_html(tmp_path, "<html><body>Missing metadata</body></html>")

    with pytest.raises(
        ADRException,
        match="requires ansys_installation and ansys_version",
    ):
        _OfflinePlaywrightPDFRenderer(
            html_dir=html_dir,
            ansys_installation=ansys_installation,
            ansys_version=ansys_version,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "render_timeout, expected_cause_type",
    [
        ("abc", ValueError),
        (None, TypeError),
    ],
)
def test_renderer_constructor_chains_render_timeout_conversion_errors(
    tmp_path, render_timeout, expected_cause_type
):
    html_dir = _write_html(tmp_path, "<html><body>Invalid timeout</body></html>")

    with pytest.raises(ADRException, match="render_timeout must be a positive number") as exc_info:
        _OfflinePlaywrightPDFRenderer(
            html_dir=html_dir,
            render_timeout=render_timeout,
            **_browser_metadata_kwargs(),
        )

    assert isinstance(exc_info.value.__cause__, expected_cause_type)


@pytest.mark.unit
def test_playwright_pdf_transient_override_env_vars_are_explicit_contract():
    """Lock in the exact transient override env vars that browser-PDF render scope clears."""
    # The render scope clears only host-platform overrides because browser-PDF handles
    # PLAYWRIGHT_BROWSERS_PATH separately.
    assert (
        _OfflinePlaywrightPDFRenderer._TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS
        == _EXPECTED_TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS
    )


@pytest.mark.unit
def test_playwright_pdf_sets_product_browser_path_during_startup_when_user_env_is_unset(
    tmp_path, monkeypatch
):
    """Set ``PLAYWRIGHT_BROWSERS_PATH`` to the product browser directory during startup."""
    renderer, flow, browser_binary_dir = _arrange_product_browser_renderer(tmp_path, monkeypatch)
    env_seen: dict[str, str | None] = {}

    _capture_render_start_env(flow, env_seen)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    assert renderer.render_pdf() == b"%PDF-mock"
    assert env_seen["playwright_browsers_path"] == str(browser_binary_dir)


@pytest.mark.unit
def test_playwright_pdf_removes_product_browser_path_after_render_when_user_env_is_unset(
    tmp_path, monkeypatch
):
    """Remove the temporary product browser path after render when no user path existed."""
    renderer, _flow, _browser_binary_dir = _arrange_product_browser_renderer(tmp_path, monkeypatch)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    renderer.render_pdf()

    assert "PLAYWRIGHT_BROWSERS_PATH" not in os.environ


@pytest.mark.unit
def test_playwright_pdf_scrubs_transient_override_env_vars_during_startup_and_restores_after_render(
    tmp_path, monkeypatch
):
    """Clear transient Playwright override env vars during startup and restore them afterward."""
    renderer, flow, _browser_binary_dir = _arrange_product_browser_renderer(tmp_path, monkeypatch)
    runtime_override_envs = {
        env_var: f"{env_var.lower()}-value"
        for env_var in _EXPECTED_TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS
    }
    env_seen: dict[str, object] = {}

    _capture_render_start_env(flow, env_seen)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    for env_var, env_value in runtime_override_envs.items():
        monkeypatch.setenv(env_var, env_value)

    renderer.render_pdf()

    assert all(value is None for value in env_seen["transient_override_envs"].values())
    for env_var, env_value in runtime_override_envs.items():
        assert os.environ[env_var] == env_value


@pytest.mark.unit
def test_playwright_pdf_overrides_user_browser_path_env_with_product_binary(tmp_path, monkeypatch):
    """Override a user-supplied browser path during render but restore it afterward."""
    renderer, flow, browser_binary_dir = _arrange_product_browser_renderer(tmp_path, monkeypatch)
    user_browser_path = str(tmp_path / "user-browser-path")
    resolver_args: dict[str, object] = {}
    env_seen: dict[str, str | None] = {}

    def resolve_browser_binary_info(ansys_installation=None, ansys_version=None):
        """Capture forwarded product inputs while returning fake browser metadata."""
        # This is the only product-browser env test that asserts resolver forwarding.
        resolver_args.update(
            {
                "ansys_installation": ansys_installation,
                "ansys_version": ansys_version,
            }
        )
        return _browser_binary_info(browser_binary_dir)

    monkeypatch.setattr(
        pdf_renderer_module,
        "resolve_playwright_browser_binary_info",
        resolve_browser_binary_info,
    )
    _capture_render_start_env(flow, env_seen)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", user_browser_path)

    assert renderer.render_pdf() == b"%PDF-mock"
    assert env_seen["playwright_browsers_path"] == str(browser_binary_dir)
    assert resolver_args == {
        "ansys_installation": str(renderer._ansys_installation),
        "ansys_version": renderer._ansys_version,
    }
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == user_browser_path


@pytest.mark.unit
def test_playwright_pdf_rejects_product_line_26_before_browser_start(tmp_path, monkeypatch):
    html_dir = _write_html(tmp_path, "<html><body><p>Unsupported line</p></body></html>")
    ansys_version = 261
    renderer = _OfflinePlaywrightPDFRenderer(
        html_dir=html_dir,
        ansys_installation=_fake_ansys_installation(ansys_version),
        ansys_version=ansys_version,
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
    renderer, _flow, _browser_binary_dir = _arrange_product_browser_renderer(tmp_path, monkeypatch)
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
        match="requires a valid product-shipped browser binary",
    ):
        renderer.render_pdf()


@pytest.mark.unit
def test_playwright_pdf_launch_failure_raises_clean_error_without_leaking_playwright(
    tmp_path, monkeypatch
):
    """A Playwright launch failure surfaces a clean ADR error and still restores env."""
    renderer, flow, browser_binary_dir = _arrange_product_browser_renderer(
        tmp_path,
        monkeypatch,
        launch_side_effect=PlaywrightError("Executable doesn't exist; run playwright install"),
    )
    user_browser_path = str(tmp_path / "user-browser-path")
    env_seen: dict[str, str | None] = {}

    _capture_render_start_env(flow, env_seen)
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", user_browser_path)

    with pytest.raises(ADRException, match=r"Browser PDF rendering failed\.$") as exc_info:
        renderer.render_pdf()
    # The caller must never have to catch Playwright errors directly: the surfaced message stays
    # ADR-owned, while the original Playwright failure remains available as the chained cause.
    assert isinstance(exc_info.value.__cause__, PlaywrightError)
    assert "Executable doesn't exist" in str(exc_info.value.__cause__)
    assert "playwright" not in str(exc_info.value).lower()
    # The product browser path is still selected for the render and the env restored afterward.
    assert env_seen["playwright_browsers_path"] == str(browser_binary_dir)
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == user_browser_path


@pytest.mark.unit
def test_base_renderer_cannot_be_instantiated_directly():
    """The shared base renderer is abstract; concrete subclasses must supply the seams."""
    with pytest.raises(TypeError):
        pdf_renderer_module._BasePlaywrightPDFRenderer()
