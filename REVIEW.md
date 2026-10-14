# Review

- **Created by:** Claude (Opus 4.8), phase 04 post-implementation review
- **Created at:** 2026-08-24
- **Updated at:** 2026-08-24 (phase 06 refresh — reflects final code after the review-fix loop)

## Verdict

Approve. Ready for human review.

The branch was well-built from the start: transactional setup, process-wide NumPy mutation restored on every failure path, fully typed new code, and tests that exercise real behavior. The review loop raised six non-blocking findings plus a documentation-checkpoint item; GPT fixed all of them in commit `b7c8163`, and this refresh verifies each against the final code. No blocking defects were found at any point.

The one item that needed a human decision — removing three PDF methods (`ADR.render_report_as_pdf`, `ADR.export_report_as_pdf`, `Template.render_pdf`) that shipped in stable `v0.10.7` — is now **confirmed by the maintainer** as intended for the unreleased `v1.0.0` major, with the changelog migration note to be added at release time. That was the only gate; it is closed.

**Review-loop findings (all resolved):** NB-1 (validate state ordering), NB-2 (glob guard), NB-3 (api_version failure docs), NB-4 (HTML export docs), NB-5 (Draco rewrite example), NB-6 (double-warning confirmed intentional), DOC-2 (docstring `Raises`). Details and final evidence are under Non-Blocking Issues and Documentation Review.

## Review Basis

- **Branch comparison:** `fix/26r1-bc` against `main`. Merge base `f018720`. Final `git diff main...HEAD` = 25 files, +2124 / -912. This includes the original branch work plus the two review-fix commits `b7c8163` (`fix: address compatibility review findings`) and `dc4a514` (`maint: refresh dependency lock`).
- **Repository evidence inspected:**
  - Production source: `compatibility.py`, `exceptions.py`, `adr_service.py`, `serverless/_compat.py`, `serverless/adr.py`, `serverless/html_exporter.py`, `serverless/template.py`, `utils/html_export_constants.py`, `utils/report_download_html.py`, `utils/report_remote_server.py`.
  - Callers and contracts: `Server.api_version` call sites, `_ansys_version` / `_api_version` usages across `src`, `Server.export_report_as_html` / `export_report_as_pdf`, the low-level documented `serverobj.export_report_as_pdf`.
  - Release history: tags `v0.10.7` (last stable) and `v1.0.0.dev0` (latest, unreleased). Confirmed the removed serverless PDF methods shipped in `v0.10.7`.
  - Docs: `doc/source/serverless/caveats.rst`, `doc/source/lowlevelapi/ServerObject.rst`, `AGENTS.md`, example `00-tagging.py`.
  - Config: `pyproject.toml` (weasyprint/django-weasyprint removed, `link-mode = "copy"`), `.gitignore`, `uv.lock`.
  - Tests: `tests/serverless/test_compat.py`, `tests/serverless/test_adr_setup.py`, `tests/serverless/test_html_exporter.py`, `tests/test_compatibility.py`, `tests/test_report_remote_server.py`, `tests/test_download_html.py`, plus the touched `test_adr.py`, `test_template.py`, `test_report.py`.
- **Focused verification (fresh, final code):**
  - `uv run --extra test python -m pytest tests/serverless/test_compat.py tests/test_compatibility.py tests/test_report_remote_server.py -k "<compat/validation subset>"` → **64 passed**, 1 error (`test_validate_existing`, a pre-existing Docker-only integration test that cannot run without Docker here; unrelated to the branch).
  - `uv run --extra test python -m pytest tests/serverless/test_adr_setup.py tests/serverless/test_html_exporter.py tests/test_download_html.py` → **46 passed**, 13 errors (all the same Docker-initialization fixture failure, environmental; the `test_adr_setup.py` unit tests covering the NB-2 area passed).
