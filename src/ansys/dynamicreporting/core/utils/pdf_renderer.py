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
    | - selected content-width viewport for layout   |
    | - execute ADR, Plotly, MathJax, viewers       |
    | - wait for readiness signals                  |
    | - inject capture CSS                          |
    | - clip overflow at the printable page width   |
    +-----------------------------------------------+
              |
              v
    +-----------------------------------------------+
    | Phase B: paged PDF generation pass            |
    | - use the selected format or dimensions       |
    | - Chromium generates paged output             |
    | - selected page width caps rendered content   |
    | - content beyond that width is clipped        |
    +-----------------------------------------------+

- Playwright documents ``page.pdf()`` as generating a PDF of the page, with print CSS
  media by default, unless ``page.emulate_media(media="screen")`` is used first (as in our case).
- MDN distinguishes the viewport used for continuous media from the page area used for
  paged media, and notes that the initial containing block changes accordingly.

That distinction matters for browser-PDF exports. Phase A stabilizes responsive
browser-rendered content such as Plotly against the printable width of the selected
oriented page. Phase B passes that explicit sizing to ``page.pdf()`` so the output page
size is definitive and content cannot expand it.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, fields
import json
import os
import platform
import re
from math import ceil, floor, isfinite
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
from ..common_utils import PDFPageSize
from ..constants import ANSYS_VIEWER_TAGS
from ..exceptions import ADRException

