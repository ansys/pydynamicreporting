# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.10.2] - <Unreleased>

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

## [0.10.1] - 2024-04-17

### Added
- New APIs: `set_comments`, `query`, `find`, `iteratorGenerator`, `create_objects`
- Filtering support on report objects
- Deletion support for Report objects via API
- JSON export/import for reports and templates
- Histogram and polar plot export support
- New statistical analysis generator APIs
- New web component: `<adr-report />`
- Serverless mode (BETA) enhancements:
  - Multiple database support
  - Backup and restore capabilities
  - Singleton interface
  - In-memory mode
- New report types and formats: PPTX and SC-DOCX
- Default templates as JSON
- Enhanced image type support (JPG, deep images)
- Offline HTML export with 3D/VR support (three.js, OBJLoader.js)
- Customizable slide layouts (`exclude_from_toc`)
- Natural sorting for sliders
- Support for polar plots and histogram visualizations

### Changed
- Improved serverless APIs and coverage
- Enhanced logging defaults and error reporting
- Lazy loading using `is_setup` flag
- JSON export avoids redundant `put_objects` calls
- Documentation updates:
  - Histogram, polar, and 3D plots
  - JSON handling and serverless usage
  - User-defined layouts
  - `<adr-report />` usage
- Improved compatibility with newer Python versions
- Template editor JSON support and example documentation
- Enhanced image handling and export logic
- Installation detection improvements
- Cheat sheet examples added
- Backward compatibility support for `report_type`
- Added support for row/column tags in table exports

### Fixed
- Fixed HTML export for scenes
- Corrected PDF download path handling
- Ensured Plotly is not ignored in output
- Fixed copying of items and templates
- Resolved session/dataset assignment in `create_item`
- Prevented stalled processes during link checking
- Avoided crashes due to logger misconfiguration
- Fixed offline asset issues in HTML export
- Migrated deprecated `filter` usage to `item_filter`
- Patched `TemplateEditorJSONLoadingError` reference
- Fixed default value errors in install path logic