- **Planning / execution artifacts:** none present (`FEATURE_SPEC_AND_PLAN.md`, `SPEC.md`, `IMPLEMENTATION_PLAN.md`, `PLAN*.md`, `GPT_EXECUTION_PROMPT.md` do not exist). This review was performed standalone from the branch diff and repository evidence. `REVIEW_FIX_VERIFICATION.md` (phase 05) is present and consistent with this refresh.

## Plan Compliance

Not assessed - no planning artifacts were provided. Absence is recorded, not treated as an issue.

## Blocking Issues

None, at any point in the loop. The public-API removal is permitted by the "unless the app version is unreleased" clause (target is the unreleased `v1.0.0`) and is now maintainer-confirmed.

## Non-Blocking Issues

All six were fixed during the review loop. Each entry keeps the original problem statement for the review trail, then records the final resolution.

### NB-1 — `Server.validate()` set `_api_version` before the check that can raise — RESOLVED

`src/ansys/dynamicreporting/core/utils/report_remote_server.py:338`

Original problem: `validate()` assigned `self._api_version = float(server_info["version"])` before calling the validator, so an unsupported/missing `ansys_version` raised *after* `_api_version` was already cached. That made the `api_version` gate non-idempotent (a second access returned the cached float) and let `_download_report_as_html_bundle` read a stale `self._ansys_version`.

Final code (fixed):

```python
server_info = self.get_api_version()
if "server_name" in server_info:
    self.cur_servername = server_info["server_name"]
ansys_version = validate_supported_server_install_version(server_info.get("ansys_version"))
api_version = float(server_info["version"])
self._api_version = api_version
self._ansys_version = ansys_version
return self._api_version
```

The validator now runs first; both values are computed before either is assigned. A raise leaves `_api_version` and `_ansys_version` untouched, so the gate is idempotent and no stale state can be read downstream. Verified by the passing `test_server_validate_*` and `test_download_html_bundle_*` unit tests.

### NB-2 — `_get_embedded_python_version` guarded the wrong operation against `OSError` — RESOLVED

`src/ansys/dynamicreporting/core/serverless/adr.py:619`

Original problem: only the lazy `Path.glob(...)` call was inside `try/except OSError`; scan errors surface during iteration, outside the guard.

Final code (fixed):

```python
try:
    for runtime_path in runtime_directory.glob("[Pp]ython-*"):
        if not runtime_path.is_dir():
            continue
        match = re.fullmatch(
            r"python-(\d+)\.(\d+)(?:\.\d+)?", runtime_path.name, flags=re.IGNORECASE
        )
        if match:
            return (int(match.group(1)), int(match.group(2)))
except OSError:
    return None
return None
```

The iteration is now inside the `try`, so a real filesystem error returns `None` as intended.

### NB-3 — reading `Server.api_version` now performs full server validation — RESOLVED (documented)

`src/ansys/dynamicreporting/core/utils/report_remote_server.py:197`

The behavior change is intended (reject unsupported servers everywhere). It is now documented: the `api_version` property is annotated `-> float` and carries a `Raises` section for `UnsupportedServerVersionError`, and `validate` (line 338) does the same. Call sites inheriting the new failure mode are unchanged for supported servers (lines 26, 27).

### NB-4 — HTML bundle download rejects servers that do not report `ansys_version` — RESOLVED (documented, behavior kept)

`src/ansys/dynamicreporting/core/utils/report_remote_server.py:955`

The stricter reject behavior is intended and confirmed by `test_download_html_bundle_rejects_missing_connected_server_version`. It is now documented on `_download_report_as_html_bundle` (line 955) and the public `export_report_as_html` (line 1124), both with a `Raises` section. The underlying assumption (every supported line-26/27 server advertises `ansys_version`) is recorded under Assumptions Surfaced.

### NB-5 — string path rewrites lacked input/output example comments — RESOLVED

`src/ansys/dynamicreporting/core/serverless/html_exporter.py:637`, `src/ansys/dynamicreporting/core/utils/report_download_html.py:308`

