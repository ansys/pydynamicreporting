# Follow-up Checklist: MathJax Backward Compatibility

**Branch**: `fix/mathjax_backward_compatibility`
**Base**: `main`
**Reviewed**: 2026-04-02

## Required Follow-up

- [x] Add the missing MathJax 2.x loader to the server-backed export path in `src/ansys/dynamicreporting/core/utils/report_download_html.py`.
  The branch detects MathJax 2.x via `MathJax.js`, but `_download_special_files()` does not currently download `media/MathJax.js`. That leaves the remote-download path incomplete for 2.x offline exports.

- [x] Reconcile the remaining MathJax 2.x asset mismatch between the two export paths.
  `src/ansys/dynamicreporting/core/serverless/html_exporter.py` copies `extensions/HelpDialog.js` and `images/CloseX-31.png`, while `src/ansys/dynamicreporting/core/utils/report_download_html.py` does not. Either add them to the server-backed path or document and test why they are intentionally omitted.

- [x] Make `_download_special_files()` in `src/ansys/dynamicreporting/core/utils/report_download_html.py` version-selective.
  The branch already detects MathJax major version in `_detect_mathjax_version()`, but the downloader still attempts both 4.x and 2.x asset trees and prints expected failures for the non-installed version. It should mirror the serverless behavior: required assets loud, non-applicable assets silent.

- [x] Add tests that lock down the server-backed MathJax asset behavior.
  Cover at least:
  - detected 4.x installs do not emit failures for missing 2.x assets
  - detected 2.x installs include the 2.x loader asset set
  - unknown version still leaves `media/` usable

- [x] Add direct unit tests for `ServerlessReportExporter._detect_mathjax_version()`.
  The serverless path changed materially in this branch and currently has no focused tests for its filesystem-based version detection.

- [x] Finish the file-write cleanup in `src/ansys/dynamicreporting/core/utils/report_download_html.py`.
  `_download_special_files()` now uses a context manager, but `_download_static_files()` still uses `open(filename, "wb").write(data)`. Convert that path to `with open(...)` as well so the fix is consistent.

## Deferred / Optional Review Items

- [x] Shared MathJax constants would improve maintainability, but refactoring both exporters to consume a single source of truth is not required to make this branch correct.
- Caching `_detect_mathjax_version()` in the serverless exporter is harmless, but the current double lookup is not a correctness problem.
- Changing `if` / `if` to `if` / `elif` in `report_download_html.py` is clearer, but it does not change behavior with the current return values.
- Extracting helper functions for repeated copy loops would reduce duplication, but it is cleanup work rather than required follow-up.
- [x] Add directory-creation tests that prove 4.x, 2.x, and unknown installs precreate the intended export tree for both exporters.
- [x] Add the remaining branch-coverage test for a direct `requests.RequestException` in the remote detector.
