# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.10.6] - <Unreleased>

### Added

-

### Changed

-

### Deprecated

-

### Removed

-

### Fixed

-

## Security

-

## [0.10.5] - 2025-12-16

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
