# Code Review — `feat/server-browser-pdf-export-clean` vs `main`

**Branch:** `feat/server-browser-pdf-export-clean`
**Base / merge target:** `main` (`545b67f4a`)
**Merge base:** `545b67f4a` — the branch is *even* with `main`, so the diff below is exactly the new work (no rebase drift).
**Feature:** Browser-fidelity PDF export for the **remote ADR service** path (headless Chromium renders the *live* authenticated report page and prints it to PDF), plus a refactor that promotes the Playwright renderer to a shared `utils` module reused by both the serverless and remote paths.
**Review date:** 2026-06-29 · **Updated:** 2026-06-29 for commits `8a97a6728` (split renderer hierarchy), `a953557c8` (privatize renderer internals), `e0db6c74b` (refresh `uv.lock`).

> **What changed since the first review (3 commits):** the renderer was refactored from a *concrete base + subclass* into a clean **abstract base + two concrete siblings**, and every renderer class was privatized. No behavior changed; the tests are pure renames. Details in §4 and the changelog box in §11. **Verdict is unchanged (approve).**

| Metric | Value |
|---|---|
| Files changed | 14 (`+~1.0k / −~0.1k`, plus `uv.lock` churn) |
| Source files | 5 (`adr_report.py`, `serverless/adr.py`, `utils/pdf_renderer.py` *(renamed)*, `utils/report_remote_server.py`, `utils/report_utils.py`) |
| Test files | 6 |
| Doc/meta files | 4 (`CHANGELOG.md`, `caveats.rst`, `00-tagging.py`, `uv.lock`) |
| New public API | `Report.export_browser_pdf(...)`, `Server.export_report_as_browser_pdf(...)` |
| Renderer classes (all private) | `_BasePlaywrightPDFRenderer(ABC)` → `_OfflinePlaywrightPDFRenderer`, `_ReportURLPlaywrightPDFRenderer` |
| `assert` / `print` / `breakpoint` in new source | **none** ✅ |

---

## 1. Scope & method

I aggregated every newly-added change via `git diff main...HEAD`, read the full moved/refactored renderer, and grounded every external-library call against the **installed** sources in `.venv` (Playwright `==1.60.0` `SetCookieParam`/`add_cookies`/`PdfMargins`, and `http.cookiejar.Cookie`). I traced the single production caller of the refactored `run_web_request`, verified `get_auth()`'s real return contract, and confirmed the release status of the moved module. After the three follow-up commits I re-diffed `ea4ebe702..HEAD`: the renderer hierarchy was split/privatized, `pyproject.toml` is unchanged (Playwright still pinned `==1.60.0`, lock churn is transitive), and the test delta is rename-only with **no test added or removed**.

There are **no `*PLAN*.md` files in the repo root.** The de-facto plan for this branch lives in `local_docs/pdfex/` (gitignored): `FOLLOWUP.md` (the working checklist) and `BROWSER_PDF_CORE_AUDIT.md` (an aspirational core-product hook design). The `local_docs/compat/` docs belong to a *different* branch (`maint/djup`) and are not in scope. Section 2 checks the branch against `FOLLOWUP.md`.

---

## 2. Plan compliance (vs `local_docs/pdfex/FOLLOWUP.md`)

**Verdict: compliant. No unexpected divergence.** Every `[x]` item that touches code in this diff is faithfully reflected, and every `[ ]` item is genuinely future/out-of-scope work that this branch does not claim to do.

