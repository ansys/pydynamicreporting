# Browser PDF Export Follow-Up Checklist

- [ ] Add best-effort cleanup for the fallback browser-PDF scratch parent after each
      render. Keep using the dedicated fallback parent under
      `Path(tempfile.gettempdir()) / "adr_browser_pdf_scratch"`, but when
      `_db_directory` is not configured and the render path has finished, attempt a
      non-recursive `scratch_root.rmdir()`. Ignore `OSError` so concurrent exports,
      already-removed directories, or stale/non-empty child directories remain safe.
      Do not recursively delete scratch contents; `TemporaryDirectory` should remain
      responsible for the per-render child directory cleanup.

- [ ] Add `Examples` sections to the `render_report_as_browser_pdf()` and
      `export_report_as_browser_pdf()` docstrings, following the existing style used
      by `render_report_as_pdf()` and `export_report_as_pdf()`. The render example
      should show creating an `ADR` instance, calling `setup()`, rendering browser-PDF
      bytes with a report selector such as `name=...`, and writing those bytes to a
      `.pdf` file. The export example should show the direct file-writing API with
      `filename=...`, `name=...`, and optionally `item_filter=...`. Include at least
      one browser-PDF-specific option, such as `landscape=True` or `margins={...}`,
      while keeping the examples concise and consistent with the surrounding
      docstrings.

- [ ] Avoid the duplicate `Template.get(**kwargs)` lookup in
      `export_report_as_browser_pdf()` when `filename` is omitted. Resolve the target
      template once and reuse it for both browser-PDF rendering and the default
      `"<guid>.pdf"` output path, matching the existing `export_report_as_pdf()`
      practice. Keep the public API unchanged. Replace
      `_render_report_as_browser_pdf_impl()` with a private template-oriented helper,
      such as `_render_template_as_browser_pdf(template, ...)`, so
      `render_report_as_browser_pdf()` and `export_report_as_browser_pdf()` each
      resolve the template once and share the browser-PDF staging/export/render
      pipeline without duplicating it. Preserve existing error behavior as much as
      practical. Add or update a focused test verifying that the no-filename export
      path does not perform a second template lookup.

- [ ] Clarify browser context cleanup in `PlaywrightPDFRenderer.render_pdf()`.
      Although the current nested `try`/`finally` structure does not call
      `context.close()` if `browser.new_context(...)` raises, the lifecycle is hard
      to read. Refactor the cleanup so `context` is initialized to `None` before
      creation and closed only when successfully created, or use `contextlib.ExitStack`
      / context manager patterns. Preserve `browser.close()` in a `finally` block and
      add a focused test covering `browser.new_context(...)` failure to ensure the
      original error is reported and browser cleanup still occurs.

- [ ] Add focused unit coverage for browser-PDF validation edge cases. Cover
      `_resolve_entrypoint_path()` traversal protection by constructing a renderer
      with a filename such as `"../../etc/passwd"` and asserting that the
      `is_relative_to()` guard rejects it with an `ADRException`. Also cover
      `_validate_margins()` exact-key validation by passing margins with the required
      `top`, `right`, `bottom`, and `left` keys plus an extra key such as `"extra"`,
      and asserting that the renderer rejects the input instead of silently ignoring
      or forwarding unsupported margin fields.

- [ ] Protect the browser-PDF render pipeline ordering that width computation depends
      on. `_measure_content_width_px()` is only reliable after
      `_apply_pdf_capture_styles()` has already unclipped overflow on Plotly/report
      containers, and the current `render_pdf()` flow intentionally runs
      `_apply_pdf_capture_styles(page)`, then `_wait_for_render_ready(page)`, then
      `_compute_pdf_width(page)`. Add a focused unit test that locks this call order
      in place, and consider tightening the surrounding comments so future changes do
      not accidentally move width measurement ahead of the style injection step.