Both Draco rewrites now carry the example comment:

```python
# Example: "/ansys271/nexus/threejs/libs/draco/" becomes
# "./ansys271//nexus/threejs/libs/draco/"; // is intentional and browser-collapsed.
```

The string transformation now shows representative input and expected output, and states that the double slash is intentional and browser-collapsed.

### NB-6 — duplicate user-facing warnings (`logger.warning` + `warnings.warn`) — RESOLVED (confirmed intentional)

`report_remote_server.py:1016-1017`, `serverless/adr.py:664`, `serverless/adr.py:749`

Confirmed intentional and consistent across the branch: the logger serves operators, `warnings.warn` serves API callers. Left unchanged by design. No further action.

## Backwards Compatibility

Highest-priority axis for this branch.

**Removed public methods (breaking vs last stable release) — maintainer-confirmed intentional for `v1.0.0`:**

| Removed symbol | In `v0.10.7`? | Replacement | Notes |
| --- | --- | --- | --- |
| `serverless.ADR.render_report_as_pdf` | Yes | `render_report_as_browser_pdf` | Playwright, different name/signature |
| `serverless.ADR.export_report_as_pdf` | Yes | `export_report_as_browser_pdf` | Playwright, different name/signature |
| `serverless.Template.render_pdf` | Yes | none direct; render via ADR browser-PDF path | WeasyPrint method deleted |

The browser-PDF replacements did not exist in `v0.10.7`; they were added later on `main`. Upgrading from `v0.10.7` and calling `adr.render_report_as_pdf(...)` now raises `AttributeError`, and the caller must move to `render_report_as_browser_pdf(...)`. This is a real break of a released public API.