| FOLLOWUP item | Status | Evidence in this diff |
|---|---|---|
| Clarify browser-context cleanup in `render_pdf()` (`context=None`, guarded close) | ✅ done | `_BasePlaywrightPDFRenderer.render_pdf` (`context=None`, guarded `context.close()`); test `test_playwright_pdf_closes_browser_when_new_context_creation_fails` |
| Plotly theme-mismatch loader overlay in readiness | ✅ done | readiness step 5 waits for `.nexus-plot.loaded` **and** a hidden `.adr-spinner-loader-container` |
| Harden request blocking for authority-bearing URLs | ✅ done | `_block_external_requests` also aborts any URL with a `netloc` |
| Per-step readiness durations at debug level | ✅ done | `_evaluate_ready_step` logs `elapsed_ms` |
| Document browser-PDF limitation for arbitrary HTML | ✅ done | comment block in `_wait_for_render_ready` |
| TIFF/GeoTIFF browser-PDF still broken | ⏳ open (deferred) | not addressed — correctly out of scope |
| Standardize core-product PDF hooks / prune speculative selectors | ⏳ open (deferred) | renderer still uses the legacy hardcoded selector lists (see §5.2) |

**Note on the audit:** `BROWSER_PDF_CORE_AUDIT.md` flags several selectors as "speculative/accidental" (`.js-plotly-plot`, `.svg-container`, `.main-svg`, `.ansys-nexus-proxy`). Those selectors are **pre-existing** (carried over verbatim by the file move, not newly authored here) and their removal is an explicitly **open** FOLLOWUP item. So this is an accepted, documented deferral — not a regression introduced by this branch.

---

## 3. Backwards compatibility — TOP PRIORITY ✅

**Bottom line: this branch is backwards-compatible.** Every change is additive or behavior-preserving.

### 3.1 The renderer move + privatization is safe (verified, not assumed)
`serverless/pdf_renderer.py` → `utils/pdf_renderer.py`, and every renderer class is now underscore-private (`_BasePlaywrightPDFRenderer`, `_OfflinePlaywrightPDFRenderer`, `_ReportURLPlaywrightPDFRenderer`, `_PlaywrightBrowserBinaryInfo`).
- The module is **absent from the latest tag `v1.0.0.dev0`** → it has **never shipped in a release**. No external consumer can depend on the old import path or the old class names.
- A repo-wide search found **zero** lingering references to the old paths/names; the two internal importers were updated (`serverless/adr.py` → `_OfflinePlaywrightPDFRenderer`, `report_remote_server.py` → `_ReportURLPlaywrightPDFRenderer`), both lazy imports.
- None of these classes were ever re-exported from an `__init__.py`. **The privatization actually strengthens the BC story** by making "this is not public API" explicit. (The only remaining module-public name is the helper function `resolve_playwright_browser_binary_info`; it is likewise not re-exported — see Issue H3.)

### 3.2 New public methods are purely additive
`Report.export_browser_pdf` and `Server.export_report_as_browser_pdf` are new. No existing signature changed.

### 3.3 `run_web_request` refactor — contract preserved, failure mode improved
`run_web_request` still returns the `Response` (or `None`). The login flow was extracted into `authenticate_web_session()`. The **only** production caller — `Server.get_file` (`report_remote_server.py:617`) — already guards with `if r is not None:`, so the new graceful `None` (when `get_auth()` returns `None`) is handled correctly. Previously that same input would have raised `TypeError` on tuple-unpacking, so this is a strict robustness improvement, not a regression.

### 3.4 `Server.export_report_as_html` — same signature & behavior
Refactored to delegate to the new private `_download_report_as_html_bundle`. Signature, default `print="html"`, and (pre-existing) mutation of the caller's `query` dict are unchanged.

### 3.5 Low-risk drive-by: `Report.export_pdf` / `export_html` error returns `"" → False`
Two disconnected-state guard paths now return `False` instead of `""` (`adr_report.py:679–682`, `748–751`). Both are falsy and both are `# pragma: no cover`, and the methods are documented to return `bool`, so this is a correctness improvement. **Caveat:** a caller doing `result == ""` (rather than `if not result:`) would observe a change. Risk is negligible but it is an undocumented behavior change bundled into a feature branch (see Issue M3).

