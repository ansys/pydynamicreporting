# Implementation Plan: mypy → ty, then full typing rollout

---

## Prerequisite 0: Docs-First Gate (MANDATORY — execute before any code changes)

> [!CAUTION]
> **No implementation work may begin until this step is completed.** Codex must read and internalize every document listed below before making any code changes.

### Documents read

| Document | Path | Key rules extracted |
|----------|------|--------------------|
| [AGENTS.md](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/AGENTS.md) | [AGENTS.md](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/AGENTS.md) | Preserve public APIs. Add/update tests for behavior changes. Run `make check`, `make test`, `make smoketest` before concluding. Avoid unrelated reformatting; keep diffs tight. Don't touch generated files (`adr_item.py`, `adr_utils.py`, [build_info.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/codegen/build_info.py)). Use NumPy-style docstrings. Branch convention: `maint/*` for this work. |
| [CONTRIBUTING.md](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/CONTRIBUTING.md) | [CONTRIBUTING.md](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/CONTRIBUTING.md) | No direct commits to `main`. Use branch naming: `maint/*` for maintenance/CI changes. Reference PyAnsys Developer's Guide. |
| [README.rst](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/README.rst) | [README.rst](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/README.rst) | Python 3.10–3.12. Uses `uv` + `make install`. Dev workflow: `make check` before committing. Available commands: `make check`, `make test`, `make smoketest`, `make build`, `make docs`, `make clean`. |
| [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml) | [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml) | `requires-python = ">=3.10, <3.13"`. Dev deps in `[project.optional-dependencies]`. Ruff config at `[tool.ruff]`. Hatch build backend. [uv.lock](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/uv.lock) is committed. |
| [.pre-commit-config.yaml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.pre-commit-config.yaml) | [.pre-commit-config.yaml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.pre-commit-config.yaml) | Hooks: blacken-docs, codespell, check-jsonschema, ruff-format, ruff-check, pre-commit-hooks, ansys license headers. No type-checking hook currently. |
| [Makefile](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/Makefile) | [Makefile](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/Makefile) | `check` = lockfile + pre-commit. `test` = pytest + coverage. `smoketest` = import sanity. All commands via `uv run`. |
| [.github/workflows/ci_cd.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/ci_cd.yml) | [ci_cd.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/ci_cd.yml) | Jobs: [style](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_objects.py#94-103), `smoketest`, `test`, `docs`, `package`, `publish-to-azure`, `upload_dev_docs`. No type-check job. |
| [.github/workflows/tests.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/tests.yml) | [tests.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/tests.yml) | Matrix: Python 3.10/3.11/3.12. Uses `make test`. |
| [.github/actions/setup-python-env/action.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/actions/setup-python-env/action.yml) | [action.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/actions/setup-python-env/action.yml) | Sets up Python + uv + caches `.venv` + runs `make install`. |
| [.github/actions/setup-env/action.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/actions/setup-env/action.yml) | [action.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/actions/setup-env/action.yml) | Sets `MAIN_PYTHON_VERSION=3.12`, `PACKAGE_NAME`, `ANSYS_VERSION=271`. |

### Engineering rules extracted (Codex must follow)

1. **Never commit directly to `main`**. Use `maint/*` branch prefix.
2. **Run `make check`, `make smoketest` before every commit/push.** If any fail, fix — never bypass.
3. **Keep diffs tight.** No unrelated reformatting. No opportunistic refactors.
4. **Do not touch generated files**: `adr_item.py`, `adr_utils.py`, [build_info.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/codegen/build_info.py).
5. **All commands run via `uv run`**. Never install globally. Never use bare `pip`.
6. **Lockfile must remain consistent**: run `uv lock` after changing deps, then `uv sync --frozen --all-extras`.
7. **Preserve public APIs**. No behavior changes.
8. **NumPy-style docstrings** for public APIs.

### Codex execution prerequisite

Before making any code change, Codex **must**:
1. Read [AGENTS.md](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/AGENTS.md) in full.
2. Read [CONTRIBUTING.md](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/CONTRIBUTING.md) in full.
3. Read [README.rst](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/README.rst) development setup section.
4. Read [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml) in full.
5. Read [.pre-commit-config.yaml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.pre-commit-config.yaml) in full.
6. Read [Makefile](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/Makefile) in full.
7. Read [.github/workflows/ci_cd.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/ci_cd.yml) in full.
8. Confirm understanding by verifying that `make install` succeeds.

Only after completing all 8 steps may Codex proceed to Task 1.

---

## 0. Repo Recon (what exists today)

### Current type-checking setup
- **mypy status**: Already removed. [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml) line 89 shows `#    "mypy",` (commented out in `[project.optional-dependencies] dev`). No `[tool.mypy]` section exists anywhere. No `mypy.ini`, no `setup.cfg` with mypy settings. No `.mypy.ini`.
- **No type-checker is currently active** — not in pre-commit, not in CI, not in Makefile.
- **Pre-commit** ([.pre-commit-config.yaml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.pre-commit-config.yaml)): blacken-docs, codespell, check-jsonschema, ruff-format, ruff-check, pre-commit-hooks, ansys license headers. No type-checking hook.
- **CI** ([ci_cd.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/ci_cd.yml)): [style](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_objects.py#94-103) job runs `ansys/actions/code-style@v10`. `test` job calls [tests.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/tests.yml). No type-checking job.
- **Makefile**: `check` target runs `uv lock --locked` + `pre-commit run --all-files`. No type-check target.
- **[.flake8](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.flake8)**: Legacy flake8 config still present (redundant with ruff). Not relevant to type-checking.

### Python versions
- `requires-python = ">=3.10, <3.13"` → supports **3.10, 3.11, 3.12**
- CI matrix: `['3.10', '3.11', '3.12']`
- ty `python-version` should be `"3.10"` (minimum supported version)

### Source tree structure (files to type)

| Path | Lines | Description |
|------|-------|-------------|
| [src/ansys/dynamicreporting/core/__init__.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/__init__.py) | 38 | Package init, re-exports |
| `src/.../core/_version.py` | ~50 | Version string (generated) |
| `src/.../core/adr_service.py` | 1040 | [Service](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/adr_service.py#75-1040) class — main public API |
| `src/.../core/adr_report.py` | 794 | [Report](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/adr_report.py#60-794) class — public API |
| `src/.../core/common_utils.py` | ~350 | Shared utility functions |
| `src/.../core/constants.py` | 66 | Constants (tuples, strings) |
| `src/.../core/docker_support.py` | ~600 | Docker launcher |
| `src/.../core/exceptions.py` | ~150 | Exception hierarchy |
| `src/.../core/serverless/__init__.py` | ~80 | Serverless package init |
| `src/.../core/serverless/adr.py` | ~2000 | Serverless ADR implementation |
| `src/.../core/serverless/base.py` | ~1000 | Base serverless classes |
| `src/.../core/serverless/html_exporter.py` | ~750 | HTML export |
| `src/.../core/serverless/item.py` | ~1000 | Serverless item |
| `src/.../core/serverless/template.py` | ~1300 | Serverless template |
| `src/.../core/utils/__init__.py` | ~40 | Utils init |
| `src/.../core/utils/encoders.py` | ~100 | JSON encoders |
| `src/.../core/utils/enhanced_images.py` | ~650 | Image processing |
| `src/.../core/utils/exceptions.py` | ~100 | Util-level exceptions |
| `src/.../core/utils/extremely_ugly_hacks.py` | ~280 | Legacy workarounds |
| `src/.../core/utils/filelock.py` | ~470 | File locking |
| `src/.../core/utils/geofile_processing.py` | ~340 | Geo file processing |
| `src/.../core/utils/html_export_constants.py` | ~150 | HTML constants |
| `src/.../core/utils/report_download_html.py` | ~800 | HTML download |
| `src/.../core/utils/report_download_pdf.py` | ~180 | PDF download |
| `src/.../core/utils/report_objects.py` | **3968** | Core data objects (largest file) |
| `src/.../core/utils/report_remote_server.py` | **1900** | REST server interface |
| `src/.../core/utils/report_utils.py` | ~900 | Report utilities |

**Generated files** (excluded from manual typing): `adr_item.py`, `adr_utils.py`, [build_info.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/codegen/build_info.py) — generated by `codegen/` build hook.

### Current annotation state
- **Partial**: Public API methods in [adr_service.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/adr_service.py) and [adr_report.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/adr_report.py) have parameter annotations (e.g., [str](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_objects.py#293-317), `bool`, [int](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_remote_server.py#66-71), `str | None`, `dict | None`, [list](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_objects.py#354-357)) but **most lack return type annotations**.
- **Internal modules** (`utils/`, `serverless/`): Almost **no annotations**. Functions use bare `def foo(self, x):` style.
- Only 5 files import from `typing` at all ([adr_report.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/adr_report.py), [report_utils.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_utils.py), [base.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/serverless/base.py), [html_exporter.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/serverless/html_exporter.py), [adr.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/serverless/adr.py)).

### Third-party dependencies and stub availability

| Package | Stubs Status |
|---------|-------------|
| `django` | `django-stubs` available (PyPI) |
| `django-guardian` | No official stubs; `django-stubs` covers basics |
| `requests` | Inline types (typed since 2.28) |
| `docker` | `types-docker` available |
| `Pillow` | Inline types |
| `numpy` | Inline types (since 1.20) |
| `pandas` | `pandas-stubs` available |
| `statsmodels` | No stubs; `allowed-unresolved-imports` needed |
| `python-pptx` | No stubs; `allowed-unresolved-imports` needed |
| `psutil` | No stubs; `allowed-unresolved-imports` needed |
| `dateutil` | `types-python-dateutil` available |
| `pytz` | `types-pytz` available |
| `qtpy` | No stubs; conditionally imported (`has_qt` guard) |
| `bleach` | No stubs; `allowed-unresolved-imports` needed |
| `weasyprint` | No stubs; `allowed-unresolved-imports` needed |
| `django-weasyprint` | No stubs; `allowed-unresolved-imports` needed |
| `psycopg` | No stubs; `allowed-unresolved-imports` needed |
| `lark` | No stubs; `allowed-unresolved-imports` needed |
| `pypng` | No stubs; `allowed-unresolved-imports` needed |

---

## 1. Migration Goals and Non-Goals

### Goals
1. **Add ty as the type-checker** with `[tool.ty]` config in [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml).
2. **Wire ty into pre-commit** as a `repo: local` hook.
3. **Wire ty into CI** as a dedicated job in [ci_cd.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/ci_cd.yml).
4. **Add a Makefile target** `make typecheck` for developer convenience.
5. **Add real, correct type annotations** across the entire `src/` codebase incrementally.
6. **Zero `# type: ignore` / `# ty: ignore`** comments (except for documented third-party stub bugs).
7. **Zero `typing.cast()`** usage (prefer `isinstance` guards or runtime narrowing).
8. **No behavior changes** — all typing work is semantics-preserving.

### Non-Goals
- Typing test files (`tests/`). Tests will be checked by ty but with relaxed rules via overrides.
- Typing generated files (`adr_item.py`, `adr_utils.py`, [build_info.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/codegen/build_info.py)). These can be excluded.
- Typing `codegen/` or `scripts/`. These are dev tools, not shipped code.
- Removing the [.flake8](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.flake8) file (separate concern).
- Upgrading Python version requirements.

---

## 1a. No Diff Churn Constraint (MANDATORY)

> [!WARNING]
> Every diff in this migration must be **minimal and strictly scoped**. Violations of this constraint will cause PR rejection.

### Allowed diff categories
- Deletion of mypy references (commented-out dep line)
- Addition of ty to dev dependencies
- Addition of `[tool.ty.*]` configuration sections
- Addition of pre-commit hook entry
- Addition of CI job
- Addition of Makefile target
- Addition of type annotations (parameter types, return types, class attribute types)
- Minimal correctness refactors strictly necessary for sound typing (e.g., `str = None` → `str | None = None`)

### Forbidden diff categories
- Opportunistic refactors (renaming, restructuring, reorganizing imports beyond what typing requires)
- Formatting churn (re-wrapping lines, changing quotes, reordering unrelated code)
- Unrelated cleanup (removing dead code, fixing non-typing issues)
- Modifying runtime behavior in any way
- Adding comments unrelated to typing

### Enforcement
- Every PR must have a diff review pass confirming **zero lines outside the allowed categories**.
- If a line change doesn't belong to one of the allowed categories, it must be reverted before merge.

---

## 1b. No Strictness Regression Rule (MANDATORY)

> [!IMPORTANT]
> ty's configuration must be **at least as strict** as mypy's effective behavior. Since mypy was not explicitly configured (commented out, never ran), the baseline is "no type checking". However, the goal is to **introduce strict type checking**, not to replicate a relaxed state.

### Formal constraints
1. **No blanket suppression**: Never use `allowed-unresolved-imports = ["**"]` or `replace-imports-with-any = ["**"]`.
2. **Per-module allowlisting only**: Each entry in `allowed-unresolved-imports` must name a specific third-party package, with documented justification.
3. **No silent error category suppression**: If a ty rule is set to `"ignore"`, the justification must be documented inline in [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml).
4. **Strictness escalation is one-way**: Once a rule severity is raised (warn → error), it must never be lowered except to fix a confirmed ty bug (with an upstream issue link).

### Strictness parity verification checklist

- [ ] `allowed-unresolved-imports` contains **only** packages confirmed to lack stubs (verified against PyPI)
- [ ] No rule is set to `"ignore"` without inline comment explaining why
- [ ] `error-on-warning = true` is enabled by end of Phase B
- [ ] `[tool.ty.rules] all = "error"` is the final state
- [ ] No `# type: ignore` / `# ty: ignore` comments exist in `src/` (grep verification)
- [ ] No `typing.cast()` calls exist in `src/` (grep verification)
- [ ] No blanket `Any` usage exists without documented justification

### Settings without ty equivalents — mitigations

| mypy Setting | ty Status | Mitigation |
|-------------|-----------|------------|
| `disallow_untyped_defs` | No direct equivalent | ty catches usage errors at call sites of untyped functions. Full annotations are enforced by this plan's Phase B, not by a flag. Manual review gate per milestone. |
| `disallow_any_generics` | No direct equivalent | Plan mandates precise generic types (`list[str]` not [list](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_objects.py#354-357)). Enforced by PR review. |
| `strict_equality` | Built into ty | No action needed. |
| `warn_unreachable` | Built into ty's reachability analysis | No action needed. |

---

## 1c. Explicit Completion Definitions (MANDATORY)

### Phase A is complete if and only if ALL of the following are true:

- [ ] `grep -r "mypy" pyproject.toml .pre-commit-config.yaml Makefile .github/` returns **zero matches** (excluding this plan document)
- [ ] `mypy` does not appear in any `[project.optional-dependencies]` section (not even commented out)
- [ ] No `mypy.ini`, `.mypy.ini`, or `[tool.mypy]` section exists anywhere in the repo
- [ ] [ty](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_objects.py#490-492) is listed in `[project.optional-dependencies] dev`
- [ ] `[tool.ty]` section exists in [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml) with valid configuration
- [ ] `uv run ty check src` exits with code 0
- [ ] [.pre-commit-config.yaml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.pre-commit-config.yaml) contains `ty-check` hook using `uv run ty check src`
- [ ] `uv run pre-commit run ty-check --all-files` exits with code 0
- [ ] [.github/workflows/ci_cd.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/ci_cd.yml) contains `typecheck` job
- [ ] [Makefile](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/Makefile) contains `typecheck` target
- [ ] `uv lock --locked` passes (lockfile is consistent)
- [ ] `make smoketest` passes

### Phase B is complete if and only if ALL of the following are true:

- [ ] `uv run ty check src` exits with code 0 with `error-on-warning = true`
- [ ] `grep -rn "# type: ignore\|# ty: ignore" src/` returns **zero matches**
- [ ] `grep -rn "typing.cast\|from typing import.*cast" src/` returns **zero matches** (unless documented exception with upstream issue link)
- [ ] Every `Any` usage in `src/` has an inline comment justified with one of: "JSON payload from external API", "stdlib contract requires Any", or a specific upstream issue link
- [ ] `make check` passes (full pre-commit suite including ty)
- [ ] `make test` passes (full test suite, no regressions)
- [ ] `make smoketest` passes
- [ ] `[tool.ty.terminal] error-on-warning = true` is set in [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml)
- [ ] All public API functions/methods in `src/` have parameter and return type annotations

---

## 2. Phase A — Replace mypy with ty (configuration + tooling)

### 2.1 Inventory: current mypy configuration and invocation points

| Asset | Status |
|-------|--------|
| `pyproject.toml [tool.mypy]` | Does not exist |
| `mypy.ini` / `.mypy.ini` / `setup.cfg [mypy]` | Does not exist |
| `mypy` in dev dependencies | Commented out (line 89) |
| `mypy` in pre-commit | Not present |
| `mypy` in CI workflows | Not present |
| `mypy` in Makefile | Not present |

**Conclusion**: There is nothing to remove. mypy was already decommissioned. Phase A is purely additive.

### 2.2 Mapping: mypy → ty (table)

Since mypy was not configured, this table maps *common mypy settings that would have been relevant* to ty equivalents, for reference:

| mypy Setting | ty Equivalent | Notes |
|-------------|---------------|-------|
| `python_version = "3.10"` | `[tool.ty.environment] python-version = "3.10"` | Auto-detected from `requires-python` |
| `mypy_path = "src"` | `[tool.ty.environment] root = ["./src"]` | ty auto-detects `src/` layout |
| `ignore_missing_imports = true` | `[tool.ty.analysis] allowed-unresolved-imports = [...]` | ty uses per-module glob patterns instead of blanket ignore |
| `disallow_untyped_defs = true` | No direct equivalent | ty focuses on usage errors, not missing annotations |
| `strict = true` | `[tool.ty.rules] all = "error"` | Closest equivalent |
| `exclude = [...]` | `[tool.ty.src] exclude = [...]` | gitignore-style patterns |
| `per-module overrides` | `[[tool.ty.overrides]]` | Per-file-glob rule overrides |
| `warn_return_any` | Built into ty's type inference | No knob needed |
| `warn_unused_ignores` | `unused-ignore-comment = "warn"` | Rule-level config |
| `# type: ignore` | Respected by default (`respect-type-ignore-comments = true`) | Can also use `# ty: ignore` |

### 2.2a Third-Party Stubs Policy (MANDATORY)

> [!IMPORTANT]
> **Blanket `ignore_missing_imports`-style relaxations are explicitly forbidden.** Every third-party package must be handled individually.

#### Resolution strategy (ordered by preference)

1. **Package has inline types** → No action needed. (e.g., `requests`, `Pillow`, `numpy`)
2. **Official `types-*` stub package exists on PyPI** → Add to `[project.optional-dependencies] dev`. (e.g., `types-docker`, `types-python-dateutil`, `types-pytz`)
3. **Community stub package exists** → Add to dev deps after review. (e.g., `django-stubs`, `pandas-stubs`)
4. **No stubs exist, package is well-typed at runtime** → Verify with `uv run ty check` — may work without stubs.
5. **No stubs exist, package lacks type info** → Add to `allowed-unresolved-imports` with per-module glob pattern. **Document justification inline.**

#### Per-package resolution table

| Package | Resolution | Action |
|---------|-----------|--------|
| `django` | `django-stubs` (PyPI) | Add `"django-stubs"` to dev deps |
| `requests` | Inline types | None |
| `docker` | `types-docker` (PyPI) | Add `"types-docker"` to dev deps |
| `Pillow` | Inline types | None |
| `numpy` | Inline types | None |
| `pandas` | `pandas-stubs` (PyPI) | Add `"pandas-stubs"` to dev deps |
| `dateutil` | `types-python-dateutil` (PyPI) | Add `"types-python-dateutil"` to dev deps |
| `pytz` | `types-pytz` (PyPI) | Add `"types-pytz"` to dev deps |
| `statsmodels` | No stubs | `allowed-unresolved-imports = ["statsmodels.**"]` — no upstream stubs, low-usage in this repo |
| `python-pptx` | No stubs | `allowed-unresolved-imports = ["pptx.**"]` — no upstream stubs available |
| `psutil` | No stubs | `allowed-unresolved-imports = ["psutil.**"]` — awaiting upstream PEP 561 support |
| `qtpy` | No stubs, conditional import | `allowed-unresolved-imports = ["qtpy.**"]` — guarded by `has_qt` flag |
| `bleach` | No stubs | `allowed-unresolved-imports = ["bleach.**"]` — deprecated library, limited usage |
| `weasyprint` | No stubs | `allowed-unresolved-imports = ["weasyprint.**"]` — no upstream stubs |
| `django-weasyprint` | No stubs | `allowed-unresolved-imports = ["django_weasyprint.**"]` — no upstream stubs |
| `psycopg` | No stubs | `allowed-unresolved-imports = ["psycopg.**"]` — no upstream stubs |
| `lark` | No stubs | `allowed-unresolved-imports = ["lark.**"]` — parser library, limited usage |
| `pypng` | No stubs | `allowed-unresolved-imports = ["png.**"]` — minimal library |
| `django-guardian` | No stubs | `allowed-unresolved-imports = ["guardian.**", "django_guardian.**"]` — Django extension |
| `tzlocal` | No stubs | `allowed-unresolved-imports = ["tzlocal.**"]` — timezone utility |

#### Forbidden approaches
- ❌ `allowed-unresolved-imports = ["**"]` (blanket suppress)
- ❌ `replace-imports-with-any = ["**"]` (blanket Any replacement)
- ❌ Adding packages to `allowed-unresolved-imports` without verifying that no stubs exist on PyPI
- ❌ Vendoring full third-party type stubs without upstream contribution plan


### 2.3 ty configuration design for this repo

Add the following to [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml):

```toml
# ── ty type checking ──────────────────────────────────────────
[tool.ty.environment]
python-version = "3.10"

[tool.ty.src]
include = ["src"]

[tool.ty.rules]
# Start with default severity for all rules, then tune as needed
# During Phase B rollout, we begin with "warn" and graduate to "error"
# once a module passes cleanly

[tool.ty.terminal]
error-on-warning = false

[tool.ty.analysis]
# Third-party packages without available type stubs
allowed-unresolved-imports = [
    "statsmodels.**",
    "pptx.**",
    "psutil.**",
    "qtpy.**",
    "bleach.**",
    "weasyprint.**",
    "django_weasyprint.**",
    "psycopg.**",
    "lark.**",
    "png.**",
    "guardian.**",
    "django_guardian.**",
    "tzlocal.**",
]

# ── Overrides: relax rules for tests and generated code ──────
[[tool.ty.overrides]]
include = ["tests/**"]
[tool.ty.overrides.rules]
possibly-unresolved-reference = "warn"

[[tool.ty.overrides]]
include = ["codegen/**", "scripts/**"]
[tool.ty.overrides.rules]
possibly-unresolved-reference = "ignore"
```

### 2.4 Pre-commit integration design

ty does **not** ship an official pre-commit hook. The integration uses `repo: local` with `uv run ty check`.

Add to [.pre-commit-config.yaml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.pre-commit-config.yaml):

```yaml
- repo: local
  hooks:
    - id: ty-check
      name: ty type check
      entry: uv run ty check src
      language: system
      types: [python]
      pass_filenames: false
      always_run: true
```

> [!IMPORTANT]
> `pass_filenames: false` + `always_run: true` ensures ty runs a whole-project check on every commit. This is necessary because type errors in file A can be caused by changes in file B. Incremental checking is still fast because ty caches internally.

**Why `uv run ty check src`**:
- `uv run` ensures ty is resolved from the project's environment (installed via `uv sync`).
- `src` scopes the check to the source directory only.
- This respects the `[tool.ty]` config in [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml) automatically.

### 2.5 CI integration design

Add a new `typecheck` job to [ci_cd.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/ci_cd.yml):

```yaml
  typecheck:
    name: Type check
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v6
        with:
          fetch-depth: '0'
          fetch-tags: true

      - name: Set up Python
        uses: ./.github/actions/setup-python-env

      - name: Run ty type check
        run: uv run ty check src --output-format github
```

> [!NOTE]
> `--output-format github` produces GitHub Actions annotations, making type errors appear inline on PRs.

### 2.6 Removal of mypy + cleanup

| Action | File | Details |
|--------|------|---------|
| Remove commented-out mypy dep | [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml) line 89 | Delete `#    "mypy",` |
| Add [ty](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_objects.py#490-492) to dev deps | [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml) → `[project.optional-dependencies] dev` | Add `"ty"` |
| Update lockfile | Terminal | Run `uv lock` then `uv sync --frozen --all-extras` |

### 2.7 Validation steps (local + CI)

1. **Local**:
   ```bash
   uv lock
   uv sync --frozen --all-extras
   uv run ty check src             # Should exit 0 (may have warnings initially)
   uv run pre-commit run ty-check --all-files  # Validate pre-commit hook
   make check                       # Full pre-commit suite
   make smoketest                   # Ensure nothing is broken
   ```
2. **CI**: Push to a branch and confirm the new `typecheck` job passes in GitHub Actions.

---

## 3. Phase B — Add type hints across the codebase (no hacks)

### 3.1 Principles and standards (what's allowed / not allowed)

#### ✅ Allowed
- Standard library `typing` types: `list[X]`, `dict[K, V]`, `tuple[X, ...]`, `set[X]`, `X | None`
- Use PEP 604 unions (`X | Y`) since Python ≥3.10
- `Optional[X]` → prefer `X | None`
- `Literal["a", "b"]` for string enums in function parameters
- `TypedDict` for structured dict returns
- `Protocol` for structural subtyping (e.g., file-like objects, iterables)
- `isinstance()` and `assert isinstance()` for runtime type narrowing
- `Sequence`, `Mapping`, `Iterable` for read-only collection parameters (prefer over concrete types)
- `from __future__ import annotations` is **not needed** (Python ≥3.10 supports `X | Y` natively)

#### ❌ Not allowed
- `Any` as a placeholder / filler type
- `# type: ignore` / `# ty: ignore` (except documented third-party stub bugs)
- `typing.cast()` to silence checker (use `isinstance` guard or restructure)
- [object](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_remote_server.py#472-583) as a catch-all parameter/return type
- Fake unions (`int | str | bytes | None | ...`) that don't reflect actual runtime behavior
- Behavior changes to make types work out
- Unnecessary refactors — changes must be surgical

#### Guidelines
- **Public APIs** (exported from [__init__.py](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/__init__.py)): Full annotations mandatory on all parameters and return types.
- **Internal helpers**: Full annotations. Use `_` prefix convention to indicate private.
- **Parameters with defaults**: The type should match the default value. `def foo(x: str = "")` not `def foo(x: str = None)` — use `def foo(x: str | None = None)` when `None` is a valid sentinel.
- **Return types**: Always annotate. Use `-> None` for procedures.
- **Class attributes**: Annotate at class level or in [__init__](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/src/ansys/dynamicreporting/core/utils/report_remote_server.py#121-152).
- **Properties**: Annotate return type.

### 3.2 Module ordering plan (with milestones and gates)

The ordering follows a dependency-first strategy: type leaf modules first, then modules that depend on them.

> [!IMPORTANT]
> **Gating rule**: Milestone N cannot begin until Milestone N-1 is complete (merged, CI green, all validation steps in §3.6 passing). This is non-negotiable.

All paths below are relative to `src/ansys/dynamicreporting/core/`.

#### Milestone 1: Foundation (small, self-contained files)

**Entry gate**: Phase A complete (§1c checklist satisfied).
**Exit gate**: `uv run ty check src` clean + `make test` + `make smoketest` + §3.6 validation.

| Priority | File (relative to `core/`) | Absolute path | Lines | Rationale |
|----------|---------------------------|---------------|-------|-----------|
| 1 | `constants.py` | `src/ansys/dynamicreporting/core/constants.py` | 66 | Pure constants, no dependencies |
| 2 | `exceptions.py` | `src/ansys/dynamicreporting/core/exceptions.py` | ~150 | Exception classes, minimal deps |
| 3 | `utils/exceptions.py` | `src/ansys/dynamicreporting/core/utils/exceptions.py` | ~100 | Util-level exceptions |
| 4 | `utils/html_export_constants.py` | `src/ansys/dynamicreporting/core/utils/html_export_constants.py` | ~150 | Pure constants |
| 5 | `utils/encoders.py` | `src/ansys/dynamicreporting/core/utils/encoders.py` | ~100 | Simple JSON encoders |
| 6 | `common_utils.py` | `src/ansys/dynamicreporting/core/common_utils.py` | ~350 | Shared utility functions |

#### Milestone 2: Utilities layer

**Entry gate**: Milestone 1 merged, CI green.
**Exit gate**: `uv run ty check src` clean + `make test` + `make smoketest` + §3.6 validation.

| Priority | File (relative to `core/`) | Absolute path | Lines | Rationale |
|----------|---------------------------|---------------|-------|-----------|
| 7 | `utils/filelock.py` | `src/ansys/dynamicreporting/core/utils/filelock.py` | ~470 | Self-contained utility |
| 8 | `utils/enhanced_images.py` | `src/ansys/dynamicreporting/core/utils/enhanced_images.py` | ~650 | Image utilities, Pillow types |
| 9 | `utils/geofile_processing.py` | `src/ansys/dynamicreporting/core/utils/geofile_processing.py` | ~340 | Geo file processing |
| 10 | `utils/report_utils.py` | `src/ansys/dynamicreporting/core/utils/report_utils.py` | ~900 | Report helper functions |
| 11 | `utils/extremely_ugly_hacks.py` | `src/ansys/dynamicreporting/core/utils/extremely_ugly_hacks.py` | ~280 | Legacy workarounds |
| 12 | `utils/report_download_pdf.py` | `src/ansys/dynamicreporting/core/utils/report_download_pdf.py` | ~180 | PDF download utility |
| 13 | `utils/report_download_html.py` | `src/ansys/dynamicreporting/core/utils/report_download_html.py` | ~800 | HTML download utility |

#### Milestone 3: Core data objects

**Entry gate**: Milestone 2 merged, CI green.
**Exit gate**: `uv run ty check src` clean + `make test` + `make smoketest` + §3.6 validation. **After this milestone, set `error-on-warning = true`.**

| Priority | File (relative to `core/`) | Absolute path | Lines | Rationale |
|----------|---------------------------|---------------|-------|-----------|
| 14 | `utils/report_objects.py` | `src/ansys/dynamicreporting/core/utils/report_objects.py` | **3968** | Core data model. Largest file. Annotate class by class. |
| 15 | `utils/report_remote_server.py` | `src/ansys/dynamicreporting/core/utils/report_remote_server.py` | **1900** | `Server` class. Depends on `report_objects`. |

#### Milestone 4: Docker support

**Entry gate**: Milestone 3 merged, CI green, `error-on-warning = true` active.
**Exit gate**: `uv run ty check src` clean + `make test` + `make smoketest` + §3.6 validation.

| Priority | File (relative to `core/`) | Absolute path | Lines | Rationale |
|----------|---------------------------|---------------|-------|-----------|
| 16 | `docker_support.py` | `src/ansys/dynamicreporting/core/docker_support.py` | ~600 | Docker launcher, uses `docker` package |

#### Milestone 5: Serverless layer

**Entry gate**: Milestone 4 merged, CI green.
**Exit gate**: `uv run ty check src` clean + `make test` + `make smoketest` + §3.6 validation.

| Priority | File (relative to `core/`) | Absolute path | Lines | Rationale |
|----------|---------------------------|---------------|-------|-----------|
| 17 | `serverless/base.py` | `src/ansys/dynamicreporting/core/serverless/base.py` | ~1000 | Base serverless classes (Django models) |
| 18 | `serverless/item.py` | `src/ansys/dynamicreporting/core/serverless/item.py` | ~1000 | Serverless item |
| 19 | `serverless/template.py` | `src/ansys/dynamicreporting/core/serverless/template.py` | ~1300 | Serverless template |
| 20 | `serverless/html_exporter.py` | `src/ansys/dynamicreporting/core/serverless/html_exporter.py` | ~750 | HTML export |
| 21 | `serverless/adr.py` | `src/ansys/dynamicreporting/core/serverless/adr.py` | ~2000 | Full serverless ADR |
| 22 | `serverless/__init__.py` | `src/ansys/dynamicreporting/core/serverless/__init__.py` | ~80 | Serverless init |

#### Milestone 6: Public API layer

**Entry gate**: Milestone 5 merged, CI green.
**Exit gate**: `uv run ty check src` clean + `make test` + `make smoketest` + §3.6 validation. **After this milestone, set `all = "error"`.**

| Priority | File (relative to `core/`) | Absolute path | Lines | Rationale |
|----------|---------------------------|---------------|-------|-----------|
| 23 | `adr_report.py` | `src/ansys/dynamicreporting/core/adr_report.py` | 794 | `Report` class — already partially annotated |
| 24 | `adr_service.py` | `src/ansys/dynamicreporting/core/adr_service.py` | 1040 | `Service` class — already partially annotated |
| 25 | `__init__.py` | `src/ansys/dynamicreporting/core/__init__.py` | 38 | Package init — minimal |

### 3.3 Hard Problem Playbook (repo-specific — MANDATORY reference)

> [!CAUTION]
> For every pattern below, the prescribed approach is **the only acceptable approach**. Do not deviate. Do not use `cast()`. Do not use `# type: ignore`.

#### 3.3.1 Dynamic attributes / `__getattr__` / `setattr` loops

**Where**: `report_objects.py` → `Template.__init__` uses `*initial_data, **kwargs` with `setattr`.

**Correct approach**:
```python
class Template:
    # Declare ALL known attributes with their types at class level
    parent: str | None
    master: bool
    name: str
    tags: str
    report_type: str
    # ... (enumerate every attribute set in __init__ or via setattr)

    def __init__(self, *initial_data: dict[str, Any], **kwargs: Any) -> None:
        # setattr loop remains as-is — no behavior change
        for dictionary in initial_data:
            for key in dictionary:
                setattr(self, key, dictionary[key])
```
- Keep the `setattr` loop unchanged (semantics-preserving).
- ty infers attribute types from class-level annotations.
- If an attribute's type is genuinely unknown, annotate as the narrowest correct type, not `Any`.

**Forbidden**: `__getattr__(self, name: str) -> Any` as a blanket escape hatch.

#### 3.3.2 Django-style patterns and lazy objects

**Where**: `serverless/base.py`, `serverless/item.py`, `serverless/template.py`, `serverless/adr.py`.

**Correct approach**:
- Install `django-stubs` (added to dev deps per stubs policy).
- Use `django.db.models.QuerySet[ModelType]` for queryset returns.
- For `objects.filter()`, `objects.get()`, etc., `django-stubs` provides typed managers.
- For `django-guardian` and `django-weasyprint` (no stubs): these are in `allowed-unresolved-imports`. Functions receiving objects from these libraries should type the parameter as the most specific known base class.

**Forbidden**: Annotating Django model fields as `Any`. Use the field's actual Python type (`str`, `int`, `datetime`, etc.).

#### 3.3.3 Dict/JSON payload shapes

**Where**: `report_remote_server.py` (REST API responses), `report_objects.py` (serialized data).

**Correct approach** (decision tree):
1. **Schema is known and stable** → Define a `TypedDict`:
   ```python
   class TemplatePayload(TypedDict):
       name: str
       report_type: str
       guid: str
       children: list[str]
   ```
2. **Schema is partially known** → Use `TypedDict` with `total=False` for optional keys.
3. **Schema is genuinely dynamic** (e.g., arbitrary JSON from external API) → `dict[str, Any]` is acceptable **with inline comment**: `# JSON payload from external API`.
4. **Schema is a pass-through** (received and forwarded without inspection) → annotate as `dict[str, Any]` with comment: `# pass-through payload, schema owned by remote service`.

**Forbidden**: Using bare `dict` without type parameters. Always specify `dict[K, V]`.

#### 3.3.4 Optional flows and runtime narrowing

**Where**: Throughout the codebase — many parameters default to `None`.

**Correct approach**:
```python
# CORRECT: narrow with isinstance or identity check
def process(data: str | None = None) -> str:
    if data is None:
        return "default"
    return data.upper()  # ty knows data is str here

# CORRECT: narrow with assert (acceptable for internal code)
def internal_process(items: list[Item] | None) -> int:
    assert items is not None, "items must be provided at this point"
    return len(items)
```

**Forbidden**:
```python
# FORBIDDEN: cast to silence checker
from typing import cast
result = cast(str, maybe_str)  # ❌ NEVER

# FORBIDDEN: type: ignore
result = maybe_str.upper()  # type: ignore  # ❌ NEVER
```

#### 3.3.5 Runtime/conditional imports

**Where**: `report_objects.py` (`has_qt`, `has_numpy`), `adr_report.py` (`IPython.display`).

**Correct approach**:
```python
try:
    from qtpy import QtCore, QtGui
    has_qt = True
except ImportError:
    has_qt = False

# ty handles this pattern correctly.
# Functions using QtCore/QtGui MUST be inside `if has_qt:` guards.
# No changes needed to the import pattern itself.
```

- The `has_qt: bool` variable is already correctly typed by inference.
- Functions that use conditionally imported modules must have their bodies inside the guard.
- Do NOT add `TYPE_CHECKING` blocks unless strictly necessary for circular import resolution.

#### 3.3.6 Decorators and higher-order functions

**Where**: `report_objects.py` → `disable_warn_logging`.

**Correct approach**:
```python
from typing import TypeVar, ParamSpec
import functools

_P = ParamSpec("_P")
_R = TypeVar("_R")

def disable_warn_logging(func: Callable[_P, _R]) -> Callable[_P, _R]:
    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        # ... implementation ...
        return func(*args, **kwargs)
    return wrapper
```

**Forbidden**: `Callable[..., Any]` as decorator signature.

### 3.4 Required refactors (only if unavoidable)

| Refactor | File | Justification |
|----------|------|---------------|
| Fix `extra_detail: str = None` | `exceptions.py:35` | Should be `extra_detail: str \| None = None`. Current signature is a type error — default `None` doesn't match `str`. This is a bug, not a style choice. |

> [!NOTE]
> No other refactors are expected. All typing should be additive annotations only. If a refactor is discovered to be necessary during implementation, it must be documented with justification before proceeding.

### 3.5 Progress tracking + gating strategy

#### Incremental gating rules (MANDATORY)

1. **Each milestone = one PR** (or small set of PRs). Never bundle multiple milestones.
2. **Pre-milestone gate**: Before starting Milestone N, Milestone N-1 must be merged and CI green.
3. **Per-PR gate**: Each PR must satisfy ALL of the following before merge:
   - `uv run ty check src` exits with code 0
   - `uv run pre-commit run --all-files` exits with code 0
   - `make smoketest` passes
   - `make test` passes (if tests are available to run locally)
   - No new `# type: ignore` / `# ty: ignore` comments
   - No new `typing.cast()` usage
   - No diff churn (verified by diff review)
4. **CI enforcement**: The `typecheck` job in CI must be a **required status check** for PR merge.
5. **Progress metric**: Count of fully-annotated files / total files. Track in PR description.

#### ty rules escalation schedule

| After Milestone | Action | Config change |
|----------------|--------|---------------|
| Milestone 1 (Foundation) | Keep defaults | None |
| Milestone 3 (Core objects) | Enable warning escalation | `error-on-warning = true` |
| Milestone 6 (Public API) | Full strict mode | `all = "error"` |

> [!WARNING]
> **Escalation is one-way.** Once a strictness level is raised, it must never be lowered.

### 3.6 Validation steps (MANDATORY — after EVERY milestone)

The following commands must ALL pass. Failure of any command blocks the milestone from completion.

```bash
# Step 1: Type check — must exit 0
uv run ty check src

# Step 2: Pre-commit — must exit 0 (includes ty hook)
uv run pre-commit run --all-files

# Step 3: Import sanity — must exit 0
make smoketest

# Step 4: Full test suite — must exit 0, no regressions
make test

# Step 5: Verify no suppression comments were added
grep -rn "# type: ignore\|# ty: ignore" src/ && echo "FAIL: suppression comments found" && exit 1 || echo "PASS"

# Step 6: Verify no cast usage was added
grep -rn "typing.cast\|from typing import.*cast" src/ && echo "FAIL: cast usage found" && exit 1 || echo "PASS"
```

If any step fails, the milestone is **not complete**. Fix the issue. Do not proceed to the next milestone.

---

## 4. Task List for Codex (ordered, ready to execute)

### Codex Execution Hardening Rules (MANDATORY)

> [!CAUTION]
> These rules are non-negotiable. Violation of any rule invalidates the task output.

1. **Virtual environment**: `uv` must create and manage the virtual environment. Never use `python -m venv` or `virtualenv` directly.
2. **All tooling via `uv run`**: Every command that invokes Python tools must use `uv run`. This includes `ty`, `pre-commit`, `pytest`, `hatch`.
3. **Pre-commit validation**: `uv run pre-commit run --all-files` must pass **before and after** each milestone. If it fails:
   - Diagnose the failure.
   - Fix the root cause (code issue, config issue, or environment issue).
   - **Never bypass hooks.** Never use `--no-verify`. Never disable checks.
   - **Never remove or comment out a hook** to make it pass.
4. **Environment issues**: If `uv sync` or `uv run` fails:
   - Run `uv lock` and try again.
   - If that fails, check Python version compatibility.
   - **Never fall back to `pip install`.**
5. **Determinism**: Every command must produce the same result when run twice in a row. If a command is flaky, investigate and fix before proceeding.
6. **No interactive commands**: All commands must run non-interactively. No prompts, no manual input.
7. **Lockfile consistency**: After any change to `pyproject.toml`, immediately run `uv lock` and verify `uv lock --locked` passes.

### Task 1: Add ty configuration to pyproject.toml

**Goal**: Set up ty configuration and add ty as a dev dependency.

**Files touched**: [pyproject.toml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/pyproject.toml)

**Edits**:

1. In `[project.optional-dependencies] dev` (line 78–92):
   - Delete `#    "mypy",` (line 89)
   - Add `"ty",` after `"ruff",` (line 85)

2. Append the following after the `[tool.pre-commit.default_language_versions]` section (after line 244):

```toml
# ── ty type checking ──────────────────────────────────────────
[tool.ty.environment]
python-version = "3.10"

[tool.ty.src]
include = ["src"]

[tool.ty.rules]
# Default severities; escalate after typing rollout is complete

[tool.ty.terminal]
error-on-warning = false

[tool.ty.analysis]
# Third-party packages without available type stubs
allowed-unresolved-imports = [
    "statsmodels.**",
    "pptx.**",
    "psutil.**",
    "qtpy.**",
    "bleach.**",
    "weasyprint.**",
    "django_weasyprint.**",
    "psycopg.**",
    "lark.**",
    "png.**",
    "guardian.**",
    "django_guardian.**",
    "tzlocal.**",
]

[[tool.ty.overrides]]
include = ["tests/**"]
[tool.ty.overrides.rules]
possibly-unresolved-reference = "warn"

[[tool.ty.overrides]]
include = ["codegen/**", "scripts/**"]
[tool.ty.overrides.rules]
possibly-unresolved-reference = "ignore"
```

**Commands**:
```bash
uv lock
uv sync --frozen --all-extras
uv run ty check src   # Validate initial run
```

**Expected outcome**: ty installs, config is valid, initial check produces warnings (expected) but no crash.

---

### Task 2: Add ty to pre-commit

**Goal**: Wire ty into the pre-commit pipeline.

**Files touched**: [.pre-commit-config.yaml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.pre-commit-config.yaml)

**Edit**: Add the following block before the `ansys/pre-commit-hooks` entry (before line 37):

```yaml
- repo: local
  hooks:
    - id: ty-check
      name: ty type check
      entry: uv run ty check src
      language: system
      types: [python]
      pass_filenames: false
      always_run: true
```

**Commands**:
```bash
uv run pre-commit run ty-check --all-files
```

**Expected outcome**: Pre-commit runs ty check successfully.

---

### Task 3: Add ty to CI

**Goal**: Add a `typecheck` job to the CI/CD pipeline.

**Files touched**: [ci_cd.yml](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/.github/workflows/ci_cd.yml)

**Edit**: Add the following job after the `style` job (after line 35):

```yaml
  typecheck:
    name: Type check
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v6
        with:
          fetch-depth: '0'
          fetch-tags: true

      - name: Set up Python
        uses: ./.github/actions/setup-python-env

      - name: Run ty type check
        run: uv run ty check src --output-format github
```

**Expected outcome**: New job appears in CI, runs ty with GitHub annotations.

---

### Task 4: Add Makefile target

**Goal**: Add `make typecheck` for developer convenience.

**Files touched**: [Makefile](file:///Users/vp-dc/Documents/GitHub/pydynamicreporting/Makefile)

**Edit**: Add after the `check` target (after line 29):

```makefile
.PHONY: typecheck
typecheck: ## Run ty type checker
	uv run ty check src
```

**Expected outcome**: `make typecheck` runs ty check.

---

### Task 5: Update lockfile and validate

**Goal**: Ensure all tooling changes work end-to-end.

**Commands**:
```bash
uv lock
uv sync --frozen --all-extras
make typecheck
make check
make smoketest
```

**Expected outcome**: All commands pass. The repo is now on ty with zero configuration for mypy.

---

### Tasks 6–30: Add type annotations (one task per Milestone file)

Each task follows this template:

1. **Open the file** and review all function signatures, class definitions, and module-level variables.
2. **Add import statements** as needed at top of file: `from __future__ import annotations` is NOT needed. Import from `typing` only if using `TypeVar`, `Protocol`, `TypedDict`, etc. Use built-in generics (`list`, `dict`, `tuple`, `set`) since Python ≥3.10.
3. **Annotate all function parameters** with their correct types.
4. **Annotate all return types** (including `-> None`).
5. **Annotate class attributes** in `__init__` or at class level.
6. **Add `isinstance` guards** where type narrowing is needed (no `cast`).
7. **Run `uv run ty check src`** — fix any real errors.
8. **Run `make smoketest`** — confirm no import regressions.

> [!IMPORTANT]
> For each file, the implementer should run `uv run ty check src/ansys/dynamicreporting/core/<file>` to check just that file first, then run the full `uv run ty check src` to catch cross-module issues.

#### Task 6: Type `constants.py`
- Annotate module-level constants with explicit types: `DOCKER_REPO_URL: str = ...`, `LAYOUT_TYPES: tuple[str, ...] = (...)`, etc.

#### Task 7: Type `exceptions.py`
- Add return type annotations to `__init__`, `__str__`.
- Fix `extra_detail: str = None` → `extra_detail: str | None = None`.

#### Task 8: Type `utils/exceptions.py`
- Same pattern as Task 7.

#### Task 9: Type `utils/html_export_constants.py`
- Annotate constants.

#### Task 10: Type `utils/encoders.py`
- Annotate encoder methods. `JSONEncoder.default` returns `Any` per stdlib contract — this is acceptable.

#### Task 11: Type `common_utils.py`
- Annotate all utility functions.

#### Task 12: Type `utils/filelock.py`
- Annotate file lock class and methods.

#### Task 13: Type `utils/enhanced_images.py`
- Annotate image processing functions. Use `PIL.Image.Image` for Pillow types.

#### Task 14: Type `utils/geofile_processing.py`
- Annotate geo file functions.

#### Task 15: Type `utils/report_utils.py`
- Annotate report utility functions. This file already has some typing imports.

#### Task 16: Type `utils/extremely_ugly_hacks.py`
- Annotate legacy workaround functions.

#### Task 17: Type `utils/report_download_pdf.py`
- Annotate PDF download functions.

#### Task 18: Type `utils/report_download_html.py`
- Annotate HTML download functions.

#### Task 19: Type `utils/report_objects.py` (largest file — split into sub-tasks)
- **Sub-task 19a**: Annotate utility functions at module level (`convert_color`, `convert_style`, `parse_filter`, etc.)
- **Sub-task 19b**: Annotate `Template` class and all its methods
- **Sub-task 19c**: Annotate `TemplateREST` class
- **Sub-task 19d**: Annotate `ItemREST` class and subclasses
- **Sub-task 19e**: Annotate `DatasetREST` class
- **Sub-task 19f**: Annotate `SessionREST` class
- **Sub-task 19g**: Annotate remaining classes

#### Task 20: Type `utils/report_remote_server.py`
- Annotate `Server` class and all methods. Use `requests.Response` return types.

#### Task 21: Type `docker_support.py`
- Annotate Docker launcher. Use `docker.models.containers.Container` type from docker-py.

#### Task 22: Type `serverless/base.py`
- Annotate base serverless classes. Use Django model types from `django-stubs`.

#### Task 23: Type `serverless/item.py`
- Annotate serverless item class.

#### Task 24: Type `serverless/template.py`
- Annotate serverless template class.

#### Task 25: Type `serverless/html_exporter.py`
- Annotate HTML exporter functions.

#### Task 26: Type `serverless/adr.py`
- Annotate full serverless ADR implementation (largest serverless file).

#### Task 27: Type `serverless/__init__.py`
- Annotate init module.

#### Task 28: Type `adr_report.py`
- Complete annotations on `Report` class (already partially annotated).

#### Task 29: Type `adr_service.py`
- Complete annotations on `Service` class (already partially annotated).

#### Task 30: Type `__init__.py`
- Add `__all__` with proper types if not present.

---

### Task 31: Final hardening

**Goal**: Graduate to strict mode.

**Edits to `pyproject.toml`**:
```toml
[tool.ty.terminal]
error-on-warning = true
```

**Commands**:
```bash
uv run ty check src   # Must exit 0 with no warnings or errors
make check
make test
```

---

## 5. Risks, Mitigations, Rollback

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ty is pre-1.0 and may have false positives | Medium | Low | Use `allowed-unresolved-imports` for unstubbed libs. Report ty bugs upstream. Can pin ty version. |
| ty doesn't support a needed mypy feature | Low | Low | mypy was never configured — no features to miss |
| Third-party stubs are incomplete | Medium | Medium | Use `allowed-unresolved-imports` per-module (not blanket). Track upstream stub issues. |
| Generated files break under ty | Low | Low | Excluded from checking via `[tool.ty.src] include = ["src"]` and the generated files are in coverage omit list already |
| Typing work introduces a bug | Low | High | All typing changes are annotation-only (no runtime behavior changes). Test suite must pass. |
| ty version breaks in CI | Low | Medium | Pin ty version in `pyproject.toml` dev deps: `"ty>=0.x,<0.y"`. |
| Large PR backlog / merge conflicts | Medium | Medium | Small PRs per milestone. Each PR is independent. |

### Rollback plan
1. **Phase A rollback**: Remove `[tool.ty.*]` sections from `pyproject.toml`, remove `ty-check` hook from `.pre-commit-config.yaml`, remove `typecheck` job from `ci_cd.yml`, remove `typecheck` target from `Makefile`. Run `uv lock && uv sync --frozen --all-extras`.
2. **Phase B rollback**: Type annotations are always backward-compatible. Reverting a typing PR has no runtime effect. Simply revert the PR.