Status: the maintainer has confirmed the removal is intended for the unreleased `v1.0.0` major (a breaking removal on a major bump is permitted by the engineering contract's "unless the app version is unreleased" clause and by SemVer), and will add the changelog migration note at release time. The removal is internally consistent: no code in `src` calls the deleted methods, `weasyprint` / `django-weasyprint` are gone from `pyproject.toml` and absent from `uv.lock`, no dangling `weasyprint` imports remain, and `AGENTS.md` was updated to `qtpy, playwright`. This item is closed.

**Untouched public surface (verified safe):** the documented low-level `serverobj.export_report_as_pdf` (`Server.export_report_as_pdf`) still exists and uses the Playwright renderer; it does not call the new validator, so it does not raise `UnsupportedServerVersionError`. `doc/source/lowlevelapi/ServerObject.rst:186` remains accurate.

**Behavior tightening (compatible in the supported window, stricter outside it):** NB-3 and NB-4, both now documented. Both reject servers outside the supported product lines (26, 27) where the old code degraded silently. Inside the supported window there is no observable change.

**New exception is additive:** `UnsupportedServerVersionError` subclasses `ADRException`, so existing `except ADRException` handlers keep catching it. No import-time or constructor-time behavior changed.

**Open question — resolved:** the earlier concern about whether removing WeasyPrint was intended is closed by the maintainer confirmation above. The residual assumption that every supported server advertises `ansys_version` is tracked under Assumptions Surfaced (low risk within the supported window).

## Public API Review

- **`UnsupportedServerVersionError`** (`exceptions.py:87`): well named, subclasses `ADRException`, sets a `detail`, matches the surrounding style.
- **`validate_supported_server_install_version`** (`compatibility.py:237`): clear name beside `get_compatibility_warning_for_install_version`; the "warn" variant returns `str | None`, the "validate" variant returns `str` or raises. Symmetric and intuitive.
- **`render_report_as_browser_pdf` / `export_report_as_browser_pdf`** are now the sole serverless PDF entry points, named consistently with the HTML methods.
- No library or framework exception leaks through the public surface. `_render_template_as_browser_pdf` wraps failures in `ADRException` with the original chained as `__cause__`, keeping implementation details out of the caller-facing error while preserving the trace.
- The new `Raises` documentation on `api_version`, `validate`, `export_report_as_html`, and `_download_report_as_html_bundle` makes the new failure mode discoverable without reading the source.

## Performance / Complexity Review

No algorithmic concerns; unchanged by the fixes.

- `apply_runtime_compatibility_shims` is O(1) attribute/print-option toggling, gated to `product_version == 261`.
- `_import_enve` iterates a fixed 3–4 element candidate list, only during one-time `setup()`.
- `_get_embedded_python_version` globs one directory and returns at the first match (the NB-2 fix did not change complexity, only exception scope).
- `_download_report_as_html_bundle` still removes a redundant network probe by reusing the cached version when validation already ran; `test_download_html_bundle_reuses_cached_connected_server_version` asserts no re-probe.

No time-based waits, retry loops, or quadratic scans.

## Source Documentation Grounding

- The NumPy shim is grounded in NumPy's actual API history: `numpy.string_` was a `numpy.bytes_` alias removed in NumPy 2.0, and `legacy="1.25"` print formatting is a real `numpy.set_printoptions` mode. The gate `_normalize_version(numpy.__version__) >= (2, 0)` limits the print-option shim to NumPy 2.x. `test_apply_runtime_compatibility_preserves_existing_numpy_string_alias` confirms the NumPy 1.x path is a no-op.
- Playwright and qtpy are pinned in `pyproject.toml` (`playwright==1.60.0`, `qtpy>=2.4.3,<2.5.0`) and used through the pre-existing `pdf_renderer.py`; this branch only removes the WeasyPrint alternative.
- No new third-party library was introduced.

## Code Quality / Readability

Strong overall, and the fixes did not regress it.

- `setup()` remains transactional: on failure it resets `ADR._is_setup`, clears `_session`/`_dataset`, restores the NumPy shim, and removes the path it added to `sys.path`.
- `_import_enve` isolates the native-import retry, snapshotting and restoring `sys.path`, `sys.modules`, and `CEI_UDILPATH` between failing candidates.
- `_restore_runtime_compatibility_shims` is idempotent (nulls the callback before invoking) and reused by both failure paths and `close()`.
- The NB-2 fix keeps the function shape and only widens the `try` scope; the NB-5 fix adds two focused comments; the NB-1 fix reorders four lines. All are minimal.
- Comments are behavior- and rationale-focused, not task narration.
- `catch BaseException` in `apply_runtime_compatibility_shims` is intentional and documented (undo the shim on Ctrl-C before re-raising).

## Python Typing Review

Meets the hard typing requirement for added/changed code, and the review loop improved coverage.

- New functions and methods are fully annotated: `validate_supported_server_install_version(...) -> str`; `apply_runtime_compatibility_shims(product_version: int) -> RuntimeCompatCleanup`; `_import_enve(candidate_paths: Iterable[Path]) -> ImportError | None`; `_get_embedded_python_version(...) -> tuple[int, int] | None`; `_get_embedded_python_mismatch_message(...) -> str | None`; `_warn_for_embedded_python_mismatch(self) -> None`; `_restore_runtime_compatibility_shims(self) -> None`.
- Fix-loop additions: `Server.api_version` and `Server.validate` are now annotated `-> float`, and `_download_report_as_html_bundle` / `export_report_as_html` gained fully typed signatures (`report_guid: str | uuid.UUID`, `directory_name: str | os.PathLike[str]`, `query: dict[str, object] | None`, `item_filter: str | None`, `filename: str`, `no_inline_files: bool`, `ansys_version: int | str | None`, `-> None`). These annotations are accurate for the values the methods handle (`directory_name` must accept `Path`, `ansys_version` matches the validator input). `report_guid: str | uuid.UUID` is a defensible if slightly permissive union. `uuid` and `os` are imported, so there is no name-resolution risk. This lands the earlier optional suggestion S-3, which is contract-consistent because the methods were already being changed.
- New type aliases are appropriate: `RuntimeCompatCleanup = Callable[[], None]`; the constant `_NUMPY_STRING_ALIAS_PRODUCT_VERSION = 261` removes a magic number.
- No local-variable annotations, no `cast`, no `type: ignore` added to pass a checker.

## Reuse / DRY / Duplication

- `validate_supported_server_install_version` reuses `install_version_to_product_release` and `is_supported_product_release`.
- `CONTEXT_MENU_PATH` is a single shared constant consumed by both exporters.
- The v261 context-menu copy/download logic is intentionally parallel across the offline exporter and the remote downloader (local static tree vs. remote URL); the shared piece (constant plus file list) is factored out.
- No reinvention of existing helpers.

## Assumptions Surfaced

- **Every supported server advertises `ansys_version`.** NB-4 rejects a server that omits it. Low risk within the supported window (lines 26, 27); recorded so a maintainer who knows the server contract can confirm.
- **`261` is the only product version needing runtime shims.** Encoded as `_NUMPY_STRING_ALIAS_PRODUCT_VERSION = 261`, named specifically for the NumPy string alias.
- **The embedded-Python layout is `apex{version}/machines/{win64|linux_2.6_64}/[Pp]ython-X.Y`.** Best-effort; a `None` result skips the warning, so a wrong assumption degrades gracefully.
- **`link-mode = "copy"` in `pyproject.toml`** assumes the CI/dev environments prefer copying over hardlinking. Tooling-only.

## Assert Usage

Clean. No `assert` statements in the changed production source. The `assert`s in `tests/` are test assertions, which is correct.

## Cross-Platform Review

Safe on Linux and Windows.

- `CONTEXT_MENU_PATH` is combined with `Path` (`self._static_dir / context_menu_path`) and split for local dirs (`CONTEXT_MENU_PATH.split("/")`); both are portable. Where it is a URL, forward slashes are correct.
- `_get_embedded_python_version` selects `win64` vs `linux_2.6_64` from `platform.system()`.
- `setup()` chooses enve candidate dirs per OS.
- No new `os.sep`-sensitive concatenation, shell calls, or hardcoded absolute paths.

**FYI (not a branch defect) — `git diff --check` reports on `adr_service.py`.** `git diff --check main...HEAD` flags "trailing whitespace" on the 9 lines this branch adds to `adr_service.py`. Investigated: the flag is a carriage return (CRLF), not a space or tab. `git cat-file blob` on the raw stored blobs shows `adr_service.py` is CRLF throughout on both `main` (1083 CRLF, 0 LF) and HEAD (1092 CRLF, 0 LF), so the file has always been CRLF and the branch's added lines match that convention. The project's real gates tolerate it: ruff uses `line-ending = "auto"`, the pre-commit `trailing-whitespace` hook preserves the EOL and strips only space/tab (the added lines have neither), and no CI workflow runs `git diff --check`. Recommendation: do not normalize line endings in this branch; a correct fix is a repo-wide normalization (`.gitattributes` with `* text=auto eol=lf`, then `git add --renormalize .`), which is a separate, out-of-scope change.

## Test Review

Good quality. The added tests exercise observable behavior and patch collaborators, not the subject under test. No tests were changed during the fix loop (verified: commit `b7c8163` touched only 4 production files).

- **`tests/serverless/test_compat.py`** fakes `numpy` via `sys.modules` injection (external boundary) and patches `_get_installed_versions` (collaborator), never the functions under test. Covers the NumPy-2 path, the pre-existing-alias no-op, the newer-product no-op, and the partial-rollback-after-failure path.
- **`tests/serverless/test_adr_setup.py`** builds a bare `ADR` and patches `_import_enve`, `_warn_for_embedded_python_mismatch`, `apply_runtime_compatibility_shims`, and `builtins.__import__` (collaborators of `setup()`), then asserts real outcomes: `ImportError` wrapping with the right cause, `sys.path` cleanup, restore callback invoked, `_runtime_compat_restore` reset.
- **`tests/test_compatibility.py`** and **`tests/test_report_remote_server.py`** parametrize the accept/reject matrix for `validate_supported_server_install_version`, and monkeypatch `get_api_version` / `ReportDownloadHTML` (collaborators) to drive `validate`, `get_server_name`, the `api_version` property, and `_download_report_as_html_bundle`. No test patches the function it is testing. Both derive expected versions from `SUPPORTED_PRODUCT_LINES` / `product_release_to_install_version` rather than hardcoding, so they will not rot when the support window advances.
- **`tests/serverless/test_html_exporter.py`, `tests/test_download_html.py`** cover the 26.1 context-menu asset copy/download and directory creation, including partial-tree and missing-file-warning behavior.
- No `time.sleep`, no real network, deterministic with `tmp_path`.
- One classification note: `test_download_html_bundle_reuses_cached_connected_server_version` sets internal attributes and asserts no re-probe — an acceptable contract test of the caching optimization, not a flake risk.

The environment cannot run the Docker-backed integration tests (`test_validate_existing`, the `test_download_*` and several `test_html_exporter` cases fail at fixture setup with "Can't initialize Docker"). That is environmental and pre-existing, not a code defect. New test authoring is deferred to the later focused-tests phase.

## Documentation Review

Documentation checkpoint per material changed behavior, verified against the final code:

- **New failure modes on `validate` / `api_version` / HTML export (NB-3, NB-4, DOC-2):** COMPLETE. `Server.validate`, `Server.api_version`, `_download_report_as_html_bundle`, and the public `Server.export_report_as_html` all now document `UnsupportedServerVersionError` in a `Raises` section. `adr_service.py` already documented it on `get_server`, `start`, and the launch path. `Server.export_report_as_pdf` / `export_report_as_browser_pdf` were correctly left out (they never reach the validator). Durable API reference: `Not applicable` for a Sphinx rebuild — none of these methods are rendered through `autoclass`/`automethod`/`autosummary`, so no reference page changes; the docstrings are the durable developer-facing surface and are now accurate.
- **WeasyPrint PDF removal (DOC-1):** durable API docs remain accurate (the removed serverless methods were never referenced in `.rst`; the untouched low-level `serverobj.export_report_as_pdf` in `ServerObject.rst` still matches the code). The changelog migration note is a maintainer action at release time, confirmed and out of scope here by contract. No inaccurate durable documentation exists on the branch.
- **Dependency change:** `AGENTS.md` export/rendering line is `python-pptx, qtpy, playwright`, matching the WeasyPrint removal. Accurate.
- **Compat shim scope:** `doc/source/serverless/caveats.rst` reads "known product-setting and dependency API transitions", matching `_compat.py` now handling the NumPy shim. Accurate.
- **Unrelated doc edits:** the RST title underlines in `caveats.rst` (`Caveats`) and `00-tagging.py` (`Tagging`) were lengthened by one `=`. Both old and new underlines are valid RST; cosmetic, noted only for scope awareness.

## Suggestions

Optional. Not required for merge.

- **S-1:** a deprecation shim (keep `render_report_as_pdf` as a thin `DeprecationWarning` wrapper over `render_report_as_browser_pdf`) would soften the `v0.10.7` → `v1.0.0` upgrade. The maintainer has chosen the hard removal for the major bump, so this is informational only.
- **S-2:** `_download_report_as_html_bundle` uses `if resolved_ansys_version is None:` as the "no explicit override" sentinel; a one-line comment noting `None` is the sentinel would prevent confusion with `ansys_version=0`/`""`.
- **S-4:** the pre-existing images-path rewrite that NB-5 mirrors could get the same example comment for symmetry.