> This same hunk also fixes a **latent crash**: those guards previously called `self.service.logger.error(...)` *after* establishing `self.service is None`, which would always raise `AttributeError`. They now use a module-level `LOGGER` (`adr_report.py:53`). Good catch by the author — though it lives in uncovered code.

---

## 4. Architecture & reuse — strong ✅ (improved by the latest refactor)

The standout decision is correct: rather than copy/paste a second renderer for the live-URL path, the branch shares one render pipeline. The **latest refactor made this cleaner**.

**Before (first review):** a *concrete* `PlaywrightPDFRenderer` baked in the offline behavior, and `_PlaywrightReportURLPDFRenderer` subclassed it — so the URL renderer inherited offline-only plumbing it could never use (`html_dir`, `_resolve_entrypoint_path`, an offline `file://` default). That was a mild design smell I noted implicitly.

**After (current):** a proper three-class hierarchy.

| Class | Role |
|---|---|
| `_BasePlaywrightPDFRenderer(ABC)` | Owns the whole render pipeline (launch, readiness, capture CSS, width measurement, shared-deadline timeouts, browser-binary env). Declares three `@abstractmethod` seams. |
| `_OfflinePlaywrightPDFRenderer(_Base…)` | Concrete: stages a `file://` bundle. Owns `html_dir`/`filename`/`_resolve_entrypoint_path`; implements the seams with an **offline** context (`offline=True`) + `_block_external_requests`. Used by serverless `ADR`. |
| `_ReportURLPlaywrightPDFRenderer(_Base…)` | Concrete: renders a **live URL**. Implements the seams with an **online** context + `context.add_cookies(auth_cookies)`. Used by remote `Server`. |

The three seams the subclasses fill in:

| Seam (`@abstractmethod`) | Offline | URL |
|---|---|---|
| `_get_navigation_target()` | `file://…/index.html` URI | the live report URL |
| `_new_browser_context()` | `offline=True` + blocks workers | **online** (network required for live assets) |
| `_prepare_context()` | `_block_external_requests()` | `context.add_cookies(auth_cookies)` |

