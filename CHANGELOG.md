# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0rc2] - 2026-09-04

### Added

- Python 3.14 support on Windows and Linux for connected service mode and
  Serverless ADR with ADR 27.1. For Serverless ADR with ADR 26.1, use Python
  3.12 and the ADR 26.1 constraint profile.

### Maintenance

- Updated the primary CI, build, and pre-commit Python version to 3.14 while retaining CI
  coverage for Python 3.10 through 3.13.

## [1.0.0rc1] - 2026-08-27

### Added

- Browser-fidelity PDF export for both serverless and connected services. Serverless ADR now
  provides `render_report_as_browser_pdf()` (bytes) and `export_report_as_browser_pdf()`
  (file output), while service-mode reports provide `Report.export_browser_pdf()`. Serverless
  exports stage an offline bundle; connected exports render an authenticated live report page
  without changing the shared REST session. Offline exports block external requests; connected live
  exports retain the report page's normal network access. The renderer supports serverless report
  context and dark mode, report query parameters and item filters, landscape output, unit-aware
  margins, and one bounded browser-render timeout covering launch, navigation, readiness, and print
  preparation. It waits for ADR web components, fonts, MathJax, Plotly, images, and videos. Print
  styling keeps headings with their following content; keeps plots, viewers, tables, sliders, images,
  videos, canvases, and responsive charts visible across pages; hides empty headers on collapsed
  tables; improves border contrast; and prevents right-edge clipping by measuring the rendered page
  width, with A4 as the fallback when a wider page is unnecessary. Raw custom asynchronous HTML has
  no separate readiness hook. Browser-PDF export requires
  a configured ADR 27.1 installation and its validated local Chromium bundle rather than a
  machine-wide Playwright cache, restores a caller-provided `PLAYWRIGHT_BROWSERS_PATH` afterward,
  and reports missing or incomplete product browser packages without exposing renderer
  implementation details. Because it temporarily changes that process-wide setting, do not run
  browser-PDF exports concurrently within one process. Cleanup failures do not mask a successful
  export.
- A public `get_compatibility_info()` helper for inspecting the client version, bundled ADR
  release, supported annual product lines, and support policy.
- Serverless `ADR.get_item_count()` and `ADR.get_report_count()` helpers. Report counts include
  only top-level templates, not child templates.
- Serverless `ADR.render_report()` and `Template.render()` now accept `embed_scene_data` to include
  full 3D scene data in rendered HTML when requested. It remains disabled by default because it can
  substantially increase the output size.
- Serverless table items now accept nested numeric sequences, or dictionaries with `array` and an
  optional `dtype`, in addition to existing NumPy arrays. Non-NumPy inputs without a dtype
  normalize to `float64`; existing NumPy inputs retain their prior dtype-validation behavior.
- Service-mode table items now support `table_wrap_word`, enabling smart wrapping at spaces or
  hyphens.
- `log_output` and `log_level` controls on `get_logger()`, `Service`, and serverless `ADR`.
  `log_output` accepts a file path or `"stdout"`; omitting `log_level` leaves the caller's logger
  configuration intact.
- Python 3.13 support.

### Changed

- Established the 1.x client-to-product compatibility policy: version 1.x is bundled with ADR
  27.1 and supports ADR 26.* and 27.*. Install discovery probes 27.1 before 26.1, and
  unsupported local installs emit a clear compatibility warning.
- Expanded the serverless runtime envelope for the two supported ADR product lines: Django
  4.2.27 through 5.x, django-guardian 2.4 through 3.x, Django REST Framework 3.15.2 through
  3.17.x, and NumPy 1.26.4 through 1.x on Python below 3.13 or NumPy 2.x on Python 3.13+.
  Added the ADR 26.1 constraint profile and pinned Playwright to 1.60.0 to match the browser
  package supplied by ADR. External serverless environments targeting ADR 26.1 should install
  with the repository's `constraints/v261.txt` (copy it from GitHub for PyPI installs); the
  compatibility shim is not a substitute for that profile.
