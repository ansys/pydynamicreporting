# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.10.8] - <Unreleased>

### Added

- Serverless browser-PDF export now uses the Playwright browser package shipped
  with Ansys 2027 R1 and newer installs.

### Changed

- Serverless browser-PDF export now fails when the expected product-shipped
  Playwright browser package is missing or invalid instead of silently using an
  ambient machine Chromium cache.
- Pinned the Python `playwright` dependency to `1.60.0` to stay aligned with the
  product-shipped browser package.

### Deprecated

-

### Removed

-

### Fixed

-

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
