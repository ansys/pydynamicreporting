# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.10.5] - <Unreleased>

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

## [0.10.4] - 2025-10-31

### Added
- Added missing template methods and attributes for serverless workflows. ([#420])
- Added validation for the `params` dictionary to ensure safer API usage. ([#431])

### Changed
- Improved HTML export to correctly handle custom URLs and avoid unsafe path resolution. ([#411])
- Moved `docutils` to documentation-only dependencies. ([#426])
- Downgraded certain error logs to warnings when safe to continue. ([#429])
- Replaced print statements with structured logger warnings. ([#423])
- Replaced unsafe `os.getlogin()` calls with `getpass.getuser()` for broader environment compatibility. ([#419])
- Updated `vtk` → 9.5.2 ([#404])
- Updated `ansys-dpf-core` → 0.14.2 ([#428])
- General dependency pinning and cleanup ([#413])

### Fixed
- Corrected item reordering inconsistencies. ([#417])
- Fixed validation issues for tree structures in serverless mode. ([#430], [#432])

### Security
- Implemented Bleach sanitization to prevent XSS injection in Trees and Tables. ([#421])
- Strengthened tree structure validation and fixed related logic errors. ([#430], [#432])