# Product-browser metadata filename expected inside the packaged Playwright cache.
_PLAYWRIGHT_BROWSER_METADATA_NAME = "playwright_browser_metadata.json"
# Spare vertical space for subpixel rounding and continuous-to-paged layout reflow.
_PAGINATION_FIT_GUARD_PX = 8.0
# Direct-child headings that own the content container in an ADR basic layout.
_PAGINATION_HEADING_SELECTOR = (
    ":scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > h5, :scope > h6"
)
# Joining the registered tags produces ``:is(ansys-adr-viewer, ansys-nexus-viewer)``.
_SCENE_VIEWER_SELECTOR = f":is({', '.join(ANSYS_VIEWER_TAGS)})"
# Visual elements treated as indivisible and resized instead of split across PDF pages.
_PAGINATION_VISUAL_SELECTOR = f"img, video, canvas, .nexus-plot, {_SCENE_VIEWER_SELECTOR}"


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
        Page margins with ``top``, ``right``, ``bottom``, and ``left`` values expressed as
        strings using unitless pixels or the ``px``, ``in``, ``cm``, or ``mm`` units.
        If omitted, 10 mm margins are used on every side.
    page_size : PDFPageSize or None, default: PDFPageSize.A4
        Fixed page format used for browser layout, pagination, and PDF generation.
        A fixed format takes precedence over ``width`` and ``height``. Set to ``None``
        to use custom dimensions.
    width : str or float, optional
        Custom page width used when ``page_size`` is ``None``.
    height : str or float, optional
        Custom page height used when ``page_size`` is ``None``.
    render_timeout : float, default: 30.0
        Maximum time, in seconds, for the shared browser render phase once the prepared
        report source is ready to open. This shared budget covers browser launch,
        navigation, readiness waits, and other browser-side preparation steps, but not
        caller-side template rendering or offline-bundle export completed before the
        renderer is invoked.
    ansys_installation : Path or str
        Resolved Ansys installation root used to locate a product-shipped
        Playwright browser binary. Browser-PDF rendering requires this value
        together with ``ansys_version`` and uses the shipped browser cache for
        the render instead of any ambient browser-path override.
    ansys_version : int
        Ansys version associated with ``ansys_installation``. This is used to
        locate ``apex###/machines/...`` runtime assets when the product ships
        Playwright browsers inside the installation tree.
    logger : Any, optional
        Logger used for renderer lifecycle messages.
    """

    _page_size: PDFPageSize | None
    _width: str | float | None
    _height: str | float | None

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
    _DEFAULT_PAGE_SIZE: PDFPageSize = PDFPageSize.A4
    # Mirror Playwright's fixed-format dimensions for internal viewport and pagination calculations.
    _PAGE_DIMENSIONS: dict[PDFPageSize, tuple[str, str]] = {
        PDFPageSize.LETTER: ("8.5in", "11in"),
        PDFPageSize.LEGAL: ("8.5in", "14in"),
        PDFPageSize.TABLOID: ("11in", "17in"),
        PDFPageSize.LEDGER: ("17in", "11in"),
        PDFPageSize.A0: ("33.1in", "46.8in"),
        PDFPageSize.A1: ("23.4in", "33.1in"),
        PDFPageSize.A2: ("16.54in", "23.4in"),
        PDFPageSize.A3: ("11.7in", "16.54in"),
        PDFPageSize.A4: ("8.27in", "11.7in"),
        PDFPageSize.A5: ("5.83in", "8.27in"),
        PDFPageSize.A6: ("4.13in", "5.83in"),
    }
    # The virtual viewport height does not constrain PDF pagination. Its width is derived
    # from the selected oriented content box after caller-configured margins are subtracted.
    _DEFAULT_BROWSER_VIEWPORT_HEIGHT: int = 900
    # Maximum time to wait for all JavaScript to finish rendering, in seconds.
    _DEFAULT_RENDER_TIMEOUT: float = 30.0
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
        page_size: PDFPageSize | None = _DEFAULT_PAGE_SIZE,
        width: str | float | None = None,
        height: str | float | None = None,
        render_timeout: float = _DEFAULT_RENDER_TIMEOUT,
        ansys_installation: Path | str | None = None,
        ansys_version: int | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize the renderer with shared browser-PDF configuration."""
        self._landscape = landscape
        validated_page_size = self._validate_page_size(page_size)
        self._width, self._height = self._validate_custom_page_dimensions(
            page_size=validated_page_size,
            width=width,
            height=height,
        )
        # ``page_size=None`` with no custom pair means "use the default", while
        # a complete pair keeps ``_page_size`` at None for Playwright width/height options.
        self._page_size = (
            self._DEFAULT_PAGE_SIZE
            if validated_page_size is None and self._width is None
            else validated_page_size
        )
        self._margins = self._validate_margins(margins)
        # Validate the selected page and margins before starting Chromium.
        self._printable_page_width_px()
        self._printable_page_height_px()
        self._render_timeout = self._validate_render_timeout(render_timeout)
        if ansys_installation is None or ansys_version is None:
            raise ADRException(
                "Browser PDF rendering requires ansys_installation and ansys_version "
                "to locate the product-shipped browser binary."
            )
        self._ansys_installation = Path(ansys_installation).expanduser()
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

    def _resolve_playwright_browser_binary(self) -> _PlaywrightBrowserBinaryInfo:
        """Return the shipped Playwright browser binary path under the resolved install."""
        self._raise_if_product_line_unsupported()

        binary_info = resolve_playwright_browser_binary_info(
            ansys_installation=str(self._ansys_installation),
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
        try:
            browser_binary_dir = self._resolve_playwright_browser_binary()
            self._logger.info(
                "Using product-shipped Playwright browser binary path: %s",
                browser_binary_dir.path,
            )
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_binary_dir.path)
            yield
        finally:
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
                    # items lay themselves out against the selected page's printable width.
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
                    self._prepare_content_for_pagination(page)
                    pdf_options = {
                        **self._pdf_page_size_options(),
                        "margin": self._margins,
                        "print_background": True,
                    }

                    # Playwright describes page.pdf() as generating paged output, not a bitmap
                    # snapshot of the already-painted viewport. MDN's paged-media model also
                    # distinguishes the continuous-media viewport from the paged page area.
                    # Capture CSS clips horizontal overflow at the printable-width viewport,
                    # while explicit page sizing keeps output dimensions predictable.
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
        except PlaywrightTimeoutError as exc:
            # Keep Playwright's own timeout wording out of the caller-facing error while preserving
            # the original timeout as the chained cause for debugging.
            self._logger.debug(
                "Browser PDF render timed out during %s.", current_timeout_phase, exc_info=True
            )
            raise ADRException(
                f"Browser PDF rendering failed: {current_timeout_phase} timed out after "
                f"{self._render_timeout:.1f}s"
            ) from exc
        except Exception as exc:
            # Keep the caller-facing error ADR-owned while preserving the original browser/driver
            # failure as the chained cause for debugging.
            self._logger.debug("Browser PDF rendering failed.", exc_info=True)
            raise ADRException("Browser PDF rendering failed.") from exc

    def _shared_browser_context_kwargs(self) -> dict[str, Any]:
        """Return browser-context options shared by both offline and live renders."""
        return {
            "viewport": {
                "width": self._browser_viewport_width_px(),
                "height": self._DEFAULT_BROWSER_VIEWPORT_HEIGHT,
            },
            "service_workers": "block",
            "accept_downloads": False,
        }

    def _page_dimensions(self) -> tuple[str | float, str | float]:
        """Return the selected portrait page dimensions."""
        if self._page_size is not None:
            return self._PAGE_DIMENSIONS[self._page_size]

        # Constructor validation makes a half-populated pair unreachable, but
        # keep this runtime guard for subclasses or later internal mutation.
        if self._width is None or self._height is None:
            raise ADRException("Browser PDF custom page dimensions are incomplete.")
        return self._width, self._height

    def _oriented_page_width(self) -> str | float:
        """Return the selected physical page width for the requested orientation."""
        page_width, page_height = self._page_dimensions()
        return page_height if self._landscape else page_width

    def _oriented_page_height(self) -> str | float:
        """Return the selected physical page height for the requested orientation."""
        page_width, page_height = self._page_dimensions()
        return page_width if self._landscape else page_height

    def _page_size_description(self) -> str:
        """Return a concise page-size description for validation errors."""
        return self._page_size.value if self._page_size is not None else "custom"

    def _printable_page_width_px(self) -> float:
        """Return the oriented content-box width after horizontal PDF margins."""
        page_width_px = self._pdf_length_to_px(self._oriented_page_width())
        margin_width_px = self._pdf_length_to_px(self._margins["left"]) + self._pdf_length_to_px(
            self._margins["right"]
        )
        printable_width_px = page_width_px - margin_width_px
        if printable_width_px < 1.0:
            raise ADRException(
                "Browser PDF horizontal margins must leave at least one CSS pixel "
                f"of printable {self._page_size_description()} page width."
            )
        return printable_width_px

    def _browser_viewport_width_px(self) -> int:
        """Return an integer viewport no wider than the PDF content box."""
        return floor(self._printable_page_width_px())

    def _printable_page_height_px(self) -> float:
        """Return the oriented content-box height after vertical PDF margins."""
        page_height_px = self._pdf_length_to_px(self._oriented_page_height())
        margin_height_px = self._pdf_length_to_px(self._margins["top"]) + self._pdf_length_to_px(
            self._margins["bottom"]
        )
        printable_height_px = page_height_px - margin_height_px
        if printable_height_px < 1.0:
            raise ADRException(
                "Browser PDF vertical margins must leave at least one CSS pixel "
                f"of printable {self._page_size_description()} page height."
            )
        return printable_height_px

    def _pdf_page_size_options(self) -> dict[str, str | float | bool]:
        """Return Playwright options for the selected page sizing."""
        options: dict[str, str | float | bool] = {"landscape": self._landscape}
        # Chromium accepts either a named format or explicit dimensions. Never
        # send both, because format is the public precedence rule for this API.
        if self._page_size is not None:
            options["format"] = self._page_size.value
        else:
            options["width"], options["height"] = self._page_dimensions()
        return options

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
        # Earlier ADR report HTML uses ``.avz-viewer`` wrappers and
        # ``.ansys-nexus-proxy`` images, so keep those selectors with the registered tags.
        # Convert each ``__ANSYS_VIEWER__`` placeholder to
        # ``:is(ansys-adr-viewer, ansys-nexus-viewer)`` before injecting the CSS.
        page.add_style_tag(
            content="""
                html,
                body {
                    /* The viewport matches the printable width. Clip wider descendants here so
                       Chromium does not shrink the entire document during PDF pagination. */
                    overflow-x: clip !important;
                }

                adr-data-item,
                .nexus-plot,
                .nexus-plot > .plot-container,
                .js-plotly-plot,
                .plot-container,
                .svg-container,
                .avz-viewer,
                __ANSYS_VIEWER__ {
                    display: block !important;
                }

                adr-data-item,
                .nexus-plot,
                .nexus-plot > .plot-container,
                .js-plotly-plot,
                .plot-container,
                .svg-container,
                .avz-viewer,
                __ANSYS_VIEWER__,
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
                .table-responsive {
                    overflow: visible !important;
                    max-height: none !important;
                }

                .avz-viewer,
                __ANSYS_VIEWER__ {
                    overflow: hidden !important;
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
            """.replace("__ANSYS_VIEWER__", _SCENE_VIEWER_SELECTOR),
        )

        page.add_style_tag(
            content="""
                div[data-layout-type="panel"] {
                    break-inside: auto !important;
                    page-break-inside: auto !important;
                }
            """,
        )
        page.evaluate(
            """() => {
                for (const panel of document.querySelectorAll('adr-panel')) {
                    const shadowRoot = panel.shadowRoot;
                    if (!shadowRoot || shadowRoot.querySelector('style[data-adr-pdf-pagination]')) {
                        continue;
                    }

                    const style = document.createElement('style');
                    style.dataset.adrPdfPagination = '';
                    style.textContent = `
                        section.adr-panel {
                            display: block !important;
                        }

                        header.adr-panel-header {
                            break-after: avoid !important;
                            page-break-after: avoid !important;
                        }
                    `;
                    shadowRoot.append(style);

                    const firstPanelContent = panel.firstElementChild;
                    if (firstPanelContent) {
                        firstPanelContent.style.setProperty(
                            'break-before', 'avoid', 'important'
                        );
                        firstPanelContent.style.setProperty(
                            'page-break-before', 'avoid', 'important'
                        );
                    }
                }
            }"""
        )

    def _prepare_content_for_pagination(self, page: Any) -> None:
        """Fit indivisible visuals and configure vertical pagination boundaries."""
        printable_height_px = self._printable_page_height_px()
        # Later cohesion checks must see post-resize geometry. Fragmentation runs
        # last so structures that still exceed a page can override avoid rules.
        visual_result = self._fit_visuals_for_pagination(page, printable_height_px)
        cohesion_result = self._set_pagination_cohesion(page, printable_height_px)
        fragmentation_result = self._make_oversized_structures_fragmentable(
            page, printable_height_px
        )
        self._log_pagination_preparation(
            visual_result,
            cohesion_result,
            fragmentation_result,
        )

    def _fit_visuals_for_pagination(self, page: Any, printable_height_px: float) -> dict[str, Any]:
        """Resize indivisible visual media to fit within one printable page."""
        return page.evaluate(
            """async (options) => {
                const {
                    printableHeightPx,
                    fitGuardPx,
                    headingSelector,
                    visualSelector,
                    sceneViewerSelector
                } = options;
                const preparedVisuals = new Set();
                const resizedVisuals = [];
                const resizePromises = [];

                const isVisible = element => {
                    const style = window.getComputedStyle(element);
                    return element.getClientRects().length > 0
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };

                const findRenderedVisuals = root => {
                    const visuals = [];
                    const seen = new Set();
                    for (const candidate of root.querySelectorAll(visualSelector)) {
                        // Plotly and the scene viewer can add image or canvas descendants.
                        // Prepare their stable ADR containers instead of internal render nodes.
                        const visual = candidate.closest(
                            `.nexus-plot, ${sceneViewerSelector}`
                        ) || candidate;
                        if (!root.contains(visual) || seen.has(visual) || !isVisible(visual)) {
                            continue;
                        }
                        seen.add(visual);
                        visuals.push(visual);
                    }
                    return visuals;
                };

                const visualLabel = visual => {
                    const id = visual.id ? `#${visual.id}` : '';
                    return `${visual.tagName.toLowerCase()}${id}`;
                };

                const sceneLayoutRoot = viewer => {
                    const item = viewer.closest('adr-data-item');
                    let layoutRoot = viewer;
                    // Current product HTML can place the component inside a sizing element.
                    // Fit the direct slotted root so the same path also handles wrapper-free HTML.
                    while (item && layoutRoot.parentElement
                            && layoutRoot.parentElement !== item) {
                        layoutRoot = layoutRoot.parentElement;
                    }
                    return layoutRoot;
                };

                const prepareSceneViewer = (viewer, layoutRoot, layoutRect) => {
                    if (layoutRect.width < 1) {
                        return;
                    }

                    const configuredAspectRatio = Number.parseFloat(
                        viewer.aspect_ratio ?? viewer.getAttribute('aspect_ratio')
                    );
                    const renderedAspectRatio = layoutRect.height > 0
                        ? layoutRect.width / layoutRect.height
                        : Number.NaN;
                    // Prefer product metadata, then the rendered box, and use a
                    // stable widescreen fallback only when neither is usable.
                    const aspectRatio = Number.isFinite(configuredAspectRatio)
                            && configuredAspectRatio > 0
                        ? configuredAspectRatio
                        : Number.isFinite(renderedAspectRatio) && renderedAspectRatio > 0
                            ? renderedAspectRatio
                            : 16 / 9;
                    layoutRoot.style.setProperty(
                        'aspect-ratio', `${aspectRatio}`, 'important'
                    );
                    layoutRoot.style.setProperty('box-sizing', 'border-box', 'important');
                    layoutRoot.style.setProperty('display', 'block', 'important');
                    layoutRoot.style.setProperty('width', '100%', 'important');
                    layoutRoot.style.setProperty('height', 'auto', 'important');
                    layoutRoot.style.setProperty(
                        'max-width', `${Math.ceil(layoutRect.width)}px`, 'important'
                    );
                    layoutRoot.style.setProperty('overflow', 'hidden', 'important');
                    layoutRoot.style.setProperty('break-inside', 'avoid', 'important');
                    layoutRoot.style.setProperty('page-break-inside', 'avoid', 'important');

                    if (layoutRoot !== viewer) {
                        viewer.style.setProperty('width', '100%', 'important');
                        viewer.style.setProperty('height', '100%', 'important');
                        viewer.style.setProperty('max-width', '100%', 'important');
                        viewer.style.setProperty('max-height', '100%', 'important');
                    }
                    viewer.style.setProperty('overflow', 'hidden', 'important');
                };

                const fitVisual = (visual, groupStart, groupEnd, title) => {
                    if (preparedVisuals.has(visual)) {
                        return true;
                    }
                    const isSceneViewer = visual.matches(sceneViewerSelector);
                    const fittedVisual = isSceneViewer ? sceneLayoutRoot(visual) : visual;
                    const initialVisualRect = fittedVisual.getBoundingClientRect();
                    if (isSceneViewer) {
                        prepareSceneViewer(visual, fittedVisual, initialVisualRect);
                    }
                    const visualRect = fittedVisual.getBoundingClientRect();
                    const responsiveHeightReduction = Math.max(
                        0, initialVisualRect.height - visualRect.height
                    );
                    // Keep the heading, owner chrome, and panel padding in the
                    // same page-height budget as the indivisible visual.
                    const fixedHeight = Math.max(0, visualRect.top - groupStart)
                        + Math.max(
                            0, groupEnd - responsiveHeightReduction - visualRect.bottom
                        );
                    const fittedHeight = Math.floor(
                        printableHeightPx - fixedHeight - fitGuardPx
                    );
                    if (fittedHeight < 1 || visualRect.height < 1 || visualRect.width < 1) {
                        return false;
                    }

                    const computedMaxHeight = Number.parseFloat(
                        window.getComputedStyle(fittedVisual).maxHeight
                    );
                    const existingMaxHeight = Number.isFinite(computedMaxHeight)
                            && computedMaxHeight > 0
                        ? computedMaxHeight
                        : Number.POSITIVE_INFINITY;
                    let constrainedHeight = Math.max(1, Math.floor(Math.min(
                        visualRect.height, fittedHeight, existingMaxHeight
                    )));
                    let constrainedWidth = Math.max(1, Math.ceil(visualRect.width));
                    const wasResized = visualRect.height > constrainedHeight + 0.5;

                    if (wasResized && isSceneViewer) {
                        const aspectRatio = visualRect.width / visualRect.height;
                        constrainedWidth = Math.max(1, Math.floor(Math.min(
                            visualRect.width, constrainedHeight * aspectRatio
                        )));
                        constrainedHeight = Math.max(
                            1, Math.floor(constrainedWidth / aspectRatio)
                        );
                    }

                    fittedVisual.style.setProperty(
                        'max-height', `${constrainedHeight}px`, 'important'
                    );
                    fittedVisual.style.setProperty(
                        'max-width', `${constrainedWidth}px`, 'important'
                    );
                    if (wasResized && isSceneViewer) {
                        fittedVisual.style.setProperty(
                            'height', `${constrainedHeight}px`, 'important'
                        );
                        fittedVisual.style.setProperty(
                            'width', `${constrainedWidth}px`, 'important'
                        );
                    } else if (wasResized && visual.matches('img, video, canvas')) {
                        visual.style.setProperty('height', 'auto', 'important');
                        visual.style.setProperty('width', 'auto', 'important');
                        visual.style.setProperty('object-fit', 'contain', 'important');
                    } else if (wasResized) {
                        visual.style.setProperty(
                            'height', `${constrainedHeight}px`, 'important'
                        );
                    }

                    if (wasResized && isSceneViewer) {
                        const item = visual.closest('adr-data-item');
                        fittedVisual.style.setProperty('overflow', 'hidden', 'important');
                        if (item) {
                            item.style.setProperty(
                                'height', `${constrainedHeight}px`, 'important'
                            );
                            item.style.setProperty(
                                'max-height', `${constrainedHeight}px`, 'important'
                            );
                            item.style.setProperty('overflow', 'hidden', 'important');
                        }
                    }

                    if (wasResized && visual.matches('.nexus-plot')
                            && window.Plotly?.Plots?.resize) {
                        resizePromises.push(Promise.resolve(window.Plotly.Plots.resize(visual)));
                    }
                    preparedVisuals.add(visual);
                    if (wasResized) {
                        resizedVisuals.push({
                            title,
                            visual: visualLabel(visual),
                            originalHeightPx: visualRect.height,
                            fittedHeightPx: constrainedHeight
                        });
                    }
                    return true;
                };

                // Basic layouts own headings and content containers, so fitting
                // against that group keeps a title with its resized visual.
                for (const layout of document.querySelectorAll(
                    'div[data-layout-type="basic"]'
                )) {
                    const heading = layout.querySelector(headingSelector);
                    const container = heading?.nextElementSibling;
                    if (!container?.matches('section.adr-container')) {
                        continue;
                    }

                    const visuals = findRenderedVisuals(container);
                    if (!visuals.length) {
                        continue;
                    }

                    const panel = layout.closest('adr-panel');
                    const panelHeader = panel?.shadowRoot?.querySelector('header.adr-panel-header');
                    const panelBody = panel?.shadowRoot?.querySelector('section.adr-panel-body');
                    const layoutRect = layout.getBoundingClientRect();
                    const panelLayout = panel?.closest('div[data-layout-type="panel"]');
                    const firstVisiblePanelChild = panel
                        ? [...panel.children].find(isVisible)
                        : null;
                    const firstOwner = visuals[0].closest(
                        'adr-data-item, adr-slider-template'
                    ) || visuals[0];
                    const fragmentPaddingPx = panelBody
                        ? Number.parseFloat(window.getComputedStyle(panelBody).paddingBottom) || 0
                        : 0;
                    for (const visual of visuals) {
                        const owner = visual.closest('adr-data-item, adr-slider-template') || visual;
                        const ownerRect = owner.getBoundingClientRect();
                        const includesHeading = owner === firstOwner;
                        const groupStart = includesHeading && panelHeader
                                && firstVisiblePanelChild === layout && panelLayout
                            ? panelLayout.getBoundingClientRect().top
                            : includesHeading
                                ? layoutRect.top
                                : ownerRect.top;
                        fitVisual(
                            visual,
                            groupStart,
                            ownerRect.bottom + fragmentPaddingPx,
                            heading.textContent.trim()
                        );
                    }
                }

                // Panels without the basic-layout wrapper still need their
                // shadow-DOM header included in the available-height budget.
                for (const panel of document.querySelectorAll('adr-panel')) {
                    const panelLayout = panel.closest('div[data-layout-type="panel"]');
                    const visibleChildren = [...panel.children].filter(
                        child => child.getClientRects().length > 0
                    );
                    if (!panelLayout || visibleChildren.length !== 1) {
                        continue;
                    }

                    const panelRect = panelLayout.getBoundingClientRect();
                    const panelHeader = panel.shadowRoot?.querySelector('header.adr-panel-header');
                    for (const visual of findRenderedVisuals(visibleChildren[0])) {
                        fitVisual(
                            visual,
                            panelRect.top,
                            panelRect.bottom,
                            panelHeader?.textContent.trim() || 'Untitled panel'
                        );
                    }
                }

                const reportRoot = document.getElementById('report_root');
                if (reportRoot) {
                    // Catch standalone visuals not owned by either known layout
                    // shape without processing anything already fitted above.
                    for (const visual of findRenderedVisuals(reportRoot)) {
                        if (preparedVisuals.has(visual)) {
                            continue;
                        }
                        const owner = visual.closest(
                            'adr-data-item, adr-slider-template, div[data-layout-type]'
                        ) || visual;
                        const ownerRect = owner.getBoundingClientRect();
                        fitVisual(
                            visual,
                            ownerRect.top,
                            ownerRect.bottom,
                            visualLabel(visual)
                        );
                    }
                }

                await Promise.all(resizePromises);
                await new Promise(resolve => requestAnimationFrame(
                    () => requestAnimationFrame(resolve)
                ));

                return {
                    cappedVisualCount: preparedVisuals.size,
                    resizedVisuals
                };
            }""",
            {
                "printableHeightPx": printable_height_px,
                "fitGuardPx": _PAGINATION_FIT_GUARD_PX,
                "headingSelector": _PAGINATION_HEADING_SELECTOR,
                "visualSelector": _PAGINATION_VISUAL_SELECTOR,
                "sceneViewerSelector": _SCENE_VIEWER_SELECTOR,
            },
        )

    def _set_pagination_cohesion(self, page: Any, printable_height_px: float) -> dict[str, Any]:
        """Keep basic layouts and panels together when they fit on one page."""
        return page.evaluate(
            """(options) => {
                const { printableHeightPx, headingSelector } = options;
                const isVisible = element => {
                    const style = window.getComputedStyle(element);
                    return element.getClientRects().length > 0
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };

                const keptLayouts = [];
                // Avoid a split only when the complete heading-plus-content
                // group fits; forcing it on taller content can create clipping.
                for (const layout of document.querySelectorAll(
                    'div[data-layout-type="basic"]'
                )) {
                    const heading = layout.querySelector(headingSelector);
                    const container = heading?.nextElementSibling;
                    if (!container?.matches('section.adr-container') || !isVisible(layout)) {
                        continue;
                    }
                    const fits = layout.getBoundingClientRect().height <= printableHeightPx;
                    layout.style.setProperty(
                        'break-inside', fits ? 'avoid' : 'auto', 'important'
                    );
                    layout.style.setProperty(
                        'page-break-inside', fits ? 'avoid' : 'auto', 'important'
                    );
                    if (fits) {
                        keptLayouts.push(heading.textContent.trim() || 'Untitled layout');
                    }
                }

                const keptPanels = [];
                // Apply the same fit-sensitive rule at the panel wrapper, which
                // owns the shadow-DOM header and its light-DOM children.
                for (const panel of document.querySelectorAll('adr-panel')) {
                    const panelLayout = panel.closest('div[data-layout-type="panel"]');
                    const visibleChildren = [...panel.children].filter(isVisible);
                    if (!panelLayout || !visibleChildren.length) {
                        continue;
                    }
                    const fits = panelLayout.getBoundingClientRect().height <= printableHeightPx;
                    panelLayout.style.setProperty(
                        'break-inside', fits ? 'avoid' : 'auto', 'important'
                    );
                    panelLayout.style.setProperty(
                        'page-break-inside', fits ? 'avoid' : 'auto', 'important'
                    );
                    if (fits) {
                        keptPanels.push(
                            panel.shadowRoot?.querySelector('header.adr-panel-header')
                                ?.textContent.trim() || 'Untitled panel'
                        );
                    }
                }

                return { keptLayouts, keptPanels };
            }""",
            {
                "printableHeightPx": printable_height_px,
                "headingSelector": _PAGINATION_HEADING_SELECTOR,
            },
        )

    def _make_oversized_structures_fragmentable(
        self, page: Any, printable_height_px: float
    ) -> dict[str, Any]:
        """Allow over-height sliders, items, and tables to split between pages."""
        return page.evaluate(
            """(printableHeightPx) => {

                const breakableSliders = [];
                // Capture CSS initially protects sliders as one unit. Release
                // only over-height containers and their direct row for paging.
                for (const slider of document.querySelectorAll('adr-slider-template')) {
                    const container = [...slider.children].find(
                        child => child.matches('section[id^="slider_container_"]')
                    );
                    if (!container || container.getBoundingClientRect().height <= printableHeightPx) {
                        continue;
                    }
                    container.style.setProperty('break-inside', 'auto', 'important');
                    container.style.setProperty('page-break-inside', 'auto', 'important');
                    const row = container.querySelector(':scope > section.adr-row');
                    if (row) {
                        row.style.setProperty('break-inside', 'auto', 'important');
                        row.style.setProperty('page-break-inside', 'auto', 'important');
                    }
                    breakableSliders.push(slider.dataset.guid || slider.id || 'untitled');
                }

                const breakableItems = [];
                // Over-height tabular items cannot honor break-inside: avoid;
                // release the item, owning layout, and table wrappers together.
                for (const item of document.querySelectorAll('adr-data-item')) {
                    const itemRect = item.getBoundingClientRect();
                    if (itemRect.height <= printableHeightPx) {
                        continue;
                    }

                    item.style.setProperty('break-inside', 'auto', 'important');
                    item.style.setProperty('page-break-inside', 'auto', 'important');
                    const layout = item.closest('div[data-layout-type="basic"]');
                    if (layout) {
                        layout.style.setProperty('break-inside', 'auto', 'important');
                        layout.style.setProperty('page-break-inside', 'auto', 'important');
                    }
                    for (const child of item.querySelectorAll('.table-responsive, table')) {
                        child.style.setProperty('break-inside', 'auto', 'important');
                        child.style.setProperty('page-break-inside', 'auto', 'important');
                    }
                    breakableItems.push({
                        id: item.id,
                        type: item.dataset.itemType || 'unknown',
                        heightPx: itemRect.height
                    });
                }

                return {
                    breakableSliders,
                    breakableItems
                };
            }""",
            printable_height_px,
        )

    def _log_pagination_preparation(
        self,
        visual_result: dict[str, Any],
        cohesion_result: dict[str, Any],
        fragmentation_result: dict[str, Any],
    ) -> None:
        """Log pagination changes that materially affect the generated PDF."""
        self._logger.debug(
            "Prepared %d browser PDF visuals and kept %d layouts and %d panels intact.",
            visual_result["cappedVisualCount"],
            len(cohesion_result["keptLayouts"]),
            len(cohesion_result["keptPanels"]),
        )
        if visual_result["resizedVisuals"]:
            self._logger.info(
                "Fitted over-height browser PDF visuals: %s",
                visual_result["resizedVisuals"],
            )
        if fragmentation_result["breakableSliders"]:
            self._logger.info(
                "Allowed over-height browser PDF sliders to paginate: %s",
                fragmentation_result["breakableSliders"],
            )
        if fragmentation_result["breakableItems"]:
            self._logger.info(
                "Allowed over-height browser PDF items to paginate: %s",
                fragmentation_result["breakableItems"],
            )

    def _pdf_length_to_px(self, value: str | float) -> float:
        """Convert a Playwright PDF length to CSS pixels.

        Examples
        --------
        ``"10mm"`` becomes approximately ``37.795`` CSS pixels, while ``"1in"`` and
        ``96.0`` both become ``96.0``.
        """
        if isinstance(value, bool):
            raise ADRException(f"Unsupported PDF length for browser PDF rendering: {value!r}")
        if isinstance(value, (int, float)):
            number = float(value)
            if not isfinite(number):
                raise ADRException(f"Unsupported PDF length for browser PDF rendering: {value!r}")
            return number
        if not isinstance(value, str):
            raise ADRException(f"Unsupported PDF length for browser PDF rendering: {value!r}")

        match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*", value)
        if match is None:
            raise ADRException(f"Unsupported PDF length for browser PDF rendering: {value!r}")

        number = float(match.group(1))
        unit = match.group(2).lower()
        if unit not in self._PDF_UNIT_TO_PX:
            raise ADRException(f"Unsupported PDF length unit for browser PDF rendering: {value!r}")
        return number * self._PDF_UNIT_TO_PX[unit]

    @classmethod
    def _validate_page_size(cls, page_size: PDFPageSize | None) -> PDFPageSize | None:
        """Validate that a supported fixed page-size enum member or ``None`` was supplied."""
        if page_size is not None and not isinstance(page_size, PDFPageSize):
            supported = ", ".join(size.name for size in PDFPageSize)
            raise ADRException(
                "Browser PDF page_size must be a PDFPageSize member or None; "
                f"supported values are {supported}."
            )
        return page_size

    def _validate_custom_page_dimensions(
        self,
        *,
        page_size: PDFPageSize | None,
        width: str | float | None,
        height: str | float | None,
    ) -> tuple[str | float | None, str | float | None]:
        """Validate custom dimensions when no fixed page format is selected."""
        if page_size is not None:
            return None, None
        if width is None and height is None:
            return None, None
        if width is None or height is None:
            raise ADRException(
                "Browser PDF width and height must be provided together when page_size is None."
            )

        for dimension_name, dimension_value in (("width", width), ("height", height)):
            dimension_px = self._pdf_length_to_px(dimension_value)
            if dimension_px <= 0:
                raise ADRException(f"Browser PDF {dimension_name} must be a positive PDF length.")
        return width, height

    def _validate_margins(self, margins: dict[str, str] | None) -> dict[str, str]:
        """Validate browser-PDF margins and return a private copy."""
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
        except (TypeError, ValueError) as exc:
            raise ADRException(error_message) from exc

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
        # emits during browser-PDF rendering. HTML items and layout ``HTML``
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
    landscape : bool, default: False
        Whether to render the PDF in landscape orientation.
    margins : dict[str, str], optional
        Page margins with ``top``, ``right``, ``bottom``, and ``left`` values expressed as
        strings using unitless pixels or the ``px``, ``in``, ``cm``, or ``mm`` units.
        If omitted, 10 mm margins are used on every side.
    page_size : PDFPageSize or None, default: PDFPageSize.A4
        Fixed page format. Set to ``None`` to use ``width`` and ``height``.
    width : str or float, optional
        Custom page width used when ``page_size`` is ``None``.
    height : str or float, optional
        Custom page height used when ``page_size`` is ``None``.
    render_timeout : float, default: 30.0
        Maximum time, in seconds, for the shared browser render phase once the
        exported HTML bundle is ready to open. This shared budget covers browser
        launch, navigation, readiness waits, and other browser-side preparation
        steps, but not the earlier ADR report render.
    ansys_installation : Path or str
        Resolved Ansys installation root used to locate a product-shipped
        Playwright browser binary. Browser-PDF rendering requires this value
        together with ``ansys_version`` and uses the shipped browser cache for
        the render instead of any ambient browser-path override.
    ansys_version : int
        Ansys version associated with ``ansys_installation``. This is used to
        locate ``apex###/machines/...`` runtime assets when the product ships
        Playwright browsers inside the installation tree.
    logger : Any, optional
        Logger used for renderer lifecycle messages.
    """

    _ENTRYPOINT_FILENAME: ClassVar[str] = "index.html"
    _BLOCKED_REQUEST_SCHEMES: ClassVar[set[str]] = {"http", "https"}
    _BLOCKED_WEBSOCKET_SCHEMES: ClassVar[set[str]] = {"ws", "wss"}

    def __init__(
        self,
        html_dir: Path | str | None,
        *,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        page_size: PDFPageSize | None = _BasePlaywrightPDFRenderer._DEFAULT_PAGE_SIZE,
        width: str | float | None = None,
        height: str | float | None = None,
        render_timeout: float = _BasePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT,
        ansys_installation: Path | str | None = None,
        ansys_version: int | None = None,
        logger: Any = None,
    ) -> None:
        # Normalize the bundle root once so the later entry-point containment
        # check compares resolved absolute paths.
        self._html_dir = None if html_dir is None else Path(html_dir).expanduser().resolve()
        super().__init__(
            landscape=landscape,
            margins=margins,
            page_size=page_size,
            width=width,
            height=height,
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
        context_kwargs = self._shared_browser_context_kwargs()
        context_kwargs["offline"] = True
        return browser.new_context(**context_kwargs)

    def _prepare_context(self, context: Any) -> None:
        """Configure the offline browser context before opening the staged bundle."""
        self._block_external_requests(context)

    def _block_external_requests(self, context: Any) -> None:
        """Keep the offline ``file://`` export self-contained during browser rendering."""

        def route_request(route: Any) -> None:
            request_url = route.request.url
            parsed_url = urlsplit(request_url)
            scheme = parsed_url.scheme.lower()
            # Block both known network schemes and any authority-bearing URL. The netloc check
            # catches protocol-relative URLs like //example.com/file and file:// URLs with
            # hostnames like file://example.com/file that the scheme check alone would miss.
            if scheme in self._BLOCKED_REQUEST_SCHEMES or parsed_url.netloc:
                route.abort()
                return
            route.continue_()

        def is_external_websocket(url: str) -> bool:
            return urlsplit(url).scheme.lower() in self._BLOCKED_WEBSOCKET_SCHEMES

        def route_websocket(websocket_route: Any) -> None:
            websocket_route.close()

        # ADR's offline HTML exporter writes a self-contained file:// bundle. Blocking known
        # network schemes plus any authority-bearing URL prevents staged report HTML from
        # calling back to arbitrary hosts during PDF generation while still allowing local
        # file:, data:, and blob: resources that are part of the offline export.
        # Playwright documents WebSocket routing separately from request routing, so handle ws/wss
        # connections through the dedicated route_web_socket API.
        context.route("**/*", route_request)
        context.route_web_socket(is_external_websocket, route_websocket)

    def _resolve_entrypoint_path(self) -> Path:
        """Return the validated HTML entry-point path that Chromium can open."""
        if self._html_dir is None:
            raise ADRException("Browser PDF HTML directory is not configured for this renderer.")
        entrypoint_path = (self._html_dir / self._ENTRYPOINT_FILENAME).resolve()
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
    offline HTML bundle. This class reuses the shared browser readiness and PDF
    sizing flow while keeping network access enabled for same-page assets.

    Parameters
    ----------
    url : str
        Absolute ADR report URL to open in the headless browser.
    auth_cookies : list[dict[str, object]], optional
        Browser-session cookies to seed into the Playwright context before the
        page is opened.
    landscape : bool, default: False
        Whether to render the PDF in landscape orientation.
    margins : dict[str, str], optional
        Page margins with ``top``, ``right``, ``bottom``, and ``left`` values expressed as
        strings using unitless pixels or the ``px``, ``in``, ``cm``, or ``mm`` units.
        If omitted, 10 mm margins are used on every side.
    page_size : PDFPageSize or None, default: PDFPageSize.A4
        Fixed page format. Set to ``None`` to use ``width`` and ``height``.
    width : str or float, optional
        Custom page width used when ``page_size`` is ``None``.
    height : str or float, optional
        Custom page height used when ``page_size`` is ``None``.
    render_timeout : float, default: 30.0
        Maximum time, in seconds, for the shared browser render phase once the
        live report URL is ready to open. This shared budget covers browser
        launch, navigation, readiness waits, and other browser-side preparation
        steps, but not the earlier server-side report generation work.
    ansys_installation : Path or str
        Resolved Ansys installation root used to locate a product-shipped
        Playwright browser binary. Browser-PDF rendering requires this value
        together with ``ansys_version`` and uses the shipped browser cache for
        the render instead of any ambient browser-path override.
    ansys_version : int
        Ansys version associated with ``ansys_installation``. This is used to
        locate ``apex###/machines/...`` runtime assets when the product ships
        Playwright browsers inside the installation tree.
    logger : Any, optional
        Logger used for renderer lifecycle messages.
    """

    def __init__(
        self,
        url: str,
        *,
        auth_cookies: list[dict[str, object]] | None = None,
        landscape: bool = False,
        margins: dict[str, str] | None = None,
        page_size: PDFPageSize | None = _BasePlaywrightPDFRenderer._DEFAULT_PAGE_SIZE,
        width: str | float | None = None,
        height: str | float | None = None,
        render_timeout: float = _BasePlaywrightPDFRenderer._DEFAULT_RENDER_TIMEOUT,
        ansys_installation: Path | str | None = None,
        ansys_version: int | None = None,
        logger: Any = None,
    ) -> None:
        self._url = self._validate_url(url)
        # Copy the container so later append/remove operations by the service
        # layer cannot change a configured renderer.
        self._auth_cookies = [] if auth_cookies is None else list(auth_cookies)
        super().__init__(
            landscape=landscape,
            margins=margins,
            page_size=page_size,
            width=width,
            height=height,
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
        return browser.new_context(**self._shared_browser_context_kwargs())

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
