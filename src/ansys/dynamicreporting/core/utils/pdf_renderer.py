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

"""
Browser-fidelity HTML-to-PDF rendering for ADR exports.

This module holds the shared Playwright renderers used by both:

- the serverless ADR export path, which stages HTML from Django-rendered content
- the remote-server export path, which opens the live report page directly

Architecture
------------
This renderer intentionally relies on two linked Chromium layout phases instead of
treating PDF export as a screenshot of already-painted viewport pixels:

    browser-loadable report source
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

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, fields
import json
import os
import platform
import re
from math import ceil
from pathlib import Path
from time import monotonic
from typing import Any, ClassVar
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ..adr_utils import get_logger
from ..compatibility import install_version_to_product_release
from ..compatibility import product_release_to_display_string
from ..compatibility import product_release_to_product_line
from ..exceptions import ADRException

_PLAYWRIGHT_BROWSER_METADATA_NAME = "playwright_browser_metadata.json"


@dataclass(frozen=True)
class _PlaywrightBrowserBinaryInfo:
    """Validated product-shipped Playwright browser binary path and required metadata."""

    EXPECTED_BROWSER_NAME: ClassVar[str] = "chromium-headless-shell"

    path: Path
    browser_name: str
    machine_arch: str
    packaged_binary_dir: str

    @classmethod
    def metadata_field_names(cls) -> tuple[str, ...]:
        """Return the serialized metadata fields, excluding the filesystem path."""
        return tuple(field.name for field in fields(cls) if field.name != "path")

    @classmethod
    def from_metadata_dict(
        cls, *, path: Path, metadata: dict[str, object]
    ) -> "_PlaywrightBrowserBinaryInfo":
        """Build a metadata record from a raw JSON object using the dataclass schema."""
        return cls(
            path=path,
            **{
                field_name: str(metadata.get(field_name, "")).strip()
                for field_name in cls.metadata_field_names()
            },
        )

    def to_metadata_dict(self) -> dict[str, str]:
        """Serialize the metadata fields using the dataclass schema."""
        return {field_name: getattr(self, field_name) for field_name in self.metadata_field_names()}


def _playwright_machine_arch() -> str | None:
    """Map the current platform to the ADR ``machines/<arch>`` directory name.

    ADR product builds ship Playwright browsers only for Windows (``win64``) and
    Linux (``linux_2.6_64``), so other platforms have no product binary to point at
    and resolve to ``None``. These are the same ``machines/<arch>`` names
    ``ADR.setup`` already uses; they are hardcoded here rather than read from
    ``enve_arch()`` because the serverless browser-PDF path cannot assume ``enve``
    is importable in the caller's Python environment.
    """
    system_name = platform.system().lower()
    if system_name.startswith("win"):
        return "win64"
    if system_name.startswith("linux"):
        return "linux_2.6_64"
    return None


def _validate_playwright_browsers_path(
    browser_dir: Path,
    machine_arch: str,
) -> _PlaywrightBrowserBinaryInfo | None:
    """Validate the product-shipped Playwright binary layout before advertising it.

    Browser-PDF export should only point Playwright at a product-managed binary
    when the stripped package layout is complete and self-consistent. This keeps
    the runtime honest to the product packaging contract instead of silently
    accepting stale or partially copied browser directories. The metadata file
    lives inside ``playwright-browsers`` itself.
    """
    if not browser_dir.is_dir():
        return None

    metadata_path = browser_dir / _PLAYWRIGHT_BROWSER_METADATA_NAME
    if not metadata_path.is_file():
        get_logger().warning(
            "Ignoring product Playwright binary at %s because metadata file %s is missing ",
            browser_dir,
            _PLAYWRIGHT_BROWSER_METADATA_NAME,
        )
        return None

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        get_logger().warning(
            "Ignoring product Playwright binary at %s because metadata file %s is unreadable: %s",
            browser_dir,
            metadata_path,
            exc,
        )
        return None

    if not isinstance(metadata, dict):
        get_logger().warning(
            "Ignoring product Playwright binary at %s because metadata file %s does not contain "
            "a JSON object.",
            browser_dir,
            metadata_path,
        )
        return None

    metadata_info = _PlaywrightBrowserBinaryInfo.from_metadata_dict(
        path=browser_dir, metadata=metadata
    )
    if (
        not metadata_info.packaged_binary_dir
        or metadata_info.browser_name != _PlaywrightBrowserBinaryInfo.EXPECTED_BROWSER_NAME
        or metadata_info.machine_arch != machine_arch
    ):
        get_logger().warning(
            "Ignoring product Playwright binary at %s because metadata file %s is incomplete or "
            "does not describe a %s binary for machine arch %r.",
            browser_dir,
            metadata_path,
            _PlaywrightBrowserBinaryInfo.EXPECTED_BROWSER_NAME,
            metadata_info.machine_arch,
        )
        return None

    packaged_dirs = sorted(path for path in browser_dir.iterdir() if path.is_dir())
    if len(packaged_dirs) != 1:
        get_logger().warning(
            "Ignoring product Playwright binary at %s because it contains %d packaged browser "
            "directories instead of exactly one.",
            browser_dir,
            len(packaged_dirs),
        )
        return None

    packaged_dir = packaged_dirs[0]
    if packaged_dir.name != metadata_info.packaged_binary_dir:
        get_logger().warning(
            "Ignoring product Playwright binary at %s because packaged directory %s does not "
            "match metadata entry %s.",
            browser_dir,
            packaged_dir.name,
            metadata_info.packaged_binary_dir,
        )
        return None

    marker_path = packaged_dir / "INSTALLATION_COMPLETE"
    if not marker_path.is_file():
        get_logger().warning(
            "Ignoring product Playwright binary at %s because installation marker %s is missing.",
            browser_dir,
            marker_path,
        )
        return None

    return metadata_info


def resolve_playwright_browser_binary_info(
    ansys_installation: str | None = None,
    ansys_version: int | None = None,
) -> _PlaywrightBrowserBinaryInfo | None:
    """Return the validated browser binary path and metadata when the product ships one."""
    machine_arch = _playwright_machine_arch()
    # The install directory and version are both required to build the machine-scoped
    # binary path, so bail out when either is missing or the current platform has no
    # validated ADR packaging layout. The version is used as-is: ADR.__init__ already
    # resolved and validated it through resolve_install_info, so re-validating it here
    # would only duplicate that frontloaded work.
    if machine_arch is None or ansys_installation is None or ansys_version is None:
        return None

    browser_dir = (
        Path(ansys_installation).expanduser()
        / f"apex{ansys_version}"
        / "machines"
        / machine_arch
        / "playwright-browsers"
    )
    return _validate_playwright_browsers_path(browser_dir, machine_arch)


class _BasePlaywrightPDFRenderer(ABC):
    """Shared Playwright browser-to-PDF render pipeline for ADR reports.

    Subclasses supply the navigation target and browser-context setup for either
    a staged offline HTML bundle or a live ADR report URL.

    Parameters
    ----------
    landscape : bool, default: False
        Whether to render the PDF in landscape orientation.
    margins : dict[str, str], optional
        Page margins with ``top``, ``right``, ``bottom``, and ``left`` Playwright PDF lengths.
        If omitted, 10 mm margins are used on every side.
    render_timeout : float, default: 30.0
        Maximum time, in seconds, for the Chromium render phase after the offline HTML bundle
        has been staged. This shared budget covers browser launch, navigation, readiness waits,
        and other browser-side preparation steps, but not server-side template rendering or
        offline asset export.
    ansys_installation : Path or str, optional
        Resolved Ansys installation root used to locate a product-shipped
        Playwright browser binary. When provided with ``ansys_version`` on a
        supported product line, browser-PDF export uses that shipped browser
        cache for the render instead of any ambient browser-path override.
    ansys_version : int, optional
        Ansys version associated with ``ansys_installation``.  This is used
        only to locate ``apex###/machines/...`` runtime assets when the product
        ships Playwright browsers inside the installation tree.
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
    # This override changes Playwright's platform-specific browser lookup, while
    # the ADR resolver has already selected the product machine directory.
    # `PLAYWRIGHT_BROWSERS_PATH` is handled separately because browser-PDF replaces
    # it with the product-shipped browser cache for the duration of a render.
    _TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS: tuple[str, ...] = (
        "PLAYWRIGHT_HOST_PLATFORM_OVERRIDE",
    )
    # Browser-PDF depends on a product-shipped Chromium binary introduced with
    # product line 27. Older supported lines can still use other export formats.
    _MIN_BROWSER_PDF_PRODUCT_LINE: int = 27

    def __init__(
        self,
        *,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = _DEFAULT_RENDER_TIMEOUT,
        ansys_installation: Path | str | None = None,
        ansys_version: int | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize the renderer with shared browser-PDF configuration."""
        self._landscape = landscape
        self._margins = self._validate_margins(margins)
        self._render_timeout = self._validate_render_timeout(render_timeout)
        # Keep the raw install metadata so the renderer can locate a product-managed
        # Playwright browser binary without changing the public browser-PDF API shape.
        self._ansys_installation = (
            None if ansys_installation is None else Path(ansys_installation).expanduser()
        )
        self._ansys_version = ansys_version
        self._logger = logger or get_logger()

    def _browser_pdf_product_line(self) -> int | None:
        """Return the annual product line for the resolved install version."""
        product_release = self._browser_pdf_product_release()
        if product_release is None:
            return None

        return int(product_release_to_product_line(product_release))

    def _browser_pdf_product_release(self) -> str | None:
        """Return the public product release for the resolved install version."""
        if self._ansys_version is None:
            return None

        try:
            return install_version_to_product_release(self._ansys_version)
        except ValueError:
            return None

    def _raise_if_product_line_unsupported(self) -> None:
        """Reject product lines that predate the shipped browser-PDF binary."""
        product_line = self._browser_pdf_product_line()
        if product_line is not None and product_line < self._MIN_BROWSER_PDF_PRODUCT_LINE:
            product_release = self._browser_pdf_product_release()
            if product_release is None:
                raise ValueError("Product release information could not be determined.")
            product_name = product_release_to_display_string(product_release)
            min_product_name = product_release_to_display_string(
                f"{self._MIN_BROWSER_PDF_PRODUCT_LINE}.1"
            )
            raise ADRException(
                f"Browser PDF export is not supported for Ansys {product_name}. "
                f"Use Ansys {min_product_name} or newer, which ships the required "
                "browser binary."
            )

    def _resolve_playwright_browser_binary(self) -> _PlaywrightBrowserBinaryInfo | None:
        """Return a shipped Playwright browser binary path under the Ansys install, if any."""
        self._raise_if_product_line_unsupported()

        if self._ansys_installation is None or self._ansys_version is None:
            return None

        binary_info = resolve_playwright_browser_binary_info(
            ansys_installation=(
                None if self._ansys_installation is None else str(self._ansys_installation)
            ),
            ansys_version=self._ansys_version,
        )
        if binary_info is None:
            raise ADRException(
                "Browser PDF export requires a valid product-shipped browser binary, "
                f"but none was found for Ansys version {self._ansys_version}."
            )

        return binary_info

    @contextmanager
    def _playwright_browser_binary_env(self):
        """Temporarily point Playwright at the product-shipped browser binary path.

        Playwright documents `PLAYWRIGHT_BROWSERS_PATH` as the supported way to
        share browser binaries across environments. Product-coupled browser-PDF
        renders must use the browser shipped inside the resolved Ansys install
        rather than any ambient machine-level Playwright browser cache, but the
        caller's original environment must still be restored afterward. The
        host-platform override is cleared because it can make Playwright look for
        a different platform layout than the ADR package resolver selected.

        This mutates ``os.environ`` for the duration of the render and restores it on
        exit, so two browser-PDF renders must not run concurrently in the same process.
        The synchronous Playwright driver renders one report at a time, which keeps that
        constraint satisfied on this export path.
        """
        restored_override_envs = {
            env_var: os.environ.pop(env_var)
            for env_var in self._TRANSIENT_PLAYWRIGHT_OVERRIDE_ENV_VARS
            if env_var in os.environ
        }
        restored_browser_binaries_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        installed_browser_binary_env = False
        try:
            browser_binary_dir = self._resolve_playwright_browser_binary()
            if browser_binary_dir is not None:
                self._logger.info(
                    "Using product-shipped Playwright browser binary path: %s",
                    browser_binary_dir.path,
                )
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_binary_dir.path)
                installed_browser_binary_env = True
            yield
        finally:
            if installed_browser_binary_env:
                # Restore the caller's original browser-path override after the
                # render so the product-specific choice stays scoped to this
                # browser-PDF operation.
                if restored_browser_binaries_path is None:
                    os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
                else:
                    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = restored_browser_binaries_path
            os.environ.update(restored_override_envs)

    def render_pdf(self) -> bytes:
        """Render the configured browser-PDF source to PDF bytes.

        Returns
        -------
        bytes
            PDF document bytes produced by headless Chromium.

        Raises
        ------
        ADRException
            If the browser render/export flow fails.
        """
        navigation_target = self._get_navigation_target()
        browser_phase_deadline = monotonic() + self._render_timeout
        current_timeout_phase = "browser launch"

        try:
            # Point Playwright at the product-shipped browser binary before the
            # driver resolves browser binaries so browser-PDF never falls back
            # to an unrelated machine-level Chromium cache.
            with self._playwright_browser_binary_env(), sync_playwright() as playwright:
                self._logger.info("Launching headless Chromium for browser PDF export.")
                browser = playwright.chromium.launch(
                    headless=True,
                    timeout=self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "browser launch"
                    ),
                )
                context = None

                try:
                    self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "browser context creation"
                    )
                    # Fix the responsive layout width up front so Plotly and other browser-rendered
                    # items lay themselves out deterministically before the PDF width is computed.
                    context = self._new_browser_context(browser)
                    self._prepare_context(context)
                    self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "page creation"
                    )
                    page = context.new_page()

                    # Load the source page exactly as Chromium will render it for the PDF pass.
                    self._logger.info(f"Loading browser PDF source: {navigation_target}")
                    # Keep navigation inside the same shared browser-phase budget used by the
                    # later readiness checks. Playwright documents ``page.goto(timeout=...)`` in
                    # milliseconds, so convert the remaining budget just before navigation.
                    current_timeout_phase = "page navigation"
                    navigation_timeout_ms = self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, current_timeout_phase
                    )
                    page.goto(
                        navigation_target,
                        wait_until="load",
                        timeout=navigation_timeout_ms,
                    )

                    # Force screen media so the PDF matches the browser view instead of print CSS.
                    page.emulate_media(media="screen")
                    self._apply_pdf_capture_styles(page)
                    self._wait_for_render_ready(page, deadline=browser_phase_deadline)
                    self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "PDF width measurement"
                    )
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
                    #
                    # Playwright's Python ``page.pdf()`` API does not expose a timeout parameter,
                    # so this deadline check is a preflight guard rather than an interruptible
                    # in-flight timeout.
                    self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "PDF generation"
                    )
                    pdf_bytes = page.pdf(**pdf_options)
                    self._logger.info(
                        f"Browser PDF generated successfully ({len(pdf_bytes)} bytes)."
                    )
                    return pdf_bytes
                finally:
                    # Playwright recommends explicitly closing contexts created via
                    # browser.new_context() before browser.close() so their resources flush
                    # gracefully. Cleanup failures should not mask successful PDF bytes or the
                    # original render failure.
                    if context is not None:
                        try:
                            context.close()
                        except Exception:
                            self._logger.debug(
                                "Failed to close Playwright browser context.", exc_info=True
                            )
                    try:
                        browser.close()
                    except Exception:
                        self._logger.debug("Failed to close Playwright browser.", exc_info=True)
        except ADRException:
            raise
        except PlaywrightTimeoutError:
            # Keep Playwright's own timeout wording out of the caller-facing error. Log the full
            # trace for debugging, then raise a clean, ADR-owned timeout message. ``from None``
            # suppresses exception chaining so the Playwright timeout never appears in tracebacks.
            self._logger.error(
                "Browser PDF render timed out during %s.", current_timeout_phase, exc_info=True
            )
            raise ADRException(
                f"Browser PDF rendering failed: {current_timeout_phase} timed out after "
                f"{self._render_timeout:.1f}s"
            ) from None
        except Exception:
            # Never surface Playwright/driver internals to the caller. Log the trace for
            # debugging and raise a generic ADR error. ``from None`` suppresses chaining so the
            # underlying Playwright/driver exception never appears in tracebacks.
            self._logger.error("Browser PDF rendering failed.", exc_info=True)
            raise ADRException("Browser PDF rendering failed.") from None

    @abstractmethod
    def _get_navigation_target(self) -> str:
        """Return the URL Chromium should open for the browser-PDF render pass."""
        raise NotImplementedError

    @abstractmethod
    def _new_browser_context(self, browser: Any) -> Any:
        """Create the browser context used by this renderer."""
        raise NotImplementedError

    @abstractmethod
    def _prepare_context(self, context: Any) -> None:
        """Configure the browser context before opening the source page."""
        raise NotImplementedError

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
                adr-slider-template > section[id^="slider_container_"],
                adr-slider-template > section[id^="slider_container_"] > section.adr-row,
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

    def _block_external_requests(self, context: Any) -> None:
        """Keep browser-PDF rendering offline while still allowing local export assets."""

        def route_request(route: Any) -> None:
            request_url = route.request.url
            parsed_url = urlsplit(request_url)
            scheme = parsed_url.scheme.lower()
            # Block both known-external schemes (http, https, ws, wss) and any URL with an
            # authority component (netloc). The netloc check catches protocol-relative URLs
            # like //example.com/file and file:// URLs with hostnames like file://example.com/file
            # that the scheme check alone would miss.
            if scheme in self._BLOCKED_REQUEST_SCHEMES or parsed_url.netloc:
                route.abort()
                return
            route.continue_()

        def is_external_websocket(url: str) -> bool:
            return urlsplit(url).scheme.lower() in self._BLOCKED_WEBSOCKET_SCHEMES

        def route_websocket(websocket_route: Any) -> None:
            websocket_route.close()

        # ADR's HTML exporter writes a self-contained file:// bundle. Blocking known network
        # schemes plus any authority-bearing URL prevents report HTML from calling back to
        # arbitrary hosts during PDF generation while still allowing local file:, data:, and
        # blob: resources that are part of the offline export.
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
        """Validate the shared browser-phase timeout."""
        error_message = "Browser PDF render_timeout must be a positive number."
        try:
            timeout = float(render_timeout)
        except (TypeError, ValueError):
            # ``from None`` keeps the underlying numeric-conversion error out of the traceback.
            raise ADRException(error_message) from None

        if timeout <= 0:
            raise ADRException(error_message)
        return timeout

    def _remaining_browser_phase_timeout_ms(self, deadline: float, phase_name: str) -> int:
        """Return the remaining browser-phase budget in milliseconds.

        The browser-PDF public API exposes ``render_timeout`` in seconds for the Chromium
        rendering phase as a whole. Convert the remaining monotonic budget just before each
        browser-side operation so navigation and readiness waits spend from one shared deadline
        instead of each resetting a fresh timeout window.
        """
        # ceil() rounds up to ensure timeout is never 0. ceil(0.0001 * 1000) = 1 instead of 0.
        # Playwright treats timeout=0 as "no timeout", so rounding down to 0 would accidentally
        # disable the timeout. Fractional milliseconds are always rounded up, giving the operation
        # slightly more time rather than slightly less.
        remaining_ms = ceil((deadline - monotonic()) * 1000)
        if remaining_ms <= 0:
            raise ADRException(
                f"Browser PDF rendering failed: {phase_name} timed out after "
                f"{self._render_timeout:.1f}s"
            )
        return remaining_ms

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
        try:
            remaining_ms = self._remaining_browser_phase_timeout_ms(deadline, step_name)
        except ADRException:
            # Emit a separate diagnostic for steps that exhausted the shared render
            # budget before the renderer could hand control to Playwright.
            self._logger.debug(
                "Browser render readiness step failed before browser evaluation "
                "because the shared render budget was exhausted: "
                f"{step_name}"
            )
            raise

        step_started = monotonic()
        step_outcome = "completed"
        try:
            evaluate_result = page.evaluate(
                f"""() => {{
                    const timeoutMs = {remaining_ms};
                    const waitForReady = {wait_script};
                    const timeoutResult = new Promise((resolve) => {{
                        setTimeout(() => {{
                            resolve({{ __adrTimedOut: true }});
                        }}, timeoutMs);
                    }});
                    const readinessResult = waitForReady()
                        .then(() => {{
                            return {{ __adrTimedOut: false }};
                        }});
                    return Promise.race([readinessResult, timeoutResult]);
                }}""",
            )
            if isinstance(evaluate_result, dict) and evaluate_result.get("__adrTimedOut") is True:
                raise ADRException(
                    f"Browser PDF rendering failed: {step_name} timed out after "
                    f"{self._render_timeout:.1f}s"
                )
        except Exception as exc:
            step_outcome = "failed"
            raise
        finally:
            elapsed_ms = (monotonic() - step_started) * 1000.0
            self._logger.debug(
                f"Browser render readiness step {step_outcome} in {elapsed_ms:.1f} ms: {step_name}"
            )

    def _wait_for_render_ready(self, page: Any, *, deadline: float) -> None:
        """Wait for browser rendering signals that indicate the page is ready to print."""
        self._logger.info("Waiting for browser render readiness signals.")

        # The readiness pipeline intentionally waits only on product-owned signals that ADR
        # emits during its staged print-mode browser render. HTML items and layout ``HTML``
        # fragments are rendered from raw macro-expanded HTML, so arbitrary custom JavaScript
        # inside those fragments does not have a separate readiness contract here. Supported
        # browser-PDF reports therefore assume such HTML is static or settles itself through
        # one of the standard signals below.

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
        #    Plotly.Plots.resize() resolves, but theme-mismatch rerenders can leave the
        #    sibling ADR loader overlay visible until a later style update. Wait for both
        #    the product-owned loaded class and a hidden loader overlay before capture.
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
                    function findLoader(plot) {
                        const item = plot.closest('adr-data-item');
                        return item ? item.querySelector('.adr-spinner-loader-container') : null;
                    }
                    function loaderHidden(loader) {
                        if (!loader) {
                            return true;
                        }
                        const style = getComputedStyle(loader);
                        return (
                            style.display === 'none' ||
                            style.visibility === 'hidden' ||
                            style.opacity === '0'
                        );
                    }
                    function isReady(plot) {
                        return plot.classList.contains('loaded') && loaderHidden(findLoader(plot));
                    }
                    plots.forEach((plot) => {
                        if (isReady(plot)) { check(); return; }
                        const loader = findLoader(plot);
                        const observer = new MutationObserver(() => {
                            if (isReady(plot)) {
                                observer.disconnect();
                                check();
                            }
                        });
                        observer.observe(plot, { attributes: true, attributeFilter: ['class'] });
                        if (loader) {
                            observer.observe(loader, {
                                attributes: true,
                                attributeFilter: ['style', 'class', 'hidden'],
                            });
                        }
                    });
                });
            }""",
        )

        # 6. Images: wait for every <img> to finish loading (covers static images,
        #    scene proxy thumbnails, file proxy images, animation thumbnails, and
        #    canvas-backed enhanced-image/deep-image views).
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
                    function findCompanionCanvas(img) {
                        if (!img.id) {
                            return null;
                        }
                        return document.getElementById(`${img.id}_canvas`);
                    }
                    function companionCanvasReady(img) {
                        const canvas = findCompanionCanvas(img);
                        if (!canvas) {
                            return true;
                        }
                        const style = getComputedStyle(canvas);
                        return style.display !== 'none' && style.visibility !== 'hidden';
                    }
                    function isReady(img) {
                        // Require both a source and decoded image dimensions before fast-passing
                        // the image. ``img.complete`` alone is too weak because a src-less <img>
                        // can already report complete even though async product code has not yet
                        // populated the final image bytes.
                        //
                        // ADR slider/deep-image widgets also render into a companion <canvas>
                        // after the underlying <img> load finishes. Those widgets can keep a
                        // stale completed <img> source around while a new TIFF or enhanced-image
                        // decode is still in flight, so do not treat the image as ready until the
                        // visible companion canvas has been unhidden.
                        const hasSource = Boolean(img.currentSrc || img.getAttribute('src'));
                        return hasSource && img.complete && img.naturalWidth > 0 && companionCanvasReady(img);
                    }
                    imgs.forEach((img) => {
                        if (isReady(img)) {
                            done();
                            return;
                        }
                        let observer = null;
                        function cleanup() {
                            img.removeEventListener('load', onLoad);
                            img.removeEventListener('error', onError);
                            if (observer) {
                                observer.disconnect();
                            }
                        }
                        function onLoad() {
                            if (isReady(img)) {
                                cleanup();
                                done();
                            }
                        }
                        function onError() {
                            cleanup();
                            done();
                        }
                        img.addEventListener('load', onLoad, { once: true });
                        img.addEventListener('error', onError, { once: true });
                        const companionCanvas = findCompanionCanvas(img);
                        if (companionCanvas) {
                            observer = new MutationObserver(() => {
                                if (isReady(img)) {
                                    cleanup();
                                    done();
                                }
                            });
                            observer.observe(companionCanvas, {
                                attributes: true,
                                attributeFilter: ['style', 'class', 'hidden'],
                            });
                        }
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

        # 8. Double requestAnimationFrame gives the page another repaint opportunity
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


class _OfflinePlaywrightPDFRenderer(_BasePlaywrightPDFRenderer):
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
        Maximum time, in seconds, for the Chromium render phase after the offline HTML bundle
        has been staged. This shared budget covers browser launch, navigation, readiness waits,
        and other browser-side preparation steps, but not server-side template rendering or
        offline asset export.
    ansys_installation : Path or str, optional
        Resolved Ansys installation root used to locate a product-shipped
        Playwright browser binary. When provided with ``ansys_version`` on a
        supported product line, browser-PDF export uses that shipped browser
        cache for the render instead of any ambient browser-path override.
    ansys_version : int, optional
        Ansys version associated with ``ansys_installation``. This is used only
        to locate ``apex###/machines/...`` runtime assets when the product ships
        Playwright browsers inside the installation tree.
    logger : Any, optional
        Logger used for renderer lifecycle messages.
    """

    def __init__(
        self,
        html_dir: Path | str | None,
        filename: str = "index.html",
        *,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = _BasePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT,
        ansys_installation: Path | str | None = None,
        ansys_version: int | None = None,
        logger: Any = None,
    ) -> None:
        self._html_dir = None if html_dir is None else Path(html_dir).expanduser().resolve()
        self._filename = filename
        super().__init__(
            landscape=landscape,
            margins=margins,
            render_timeout=render_timeout,
            ansys_installation=ansys_installation,
            ansys_version=ansys_version,
            logger=logger,
        )

    def _get_navigation_target(self) -> str:
        """Return the staged HTML bundle entry point for the browser-PDF render pass."""
        return self._resolve_entrypoint_path().as_uri()

    def _new_browser_context(self, browser: Any) -> Any:
        """Create the browser context used by the offline HTML renderer.

        The serverless path renders a fully staged ``file://`` bundle, so the
        context is explicitly offline and blocks service workers to keep the
        browser phase deterministic and self-contained.
        """
        return browser.new_context(
            viewport={
                "width": self._DEFAULT_BROWSER_VIEWPORT_WIDTH,
                "height": self._DEFAULT_BROWSER_VIEWPORT_HEIGHT,
            },
            service_workers="block",
            accept_downloads=False,
            offline=True,
        )

    def _prepare_context(self, context: Any) -> None:
        """Configure the offline browser context before opening the staged bundle."""
        self._block_external_requests(context)

    def _resolve_entrypoint_path(self) -> Path:
        """Return the validated HTML entry-point path that Chromium can open."""
        if self._html_dir is None:
            raise ADRException("Browser PDF HTML directory is not configured for this renderer.")
        entrypoint_path = (self._html_dir / self._filename).resolve()
        if not entrypoint_path.is_relative_to(self._html_dir):
            raise ADRException(
                "Browser PDF entry-point file must be inside the exported HTML directory."
            )
        if not entrypoint_path.is_file():
            raise ADRException(f"Browser PDF entry-point file does not exist: {entrypoint_path}")
        return entrypoint_path


class _ReportURLPlaywrightPDFRenderer(_BasePlaywrightPDFRenderer):
    """Render a live ADR report URL to PDF via headless Chromium.

    The remote-server browser-PDF path already has a running report server, so
    it can render the live report page directly instead of first staging an
    offline HTML bundle.  This class reuses the shared browser readiness and
    PDF sizing flow while keeping network access enabled for same-page assets.
    Like the offline renderer, it renders with the product-shipped Playwright
    browser binary resolved from ``ansys_installation`` and ``ansys_version``.
    """

    def __init__(
        self,
        url: str,
        *,
        auth_cookies: list[dict[str, object]] | None = None,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        render_timeout: float = _BasePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT,
        ansys_installation: Path | str | None = None,
        ansys_version: int | None = None,
        logger: Any = None,
    ) -> None:
        self._url = self._validate_url(url)
        self._auth_cookies = [] if auth_cookies is None else list(auth_cookies)
        super().__init__(
            landscape=landscape,
            margins=margins,
            render_timeout=render_timeout,
            ansys_installation=ansys_installation,
            ansys_version=ansys_version,
            logger=logger,
        )

    def _get_navigation_target(self) -> str:
        """Return the live report URL for the browser-PDF render pass."""
        return self._url

    def _new_browser_context(self, browser: Any) -> Any:
        """Create the browser context used by the live remote-report renderer.

        Unlike the offline HTML renderer, the live report path must keep network
        access enabled so Chromium can fetch the report HTML and its assets from
        the already-running ADR service. This also permits network egress to any
        host the report references; the seeded auth cookies stay domain-scoped by
        the browser, so they are only sent back to the originating ADR service.
        """
        return browser.new_context(
            viewport={
                "width": self._DEFAULT_BROWSER_VIEWPORT_WIDTH,
                "height": self._DEFAULT_BROWSER_VIEWPORT_HEIGHT,
            },
            service_workers="block",
            accept_downloads=False,
        )

    def _prepare_context(self, context: Any) -> None:
        """Seed the live report context with any authenticated ADR web-session cookies."""
        if self._auth_cookies:
            context.add_cookies(self._auth_cookies)

    @staticmethod
    def _validate_url(url: str) -> str:
        """Validate that the live report renderer received an absolute URL."""
        parsed_url = urlsplit(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ADRException(f"Browser PDF report URL is not valid: {url!r}")
        return url
