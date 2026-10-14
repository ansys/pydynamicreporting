# GPT Review-Fix Prompt — `fix/26r1-bc`

- **Created by:** Claude (Opus 4.8), phase 04 post-implementation review
- **Created at:** 2026-08-24
- **Updated at:** 2026-08-24

You are GPT performing the review-fix pass on the `fix/26r1-bc` branch of `pydynamicreporting`. Fix every valid finding in `REVIEW.md` and stop only with fresh verification evidence or a concrete blocker.

## Skills

Use only these skills, as supporting procedures:

- [incremental-implementation](https://github.com/viseshrp/ai-skills-archive/blob/main/archives/addyosmani__agent-skills/snapshot/skills/incremental-implementation/SKILL.md)
- [source-driven-development](https://github.com/viseshrp/ai-skills-archive/blob/main/archives/addyosmani__agent-skills/snapshot/skills/source-driven-development/SKILL.md)
- [verification-before-completion](https://github.com/viseshrp/ai-skills-archive/blob/main/archives/obra__Superpowers/snapshot/skills/verification-before-completion/SKILL.md)
- [receiving-code-review](https://github.com/viseshrp/ai-skills-archive/blob/main/archives/obra__Superpowers/snapshot/skills/receiving-code-review/SKILL.md)
- [no-ai-slop](https://github.com/viseshrp/ai-skills-archive/blob/main/archives/petergyang__no-ai-slop/snapshot/skills/no-ai-slop/SKILL.md), including its required [eval.md](https://github.com/viseshrp/ai-skills-archive/blob/main/archives/petergyang__no-ai-slop/snapshot/skills/no-ai-slop/eval.md)

## Skill Handling Rule

- Use only the explicitly linked skills listed above.
- The prompt is the contract. When locked task artifacts are present, they are the contract for execution.
- When prior planning or execution artifacts are absent, proceed from `REVIEW.md`, `WALKTHROUGH.md`, and the current branch diff.
- Skills are supporting procedures only.
- If a skill conflicts with this prompt, this prompt wins.
- If a conflict is material, stop and ask instead of silently choosing.
- Never use a skill to expand scope, add architecture changes, add tests, add unrelated refactors, or override the explicit instructions here.
- Treat `no-ai-slop` as a hard requirement for every Markdown document this phase creates or revises, and as the ultimate writing guide for prose and presentation.
- Apply `no-ai-slop` while drafting, run its `eval.md` self-check before saving each Markdown artifact or sending the final response, and stop before creating or revising Markdown if its `SKILL.md` or `eval.md` cannot be read and applied.
- Let `no-ai-slop` win over conflicting writing-style guidance, while this prompt and any available locked task artifacts continue to control scope, meaning, required structure, artifact names, constraints, and evidence.
- Ignore `no-ai-slop`'s draft-request, detection-mode, and mandatory `What changed` workflow unless this prompt explicitly asks for them.

## Engineering Contract

Use this contract as the single shared engineering standard for this fix pass.

### Plan adherence

- If there is a plan, and only when a plan is provided explicitly, follow the plan exactly.
- No divergence. No creativity. No architecture changes. Just execute what is written.
- If the plan, code reality, or request conflicts with another instruction, stop and ask.
- If you have questions, cannot make a decision, do not have enough context, or hit conflicts, DO NOT MAKE ASSUMPTIONS. STOP. ASK. GET CONFIRMATION. THEN PROCEED.

### Scope control

- Do not change, refactor, or reorganize unrelated code unless absolutely necessary.
- Suggestions to improve surrounding code are welcome, but put them in a separate "Not Doing / Suggestions" section instead of implementing them.
- Ignore DevOps, packaging, building, and test-related work unless otherwise specified in the plan or prompt.
- Keep UI changes local to UI code only. Do not touch other code for UI changes unless the plan explicitly requires it.
- Match existing style guidelines.
- Do not write the changelog.

### Performance and complexity

- No time-based waiting hacks. No hacky retry loops.
- Keep a check on algorithmic time and space complexity. Use the best solution after weighing options.
- Do not choose brute-force or quadratic operations unless the plan explicitly justifies them and the data size makes them safe.
- Write code with readability in mind. Prefer readability over overly complicated changes for performance.
- If a requested change reduces performance, stop and say so before implementing it.
- Explain performance concerns so a junior developer can understand them.

### Dependencies, frameworks, and documentation grounding

- No third-party libraries without explicit approval.
- If a third-party library is approved, check usages against the correct documentation and ground them 100% in documentation.
- Always ground library work 100% in documentation with zero assumptions.
- If documentation is poor, find the library's open-source code, clone it in a temporary folder, and read it thoroughly.
- Make sure usages use the latest APIs. Flag outdated APIs.
- Check that library/framework usages are justified and not unnecessary.

### Public APIs and exceptions

- Changes in user-facing APIs must be backwards compatible, unless the app version is unreleased.
- If a third-party library is used in a public-facing API, the user should never see library/framework-specific exceptions raised.
- Use custom errors/exception classes instead. Reuse existing classes or create custom ones if needed.
- Do not chain exceptions when doing so would expose implementation/library details to users.
- If logging is available, dump the trace via the logger for debugging.
- If changes touch or add public APIs, ensure they are user-friendly, intuitive, blend with the existing API set, and are named properly.

### Code quality and maintainability

- Reuse existing code wherever possible. Keep code DRY. Follow separation of concerns and single responsibility.
- Use proper imports. Do not load files as blobs and execute the code within another block.
- Do not use assert statements in production code. Asserts are allowed only in test files.
- Surface all assumptions.
- If changes reinvent or duplicate something already in the source, stop and flag it.
- Do not hardcode numbers, versions, or other constants. Reuse existing constants, or create new constants in the right places and reuse them.

### Types

- Use correct types. Keep type declarations proportionate and readable.
- Do not use filler types, overly generic types to satisfy a checker, `type: ignore` to pass CI temporarily, or `typing.cast`/casts just to satisfy type checkers.

### Python

Apply when the target repository uses Python (it does).

- Every parameter, including `*args` and `**kwargs`, and return value of an added or changed function or method must have an explicit, accurate type hint. Treat `self` and `cls` as implicit.
- Every added or changed class variable, class attribute, instance attribute, and module-level mutable or optional state must have an explicit, accurate type hint. A trivial immutable module constant may remain inferred unless the type checker needs an annotation.
- Declare instance-attribute types at class scope where feasible; do not add `self.attribute: Type` annotations inside a method merely to satisfy this.
- Do not type annotate local variables inside function or method bodies. Add a local annotation only to resolve a real configured type-checker error.
- Keep required annotations simple and accurate. Do not add advanced type constructs or type-only refactors unless the type checker requires them.

### Comments and documentation

- Add brief, detailed comments where they make the code easier to understand. Comments address the code itself, not the task.
- Cleaning up stale comments is encouraged. Add comments for every non-obvious change. Avoid bloated comment blocks.
- Always update related documentation. Find the correct docs folder by backtracking from CI workflows, Makefiles, or docs-build config. Append to the right sections or create new ones.
- Do not write the changelog.

### Documentation checkpoint

- Documentation is a required completion checkpoint at every stage, not end-of-task cleanup.
- Before a checkpoint passes, identify the user-, operator-, API-, configuration-, or developer-facing documentation affected by the changed behavior.
- Require the exact durable documentation files/sections, their in-change-set update, and applicable docs build, link check, rendering check, or focused validation; if no durable documentation change is needed, require an evidence-based `Not applicable` decision.
- Code comments, commit messages, and workflow artifacts do not substitute for durable documentation. Do not write the changelog unless explicitly requested.

### Cross-platform behavior

- All changes must be strictly cross-platform and work on both Linux and Windows. Mac is not a concern.

### Git and verification

- Commit often and incrementally in small increments. Split large commits into sensible parts. Add detailed commit messages explaining what you are doing.
- Do not claim work is complete without fresh verification evidence.
- Run linter and smoke test on every commit, unless the prompt forbids command execution.
- If a command fails, paste the exact error/log back. Never paraphrase logs.

### Tests

- Do not author tests in this fix pass unless explicitly asked. Review-only for tests.
- Run only focused existing tests or checks needed to verify fixes; do not manually run the entire suite.
- Defer all test authoring to the final focused-tests phase.

## Prompt

### Goal

Fix all valid review findings from Opus in `REVIEW.md`, and stop only when you have fresh verification evidence or a concrete blocker.

### Success criteria

- Each implemented fix is validated against the actual review finding and the current code.
- All valid findings in `Blocking Issues` and `Non-Blocking Issues` are fixed, including minor non-blocking issues.
- Scope stays within the review contract and, when available, the original implementation contract.
- Backwards compatibility is preserved.
- Each fixed or retained material behavior completes its documentation checkpoint: applicable durable documentation is updated and validated in the same change set, or an evidence-based `Not applicable` decision is reported.
- Verification evidence is reported clearly.
- Any workflow-generated Markdown artifacts created or updated during the workflow remain in the target repo root and are never moved to subdirectories or alternate paths.
- Any workflow-generated Markdown artifacts created or updated during the workflow include `Created by`, `Created at`, and `Updated at` metadata, with `Updated at` refreshed on every edit.
- Workflow-generated Markdown artifacts are not staged or committed unless explicitly requested.
- The fix pass stages changes, commits them, pushes the branch, and creates a pull request only if the current branch does not already have one.

### Context to read before acting

- `REVIEW.md` (the findings you must fix; authoritative for this pass).
- `WALKTHROUGH.md` (line-by-line explanation of every change on the branch).
- `FEATURE_SPEC_AND_PLAN.md`, if present.
- `GPT_EXECUTION_PROMPT.md`, if present.
- The current branch diff against `main` (`git diff main...HEAD`).

The planning and execution artifacts are optional inputs. When present, treat them as authoritative per this prompt. Their absence is not a blocker and must not trigger a request for them. As of this writing none of the optional planning/execution artifacts exist in the repo; proceed from `REVIEW.md`, `WALKTHROUGH.md`, and the branch diff.

### Execution posture

- Understand the context of the current branch or PR before editing.
- Inspect the actual code and review artifacts before deciding whether a finding is valid.
- Read likely relevant files in parallel before editing when that shortens the loop.
- Prefer dedicated repo/search/edit tools over raw shell when available.
- Carry through implementation and focused verification without waiting for step-by-step approval unless blocked.

### Constraints

- Do not blindly implement every review comment; verify each against the code first.
- Address all valid review findings in `Blocking Issues` and `Non-Blocking Issues`.
- Do not implement optional items from `Suggestions` unless explicitly approved.
- Keep all fixes within the scope established by `REVIEW.md` and the current branch diff; when the original implementation scope can be established from available planning artifacts, preserve it too.
- Preserve plan scope when a plan is available.
- Preserve backwards compatibility.
- Workflow-generated Markdown artifacts belong only in the target repo root using their exact required filenames.
- Workflow-generated Markdown artifacts must include `Created by`, `Created at`, and `Updated at` metadata, preserving the creation fields after first write and updating `Updated at` on every edit.
- No architecture changes. No unrelated refactors. No tests unless explicitly asked.
- Treat a valid documentation-checkpoint gap as a required review fix: update and validate the durable documentation in the same change set, or stop and ask if the required change would exceed the approved scope.
- Stop and ask on ambiguity, conflict, or context gaps.

### Findings to fix (from `REVIEW.md`)

Read `REVIEW.md` for the full evidence and failure scenarios. In brief, the valid findings are:

- **NB-1** — `Server.validate()` (`report_remote_server.py:332`) assigns `self._api_version` before the `validate_supported_server_install_version(...)` call that can raise, leaving inconsistent state and a non-idempotent version gate. Fix: compute the validated `ansys_version` first, then assign `_api_version` and `_ansys_version` together, so a raise leaves `_api_version` untouched.
- **NB-2** — `_get_embedded_python_version` (`serverless/adr.py:619`) wraps only the lazy `Path.glob(...)` call in `try/except OSError`; scan errors surface during iteration, outside the guard. Fix: move the iteration inside the `try` (or wrap the `for` loop) so a real filesystem error returns `None` as intended.
- **NB-3** — Behavior change: reading `Server.api_version` now runs full `validate()` and can raise `UnsupportedServerVersionError`. Fix: document the new failure on the `api_version` property and `validate` docstrings (`Raises`), consistent with the DOC-2 checkpoint.
- **NB-4** — Behavior change: `_download_report_as_html_bundle` rejects servers that do not report `ansys_version` instead of falling back to the client version. This is intended; ensure the docstrings of `_download_report_as_html_bundle` and `Server.export_report_as_html` document `UnsupportedServerVersionError` (DOC-2). Do not revert the behavior. If you believe the old fallback should be preserved, stop and ask.
- **NB-5** — Add an input/output example comment for the Draco asset-path rewrites in `serverless/html_exporter.py:637` and `utils/report_download_html.py:305`, noting the intentional `//` and a concrete before/after.
- **NB-6** — Duplicate `logger.warning` + `warnings.warn` at `report_remote_server.py:999`, `serverless/adr.py:664`, `serverless/adr.py:749`. This is likely intentional. Verify against the code; if intentional and consistent, keep it and record that as the resolution. Do not remove either surface without confirming intent — if you think one should go, stop and ask.
- **DOC-2** — Add `UnsupportedServerVersionError` to the `Raises` sections of `Server.validate`, `Server.export_report_as_html`, and `_download_report_as_html_bundle` docstrings only. Do **not** add it to `Server.export_report_as_pdf` or `Server.export_report_as_browser_pdf`: verified in `report_remote_server.py:1224`, `export_report_as_pdf` uses Qt `NexusPDFSave` or the external `report_save_pdf` utility and never reaches `validate` / `api_version` / `_download_report_as_html_bundle` / the validator (`build_url_with_query` does not touch `api_version`), so it cannot raise that exception. Do not make any PDF method validate the server; that would be an unapproved behavior change.

Do not act on `DOC-1` (changelog migration note for the removed WeasyPrint PDF methods) as a code change: writing the changelog is out of scope per the contract. Record it under Documentation Checkpoints as a release-owner action with an evidence-based note. Do not implement the `Suggestions` (S-1..S-4) unless explicitly approved.

### Per-review-item process

1. Verify the review item against the actual code.
2. Determine whether it is valid.
3. Implement every valid fix from `Blocking Issues` and `Non-Blocking Issues`, including minor nits that are still valid issues.
4. Complete the documentation checkpoint for the changed behavior before treating the review item as fixed.
5. Do not implement items from `Suggestions` unless explicitly approved.
6. If a review item is wrong, stale, or conflicts with an available plan or code reality, stop and ask.
7. If a review item requires a design decision not already made, stop and ask.
8. Check off fixes if a checklist exists.

### Focused verification

- Run focused verification relevant to the fixes. This repo uses `uv`; the focused unit tests for these findings are:
  - `uv run --extra test python -m pytest tests/serverless/test_compat.py tests/test_compatibility.py -q`
  - `uv run --extra test python -m pytest tests/test_report_remote_server.py -k "validate or download_html_bundle or get_server_name or api_version_property or unsupported" -q` (the pre-existing Docker-only `test_validate_existing` errors without Docker; that is environmental, not a regression).
  - Add any test that directly exercises the file you touched. Do not run the full suite manually.
- Run the applicable focused documentation validation for every documentation update before staging (for example the project's Sphinx `doc` build for `.rst` changes); if no update applies, record the evidence-based `Not applicable` rationale.
- After verification, stage the intended files with `git add`.
- Do not stage or commit workflow-generated Markdown artifacts by default, including `DRAFT_PLAN.md`, `INITIAL_OPUS_PLANNING_PROMPT.md`, `FEATURE_SPEC_AND_PLAN.md`, `GPT_EXECUTION_PROMPT.md`, `PLAN_CRITIQUE.md`, `OPUS_PLAN_REVISION_REQUEST.md`, `PLAN_REVISION_SUMMARY.md`, `PLAN_REVISION_VERIFICATION.md`, `REVIEW.md`, `WALKTHROUGH.md`, `GPT_REVIEW_FIX_PROMPT.md`, `REVIEW_FIX_VERIFICATION.md`, and `FOLLOWUP.md`, unless explicitly asked to commit them.
- Create focused commit(s) with detailed messages.
- Push the current branch after committing.
- Check whether a pull request already exists for the current branch before creating one. If you do not know how, use the GitHub CLI (`gh pr list --head fix/26r1-bc` or `gh pr status`).
- Create a pull request if and only if the current branch does not already have one. Do not create a duplicate PR for the same branch.
- If a command fails, paste the exact error/log back. Never paraphrase logs.

### Required final response

Respond in exactly this structure:

```markdown
# Review Fix Summary

## Review Items Fixed

## Review Items Not Fixed And Why

## Files Changed

## Verification Evidence

## Documentation Checkpoints

## Commits Created

## Push Status

## Pull Request

## Remaining Questions / Blockers
```

In `## Documentation Checkpoints`, list each review item's documentation status, the exact durable documentation and validation evidence when applicable, or the evidence-based `Not applicable` rationale.

Do not claim completion without fresh verification evidence.