- Core, utility, service, and remote-server imports now defer optional Qt/PySide loading until a
  GUI path actually needs it, keeping existing `Item`, `Report`, and `Service` imports available
  to headless and serverless callers.
- Default Docker image references and the pull helper now use the ADR development image instead of
  the legacy Nexus repositories. Serverless Docker setup requires an explicit `docker_image`, tries
  the `/Nexus/ADR` layout before falling back to `/Nexus/CEI`, and documents how to build a local
  Linux image. Service-mode Docker launch reads the product version discovered in the container and
  emits a compatibility warning when it is outside the supported `26.*` and `27.*` lines.

### Deprecated

- `logfile` is deprecated in favor of `log_output`. Existing positional `logfile` calls continue
  to work and issue a `DeprecationWarning`; passing both arguments raises `ValueError`.

### Removed

- The legacy serverless `ADR.render_report_as_pdf()`, `ADR.export_report_as_pdf()`, and
  `Template.render_pdf()` APIs, along with their `django-weasyprint`/`weasyprint` backend.
  Browser-PDF export requires a configured ADR 27.1 installation; serverless PDF rendering is no
  longer available for ADR 26.1. For serverless browser-PDF export, configure `static_directory`
  with the report's static assets.
- VNC-dependent geometry handling, including EVSN and ENS proxy-image extraction and their
  associated calls and test data. AVZ, UDRW, SCDOC/SCDOCX, and DSCO geometry paths remain.
- Qt translation calls for UI messages as part of the language-support removal; UI text is now
  supplied directly in English.

### Fixed

- Distribution artifacts now use Core Metadata 2.4 so Poetry/pkginfo-based environments that do
  not yet support 2.5 can inspect and install the wheel correctly.
- Static HTML export now handles legacy Latin-1 responses, detects and copies the MathJax 4.x asset
  tree referenced by the report while retaining legacy MathJax 2.x layouts, creates required output
  directories on demand, preserves print styles, and avoids reprocessing already rewritten relative
  paths. Remote HTML
  export derives the static-asset version from the connected server when no override is supplied.
  Explicit asset-version overrides remain authoritative, continue if the best-effort server-version
  probe fails, and warn on a mismatch. Exports retain viewer, context-menu, and Draco assets,
  rewrite both quote styles of offline Draco decoder paths, and issue diagnostics for incomplete
  remote legacy assets. Connected static HTML export no longer mutates the caller-provided query
  dictionary while adding `print=html`.
- Product-settings initialization failures now restore partial compatibility shims and import-path
  additions. Later serverless setup failures reset ADR session/setup state and restore shims while
  preserving the original exception. Setup warns about embedded-Python version mismatches,
  cleans up failed `enve` imports between candidate installations, restores the ADR 26.1 NumPy 2
  compatibility state on teardown, handles inaccessible embedded-Python runtime directories, and
  initializes in-memory `collectstatic` correctly on Django 5.1+.
- Connected-server validation now raises `UnsupportedServerVersionError` for missing, malformed,
  or unsupported product versions and caches neither API nor product version until both validate.
  Local database version ceilings follow the resolved product installation. Install, launcher, and
  geometry-converter resolution consistently use supported paths and `exec_basis`, including clear
  handling for missing version settings and retriable geometry rebuilds. Local launch suppresses a
  Windows garbage-collection handle race when its monitor is intentionally left running, and a
  permission failure releases the launch lock.
- `get_logger()` now uses the `ansys.dynamicreporting.core` logger, no longer forces it or the
  application root logger to `ERROR`, and avoids duplicate ADR-owned output handlers.
- Disconnected report helpers no longer crash while logging: `get_guid()` still returns an empty
  string, while `export_pdf()` and `export_html()` now return `False` rather than `""`.