Why this is better: the base no longer knows about either source kind (it's abstract), the offline-only logic lives only in the offline renderer, and the two concrete renderers are *siblings* rather than one inheriting the other's irrelevant details. The expensive, well-tested pipeline is still written **once** and inherited unchanged — exactly the reuse pattern the task asks me to watch for. The `authenticate_web_session` extraction is likewise DRY: the cookie path reuses the repo's *established* Django login flow instead of reinventing it. Instantiating the ABC directly now raises `TypeError`, which is the intended guard against misuse.

---

## 5. Library/framework usage — grounded in docs ✅ (one note)

### 5.1 Playwright `==1.60.0` (exact pin, unchanged by the lock refresh) — all calls valid against installed source
- `context.add_cookies(Sequence[SetCookieParam])` — verified at `_generated.py:14135`. The cookie dict built by `_build_playwright_cookie` uses exactly the documented keys: `name, value, url|domain+path, expires(float), httpOnly(bool), secure(bool), sameSite∈{Lax,None,Strict}` (`_api_structures.py:50–60`). The `sameSite` guard `in {"Strict","Lax","None"}` matches the `Literal` precisely. **100% grounded.** ✅
- `page.pdf(width, height, landscape, margin, print_background=…)` — snake_case is correct for the Python API; margins match `PdfMargins` keys. ✅
- `new_context(viewport, service_workers="block", accept_downloads, offline)`, `page.goto(wait_until="load", timeout=ms)`, `page.emulate_media(media="screen")`, `context.route` / `context.route_web_socket` — all current, non-deprecated APIs. ✅
- The `page.pdf()` timeout caveat is handled honestly: the code comments that the Python `page.pdf()` has no timeout param and uses the deadline as a *preflight* guard. Accurate.

### 5.2 MathJax readiness still carries a v2 `Hub.Queue` branch
This is **pre-existing** (moved) and self-documented as a removable v1 shim. The audit confirms the core product is MathJax v3/v4-only, so the branch is dead but harmless. Not introduced here; flagging only for the deferred-cleanup backlog.

### 5.3 `http.cookiejar.Cookie` usage is exemplary
`_build_playwright_cookie` reads non-standard attributes via the **public** `has_nonstandard_attr` / `get_nonstandard_attr` accessors and explicitly comments that it avoids private storage. This is the correct, documented API.

---

## 6. Public API review — intuitive & consistent ✅ (one doc gap)

`Report.export_browser_pdf(file_name, query_params=None, item_filter=None, *, landscape=False, margins=None, render_timeout=30.0) -> bool`

- **Naming** is consistent with the existing family: `export_pdf`/`export_html` on `Report` map to `export_report_as_pdf`/`export_report_as_html` on `Server`; `export_browser_pdf` ↔ `export_report_as_browser_pdf` follows the same convention, and aligns with the serverless `ADR.export_report_as_browser_pdf`/`render_report_as_browser_pdf`. ✅
- **Signature** mirrors the siblings (`file_name`, `query_params`, `item_filter` first) and improves on them by making the browser-specific options **keyword-only** (`*`). Good, modern, hard to misuse. ✅
- **Return contract** (`bool`, `False` on any failure, errors logged) matches `export_pdf`/`export_html`. ✅
- The concrete renderer classes are correctly **private** (underscore) — users only ever touch `Report`/`Server`. ✅

**Gap (Issue M1):** `Report.export_browser_pdf` has **no `Examples` docstring section**, while both `export_pdf` and `export_html` do — and `FOLLOWUP.md` explicitly required Examples on the serverless browser-PDF methods. Add one for parity (snippet in §11).

---

## 7. Assumptions surfaced

These are implicit contracts a reviewer/maintainer should know about. None are bugs; the important ones deserve a one-line doc mention.

1. **Client must have a Chromium browser installed for the *remote* path.** Unlike the serverless path (which can use the product-shipped binary via `ansys_installation`/`ansys_version`), the remote `_ReportURLPlaywrightPDFRenderer` passes neither, so `render_pdf()` uses the ambient Playwright browser. Partially documented in the docstrings ("requires a Playwright-managed Chromium browser to be installed on the client machine"). ✅ but see Issue M2 (discoverability of the failure).
2. **The live report page is trusted to reach the network.** The live context deliberately does **not** install `_block_external_requests` (it needs to fetch the report + assets from the running ADR server). Consequence: a live report can also fetch *arbitrary third-party* resources during the render. Seeded session cookies are domain-scoped by the browser, so they do not leak to other hosts. This matches the trust model of a user opening the report in their own browser, but it is a real asymmetry vs. the locked-down offline path and is currently undocumented (Issue L1).
3. **Session cookies have non-`None` string values.** `_build_playwright_cookie` forwards `cookie.value` directly; a valueless cookie (`http.cookiejar` allows `value=None`) would violate Playwright's `value: str`. Django CSRF/session cookies always carry values, so this is theoretical (Issue L2).
4. **`render_pdf()` is single-flight per process.** Inherited assumption — `_playwright_browser_binary_env` mutates `os.environ`. Already documented in that method's docstring; the synchronous driver renders one report at a time. ✅
5. **`build_url_with_query` produces an absolute `http(s)` URL.** `_validate_url` only checks `scheme + netloc`, so it would also accept e.g. `file://host/…`; in practice the URL always comes from the server's own base URL, so this is a sanity guard, not a boundary.

---

## 8. Assertions / anti-patterns — clean ✅

No `assert`, `print`, or `breakpoint` in the new **source**. (The added `assert` lines are all in tests, which is correct.) Errors are normalized to `ADRException`; logging uses module/Service loggers; no credential values are logged. The new abstract base uses `abc.abstractmethod` rather than `assert`/`NotImplementedError`-only stubs — the right tool.

---

## 9. Cross-platform (Linux + Windows) ✅

- Paths use `pathlib` / `os.path.abspath`; the file entry point uses `Path.as_uri()` for a correct `file://` URL on both OSes.
- `output_path.write_bytes(...)` and all new I/O are platform-neutral.
- `_playwright_machine_arch()` handles `win64` / `linux_2.6_64` (pre-existing); the remote path doesn't depend on it.
- Readiness logic runs inside Chromium (OS-independent).
- No hardcoded separators, shell-outs, or POSIX-only calls in the new code.

No cross-platform issues found.

---

## 10. Tests — meaningful and well-targeted, with minor brittleness ✅

**Coverage of new lines looks ≥95%.** Every new branch is exercised. The latest refactor changed **only identifiers** in the tests (`PlaywrightPDFRenderer` → `_OfflinePlaywrightPDFRenderer`, `_PlaywrightReportURLPDFRenderer` → `_ReportURLPlaywrightPDFRenderer`, `PlaywrightBrowserBinaryInfo` → `_PlaywrightBrowserBinaryInfo`); **no test was added or removed**, and the offline tests now correctly instantiate the concrete `_OfflinePlaywrightPDFRenderer` (the base is abstract and cannot be constructed).

| New unit | Covering tests |
|---|---|
| `Report.export_browser_pdf` (success, exception, no-service, no-serverobj) | `test_export_browser_pdf_forwards_options` / `_returns_false_on_failure` / `_without_service` / `_without_serverobj` |
| `Server.export_report_as_browser_pdf` (success, empty filename, render fail, write fail) | `test_export_browser_pdf_renders_live_report_url` / `_requires_file_name` / `_wraps_renderer_failures` / `_wraps_output_write_failures` |
| `_get_browser_auth_cookies` (anonymous, auth-fails, happy) | `_returns_empty_list_without_configured_auth` / `_requires_authenticated_session` / live-render test |
| `_build_playwright_cookie` (domain+path, base-url, raise, expires/httpOnly/sameSite) | `_uses_base_url_when_cookie_has_no_domain` / `_requires_domain_or_base_url` / live-render assertions |
| `authenticate_web_session` (login, no-auth) + `run_web_request` (session, no-session) | 4 focused tests in `test_report_utils.py` |
| `_ReportURLPlaywrightPDFRenderer` + `_OfflinePlaywrightPDFRenderer._resolve_entrypoint_path(None)` + ceil-rounding | 3 focused tests in `test_pdf_renderer.py` |

**Good practices:** all global state (`monotonic`, module attrs) is mutated via `monkeypatch` (auto-restored); no `sleep`-based timing; readiness tests are signal-based; the renderer-rename updates are mechanical and correct.

**Brittleness / maintainability notes (classified):**
- `test_live_report_url_renderer_navigates_to_report_url` asserts `browser.new_context.assert_called_once_with(viewport={…}, service_workers="block", accept_downloads=False)` — **acceptable contract test** (its purpose is to prove the live path stays *online*, i.e. no `offline=True`), but it couples to exact viewport constants. A behavior-level assertion (`"offline" not in kwargs`) would be more durable. *(Issue T1)*
- `test_export_browser_pdf_renders_live_report_url` asserts the full `renderer_auth_cookies` list **and** ~10 other facets in one test — **multiple behaviors per test**, and the exact cookie-dict shape duplicates what the `_build_playwright_cookie` tests already pin. Consider trimming the cookie assertions here to a length/identity check and leaving shape verification to the dedicated tests. *(Issue T2 — violates the "one behavior per test" guideline.)*
- Stubs set `_ansys_version=252` (not a real release). It is unused by the remote browser-PDF path (which doesn't forward a version), so it's harmless but slightly misleading. *(Issue T3, trivial.)*
- `test_authenticate_web_session_logs_in_shared_session` uses **string** credentials, but real `get_auth()` returns **bytes** (`(b"user", b"pass")`). The test verifies orchestration (login → reuse session), not credential encoding, so it's an **acceptable** simplification — noting only for fidelity. *(Issue T4, trivial.)*

No tests assert exact user-facing error *prose* beyond short `match=` substrings on intentional `ADRException` messages (acceptable contract checks). No test mutates env vars without `monkeypatch`. No test depends on packaging layout. **One small gap worth adding** (Issue T5): there is no positive test that `_BasePlaywrightPDFRenderer` cannot be instantiated (`pytest.raises(TypeError)`), which would lock in the new abstract contract.

---

## 11. Issues & suggestions (prioritized)

Nothing here blocks merge. Items are ordered by value.

### Medium

**M1 — Add an `Examples` section to `Report.export_browser_pdf`** (`adr_report.py:769`). Parity with `export_pdf`/`export_html` and the FOLLOWUP doc-style requirement.
```text
        Examples
        --------
        ::

            import ansys.dynamicreporting.core as adr
            adr_service = adr.Service(ansys_installation=r"C:\\Program Files\\ANSYS Inc\\v271")
            adr_service.connect(url="http://localhost:8000", username="nexus", password="cei")
            my_report = adr_service.get_report(report_name="My Top Report")
            ok = my_report.export_browser_pdf(
                file_name=r"D:\\tmp\\myreport.pdf",
                query_params={"colormode": "dark"},
                landscape=True,
            )
```

**M2 — Make the "missing client Chromium" failure actionable.** On the remote path, if the user hasn't run `playwright install chromium`, `playwright.chromium.launch()` raises and is wrapped as a generic `Browser PDF rendering failed: …`. Consider catching the launch error and surfacing a one-line hint (`run 'playwright install chromium' on the client`). This is the single most likely first-run failure for the new public method.

**M3 — Note the `"" → False` return change.** Either add a one-line `CHANGELOG.md` "Fixed" entry for the `Report.export_pdf`/`export_html` disconnected-state return value (and the latent `self.service.logger` crash fix), or leave a code comment. Low risk, but undocumented behavior changes shouldn't ride silently in a feature branch.

### Low

**L1 — Document the live-path network posture.** One sentence in `export_report_as_browser_pdf`'s docstring (or a code comment on `_ReportURLPlaywrightPDFRenderer._new_browser_context`) noting that, unlike the offline path, the live render permits network egress from the report page (assets are fetched live; auth cookies stay domain-scoped). Surfaces assumption #2.

**L2 — Guard `cookie.value is None`** in `_build_playwright_cookie` (`report_remote_server.py:963`) — coerce to `""` or skip the cookie, so a valueless cookie can't violate Playwright's `value: str`. Theoretical for Django, cheap to harden.

**L3 — De-duplicate the `30.0` default.** `render_timeout=30.0` is hard-coded in `Report.export_browser_pdf`, `Server.export_report_as_browser_pdf`, and the renderer's `_DEFAULT_RENDER_TIMEOUT`. Acceptable (public signatures often inline literals to avoid importing a private constant), but worth a comment cross-referencing the source of truth.

### Test (see §10)
**T1** loosen the `new_context` assertion to a behavior check; **T2** split/trim the omnibus live-render test to honor one-behavior-per-test and avoid re-pinning cookie shape; **T5** add a `TypeError`-on-instantiate test for the new abstract base; **T3/T4** trivial fidelity nits.

### Trivial / housekeeping
**H1 — Unrelated changes bundled in.** `00-tagging.py` and `caveats.rst` each only widen an RST title underline (7 → 8 `=`). Harmless and valid RST, but unrelated to browser-PDF — ideally dropped from a feature branch (or noted as a lint sweep).
**H2** — `from typing import Optional` was correctly removed from `adr_report.py` (no remaining uses; replaced by `X | None`). ✅ no action.
**H3 — Lone remaining module-public name.** After privatization, `resolve_playwright_browser_binary_info` is the only non-underscore name left in `pdf_renderer.py`. It is not re-exported, so there's no BC concern, but for consistency consider privatizing it too (or confirm it is intentionally kept callable from elsewhere). Trivial.

---

## 12. Verdict

**Approve — merge-ready after the Medium items (M1–M3), which are documentation/UX, not code-correctness.**

This is a clean, well-architected branch, and the latest refactor improved it: the renderer is now an abstract base with two concrete siblings, and all renderer classes are explicitly private. Backwards compatibility — the stated top priority — is fully preserved: the renderer module + class renames are provably safe (unreleased, no importers, not re-exported), the new methods are additive, and the one refactored function keeps its contract while *improving* a failure mode. External-library usage is pinned (`uv.lock` refresh left Playwright at `1.60.0`) and 100% grounded in the installed Playwright/`http.cookiejar` sources. Reuse via the abstract-base hierarchy is the right call and avoids duplication. Tests are focused and cover the new lines well; the only test debt is some over-coupled assertions, one omnibus test, and a missing abstract-base instantiation guard. Plan compliance against `FOLLOWUP.md` is complete, with the remaining gaps being explicitly-deferred future work.

---

## 13. Resolution — all items addressed (2026-06-29)

Implemented in 11 focused commits (ruff check+format and the smoke test ran clean on each). Non-test items first, then the test items (done after explicit approval, since the standing rule gates test work).

| Item | Status | Commit | Note |
|---|---|---|---|
| **M1** | ✅ | `15ab453c` | `Examples` block added to `Report.export_browser_pdf` in the sibling `::` style, grounded in the real `connect()`/`export_browser_pdf` signatures. |
| **M2** | ✅ revised — see §14 | `577b2ca8`, superseded by `0aff4e8d`/`cf676d755`/`b33fc377` | **Original approach reversed per maintainer feedback.** The "run `playwright install chromium`" hint was wrong: browser-PDF must use the product-packed binary. See §14 for the corrected behavior (packed binary on the remote path + no Playwright info surfaced). |
| **M3** | ✅ | `866fd88e` | CHANGELOG `Fixed` entry for the `""`→`False` return + latent crash fix. |
| **L1** | ✅ | `133e71e9` | Documented the live-path network egress + domain-scoped cookie posture. |
| **L2** | ✅ | `560c2475` (+test `bb866984`) | Value-less cookie value normalized to `""` (Playwright requires `value: str`). |
| **L3** | ✅ | `e79bb965` | Commented the duplicated `render_timeout=30.0` defaults. **Not** collapsed onto `_DEFAULT_RENDER_TIMEOUT`: that would force `adr_report`/`report_remote_server` to import the Playwright-bearing renderer module at load time, defeating the lazy import — a real regression. |
| **T1** | ✅ | `14cfeb98` | `new_context` assertion loosened to the behavior-level "stays online" (`offline` absent from kwargs). |
| **T2** | ✅ | `bb866984` | Omnibus live-render test trimmed to a cookie name/order check; exact shape stays in the dedicated `_build_playwright_cookie` tests. Remaining asserts kept together (one orchestration contract; splitting would duplicate ~50-line setup). |
| **T3** | ✅ | `8055eaef` | Dropped the unused/misleading `_ansys_version=252` stub. |
| **T4** | ✅ | `c3d43c8f` | Stub credentials switched to `bytes` to match `get_auth()`'s real return. |
| **T5** | ✅ | `14cfeb98` | Added a `TypeError`-on-instantiate test for the abstract `_BasePlaywrightPDFRenderer`. |
| **H1** | ✅ | `e7493c12` | Reverted the two unrelated RST-underline edits to `main`. |
| **H2** | ✅ | — | No action needed; the `Optional` import was already removed. |
| **H3** | ✅ | — | **Kept `resolve_playwright_browser_binary_info` public.** It is the module's binary-resolution entry point referenced by ~25 test call sites; privatizing would force mass test edits for no behavior gain. This is the "intentionally callable" branch the item offered. |

**Verification.** 18 focused non-Docker tests pass across `test_report.py`, `test_report_remote_server.py`, and `test_report_utils.py` (browser-PDF / cookie / auth subset). The renderer test module (`test_pdf_renderer.py`) requires Docker via a `scope="module", autouse=True` fixture — unavailable locally — so its new tests were validated via targeted premise checks and throwaway scratch runs of the changed branches; they execute in CI. No push performed.

---

## 14. Round 2 — product-packed binary + zero Playwright leakage (2026-06-30)

Maintainer feedback corrected two things: (a) the remote path must always use the **product-packed** Playwright binary (never tell users to install one), and (b) **callers must never see any Playwright information** — raise ADR errors only, no exception chaining, and dump the trace via the logger.

| Concern | Commit(s) | What changed |
|---|---|---|
| Use packed binary on the **remote** path | `cf676d755` | The remote path passed no install info, so it fell back to an ambient browser. Now `Report.export_browser_pdf` forwards `self.service._ansys_installation`/`_ansys_version` → `Server.export_report_as_browser_pdf(exec_basis, ansys_version)` → `_ReportURLPlaywrightPDFRenderer(ansys_installation, ansys_version)`, mirroring `export_pdf` + the serverless path. A missing packed binary now raises the existing clean, product-oriented `ADRException`. |
| No Playwright in raised errors | `0aff4e8d`, `b33fc377` | Reverted the launch-time install hint. The `render_pdf` timeout + catch-all handlers, and the `Server` / serverless `_render_template_as_browser_pdf` wrappers, now log the trace at debug level and raise clean ADR errors. The catch-all no longer interpolates the raw exception. |
| No exception chaining (incl. traceback context) | `b33fc377` | All those handlers raise `... from None`. Dropping `from exc` alone left `__context__` populated, which tracebacks still print ("During handling of…"); `from None` sets `__suppress_context__` so the underlying Playwright/driver exception never appears. Verified by formatting the traceback (no "playwright", no context chain). |
| No "Playwright" in product messages | `7ae2c6a1` | The unsupported-product-line and missing-binary errors no longer say "Playwright browser binary" — just "browser binary". |
| Tests | `d8e0de1d`, `b33fc377` | Removed the install-hint test; rewrote the launch-failure test to assert a clean message, `__cause__ is None`, `__suppress_context__ is True`, and no "playwright" text; timeout/new-context/wrap tests assert the clean message + suppressed context; added a renderer install-metadata-forwarding test and Server/Report `exec_basis`/`ansys_version` forwarding assertions. |

**Follow-ups settled (`02edaaf0`):**
- **Verified** (not assumed) the remote path uses the packed binary: with a real `apex<ver>/machines/<arch>/playwright-browsers` layout, the live-URL renderer resolves that binary and sets `PLAYWRIGHT_BROWSERS_PATH` to it for the render, then restores the env — no ambient fallback. `service._ansys_installation` is the resolved install root (same value serverless uses and the legacy `exec_basis` plumbing uses).
- **Renamed** the new install argument `exec_basis` → `ansys_installation` (it only echoed the legacy `export_report_as_pdf`; the clear name matches the renderer param + the serverless attribute). Value/flow unchanged; legacy `exec_basis` params left as-is.
- **Scrubbed** "Playwright"/"Chromium" from all four public browser-PDF docstrings (→ "a headless browser"; margins now documented as CSS length strings like `"10mm"`). Verified each public `__doc__` is engine-name-free. Kept internal/private docstrings, comments, and code identifiers (legitimate maintainer-facing references). Left untouched: the non-Playwright exception chains on the Django template-render / PPTX / WeasyPrint paths (out of scope).