- [ ] Add focused coverage for the currently untested readiness branches in
      `_wait_for_render_ready()`, especially the ADR-specific DOM signals. In
      particular, add focused coverage for the FOUC transition/body-loaded branches so
      the readiness pipeline is exercised beyond the existing MathJax and Plotly
      timeout-related tests. Keep these tests signal-based and bounded; the goal is to
      lock in the expected DOM signals, not to introduce sleep-based timing tests.

## Core Product Audit Follow-Ups

- [ ] Close the TIFF/GeoTIFF browser-PDF readiness gap. The core-product audit found
      that TIFF image items emit `<img>` elements without a `src` initially and fill
      them asynchronously after GeoTIFF decode, which means the current image wait can
      false-pass because `img.complete` is already `true` on a src-less image. Decide
      whether the near-term consumer fix should detect this case explicitly in the
      browser-PDF renderer or whether it should remain blocked on product-owned
      readiness hooks. In either case, document the limitation clearly until the
      product contract exists.

- [ ] Account for the Plotly theme-mismatch loader overlay in browser-PDF readiness.
      The audit found that `.nexus-plot.loaded` can be set while the
      `.adr-spinner-loader-container` overlay is still visible during theme mismatch
      re-rendering. Follow up by verifying whether the browser-PDF path can hit this
      state and, if so, extend readiness or capture logic so the PDF is not generated
      with a loader still obscuring the plot.

## Nice To Have

- [ ] Harden browser-PDF request blocking for URLs with an external authority.
      Update `PlaywrightPDFRenderer._block_external_requests()` so request URLs with
      a non-empty `urlsplit(...).netloc` are treated as external and aborted, in
      addition to `http`/`https` schemes. This should cover protocol-relative URLs
      such as `"//example.com/asset.js"` and file URLs with an authority such as
      `"file://example.com/asset.js"`, while still allowing local file URLs like
      `"file:///tmp/report/index.html"` plus `data`/`blob` URLs used by the offline
      export. Add focused tests for protocol-relative and authority-bearing file
      URLs. Consider whether the implementation should use an explicit allowlist of
      local/offline schemes such as `file`/`data`/`blob` instead of only blocking
      known external forms.

- [ ] Ensure Chromium-backed browser-PDF renderer tests actually run in CI. The real
      browser tests use `_render_or_skip()` and skip when Playwright's Chromium binary
      is unavailable, which is useful locally but can hide regressions if CI never
      installs the browser. Add a CI step or dedicated job that runs
      `playwright install chromium` (or the repo-approved equivalent) and executes the
      browser-dependent renderer tests in an environment where Chromium is expected to
      be present.

- [ ] Evaluate enabling `tagged=True` for `page.pdf()` in the browser-PDF renderer.
      Playwright supports tagged, accessible PDF output, but this should be tested
      against ADR reports before enabling it by default. Check output size,
      compatibility with existing consumers, and whether Chromium produces meaningful
      accessibility structure from the exported ADR HTML.

- [ ] Evaluate enabling `outline=True` for `page.pdf()` in the browser-PDF renderer.
      Playwright can embed PDF document outlines/bookmarks, but this is only useful if
      ADR's exported headings/report structure produce a navigable outline. Verify the
      generated bookmarks on representative reports before deciding whether to enable
      it by default or expose it as an option.

- [ ] Standardize browser-PDF hooks in the core product so the renderer stops owning
      drifting ADR element vocabularies through hardcoded selector lists. Define
      explicit semantic hooks in the exported HTML for the distinct browser-PDF
      concerns, for example width measurement candidates, break-avoid containers, and
      asynchronous readiness signals. Prefer stable attributes or similarly explicit
      contracts over incidental styling classes. Once those hooks exist, refactor the
      renderer to consume the product-defined contract instead of maintaining separate
      ad hoc selector lists for measurement, CSS capture adjustments, and readiness
      waits. Document the contract so new ADR content types update the shared hooks
      rather than silently bypassing browser-PDF behavior.

- [ ] Log individual browser readiness step durations at debug level. The renderer
      currently logs when the full readiness pipeline starts and completes, but not
      which specific step is slow. Add per-step timing around `_evaluate_ready_step()`
      so slow exports can be diagnosed without adding noise to normal info-level logs.