- Object-copy upload fallback now returns a valid response object when `requests` or `urllib3`
  raises during an upload. Best-effort cleanup of ADR-created temporary directories, copied Docker
  tar files and launcher resources, and serverless image handles no longer masks a successful
  result or the primary operation error.

### Security

- HTML, static-asset, MathJax, and report/PPTX download paths now use 300-second request timeouts.
  Static-asset, MathJax, and report/PPTX payloads are read through streamed response iteration in
  64 KiB chunks.

### Maintenance

- Updated developer/test dependencies to PyVista 0.48.4, VTK 9.6.2, and ansys-dpf-core 0.16.1;
  replaced the Black, isort, Flake8, and pyupgrade hooks with Ruff; added license-header enforcement;
  set Python 3.13 as the pre-commit default; configured `uv` to use copy link mode; and added a
  10-day Dependabot cooldown.
- Development install and test targets now rely on `uv sync` instead of a second `pip install -e`,
  avoiding stale distribution metadata.
- Updated CI and release tooling: `docker/login-action` 3 to 4.5.2,
  `actions/download-artifact` 6 to 8, `actions/upload-artifact` 5 to 7,
  `actions/checkout` 5 to 7.0.1, `codecov-action` 5 to 6, `anchore/sbom-action` 0.20.9 to 0.24.0,
  and `pypa/gh-action-pypi-publish` 1.13.0 to 1.14.0.
  `ansys/actions` is now 10.3.2 generally and 10.3.6 in the SBOM workflow. The new
  linked-work-item workflow uses `actions/github-script@v9`. Release workflows use one full tag
  checkout, and the release helper resolves the Hatch version through `uv run`. The
  linked-work-item workflow supports the current Azure DevOps URL. New pull requests must link a
  TFS or Azure DevOps work item with a closing keyword, and CI uses the ADR-supplied browser instead
  of installing Playwright separately.
- Refreshed package and project metadata: the package now uses the SPDX `MIT` license expression
  and explicitly includes `LICENSE`; contributor guidance, author/copyright records, and the
  security reporting contact were updated.

## [0.10.7] - 2026-03-12

### Changed

- Raised the minimum supported `urllib3` version to `2.6.3`.

## [0.10.6] - 2025-12-16

### Added
- PPTX export improvements: added export_report_as_pptx and font control properties for PPTX exports.
- Add Support for Predictor Variable List Length for Template Editor Compatibility
- Add API docs for serverless ADR functions.
- [BETA] PDF export utilities: added render_pdf, render_report_as_pdf and export_report_as_pdf to enable programmatic PDF rendering and exporting of reports through serverless ADR.

### Changed
- HTML exporter: multiple updates and fixes to the HTML exporter and documentation; improved handling of static/media URLs and MathJax.
- Update django to 4.2.27

### Fixed
- Tree validation: fixed several issues in tree validation logic.
- Export defaults and filenames: fixed default filename behavior for PPTX/PDF exports.
- Fix copying of template subtrees in serverless mode.
- Suppress warnings coming from urllib3
- Improve error messages in template parameter validation.

## [0.10.4] - 2025-10-31

### Added
- Added missing template methods and attributes for serverless workflows.
- Added validation for the `params` dictionary to ensure safer API usage.

### Changed
- Improved HTML export to correctly handle custom URLs and avoid unsafe path resolution.
- Moved `docutils` to documentation-only dependencies.
- Downgraded certain error logs to warnings when safe to continue.
- Replaced print statements with structured logger warnings.
- Replaced unsafe `os.getlogin()` calls with `getpass.getuser()` for broader environment compatibility.
- Updated `vtk` → 9.5.2
- Updated `ansys-dpf-core` → 0.14.2
- General dependency pinning and cleanup

### Fixed
- Corrected item reordering inconsistencies.
- Fixed validation issues for tree structures in serverless mode.

### Security
- Implemented Bleach sanitization to prevent XSS injection in Trees and Tables.
- Strengthened tree structure validation and fixed related logic errors.
