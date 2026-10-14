# Walkthrough

- **Created by:** Claude (Opus 4.8), phase 04 post-implementation review
- **Created at:** 2026-08-24
- **Updated at:** 2026-08-24 (phase 06 refresh — reflects final code after the review-fix loop)

This document walks every production change on `fix/26r1-bc` line by line, with a plain-English explanation beside each line, so you can review without opening the source. It assumes no prior context. It reflects the **final** code, including the review-loop fixes (validate ordering, the glob guard, the new `Raises` docstrings and type hints, and the Draco example comments).

## How to read this

Each section names a file. Code appears in a block, then each line (or a tight group of related lines) gets an English explanation. Test, docs, and config files are covered after the production code, at the level of "what it proves / why it changed".

## What this branch does, in one paragraph

The client is bundled with Ansys product line `27.1` and officially supports the current and previous annual lines (`27` and `26`). This branch does four things. First, it teaches the client to **reject** a connected ADR server whose reported product version is outside that support window (a new exception, a new validator, and re-raise plumbing). Second, it makes serverless ADR **run against a 26.1 install on NumPy 2** by temporarily restoring a removed NumPy alias and legacy print formatting, then undoing that when ADR is torn down. Third, it makes the offline/remote HTML exporters **ship the older 26.1 viewer's context-menu assets** so 26.1 reports render correctly. Fourth, it **removes the WeasyPrint PDF path**, leaving the browser (Playwright) PDF path as the only one.

---

## 1. `src/ansys/dynamicreporting/core/exceptions.py`

A new exception type is added.

```python
class UnsupportedServerVersionError(ADRException):
    """Exception raised if the connected ADR server version is not supported."""

    detail = "Unsupported dynamic reporting server version."
```

- `class UnsupportedServerVersionError(ADRException):` — declares a new exception that inherits from the project's base error class `ADRException`. Because it inherits from `ADRException`, any code that already writes `except ADRException` keeps catching it, so this addition is backwards compatible.
- `"""..."""` — one-line docstring describing when it is raised.
- `detail = "Unsupported dynamic reporting server version."` — a class attribute the base `ADRException` uses to build a default message when the exception is raised without explicit text. Matches how the sibling exceptions in this file define `detail`.

---

## 2. `src/ansys/dynamicreporting/core/compatibility.py`

One import and one new function.

```python
from .exceptions import UnsupportedServerVersionError
```
- Imports the new exception so the validator below can raise it.

```python
def validate_supported_server_install_version(
    install_version: int | str | None,
    supported_product_lines: tuple[str, ...] = SUPPORTED_PRODUCT_LINES,
) -> str:
```
- `def validate_supported_server_install_version(` — new public function that checks a server-reported version and either returns a clean value or raises.
- `install_version: int | str | None,` — the version the server reported (for example `271`, `"261"`, or `None` if it reported nothing). Accepting all three shapes means callers do not have to pre-clean the value.
- `supported_product_lines: tuple[str, ...] = SUPPORTED_PRODUCT_LINES,` — the annual lines this client accepts (default `("26", "27")`). Passing it as a parameter with a default keeps the function testable while staying convenient.
- `-> str:` — on success it returns the normalized three-digit version string.

```python
    if install_version is None:
        raise UnsupportedServerVersionError(
            "The server did not report an Ansys version in /item/api_version/."
        )
```
- `if install_version is None:` — first rejection case: the server sent no version at all.
- `raise UnsupportedServerVersionError(...)` — fail with a message that tells the user exactly which server endpoint was expected to carry the version.

```python
    normalized = str(install_version).strip()
    try:
        detected_release = install_version_to_product_release(normalized)
    except ValueError as exc:
        raise UnsupportedServerVersionError(
            f"The server reported Ansys version {install_version!r}, which is not a "
            "three-digit install version such as '271'."
        ) from exc
```
- `normalized = str(install_version).strip()` — turns `271` (int) or `" 271 "` (padded string) into the clean string `"271"`. This is the value returned on success.
- `try:` / `detected_release = install_version_to_product_release(normalized)` — reuses the existing converter that turns `"271"` into the product release `"27.1"`. If the value is not a valid three-digit install version, that converter raises `ValueError`.
- `except ValueError as exc:` — catches the malformed-version case.
- `raise UnsupportedServerVersionError(...) from exc` — re-raises as the domain exception, showing the original raw value (`{install_version!r}`) so the user sees what the server actually sent, and chains the `ValueError` as the cause for debugging.

```python
    if is_supported_product_release(detected_release, supported_product_lines):
        return normalized
```
- `if is_supported_product_release(...)` — reuses the existing check that asks "is the annual line of `27.1` (which is `27`) in the supported set?".
- `return normalized` — supported: hand back the clean `"271"` string.

```python
    supported_lines = ", ".join(f"{line}.*" for line in supported_product_lines)
    raise UnsupportedServerVersionError(
        "Connected ADR server reports product release "
        f"{detected_release}. This client is bundled with {BUNDLED_PRODUCT_RELEASE} "
        f"and supports annual lines {supported_lines}."
    )
```
- `supported_lines = ", ".join(...)` — builds a human list like `26.*, 27.*` for the error message.
- `raise UnsupportedServerVersionError(...)` — final rejection: the version parsed fine but its line is outside the window. The message states what the server reported, what this client bundles, and what it supports, so the user can act.

**Note (see REVIEW.md NB-1):** the sibling function `get_compatibility_warning_for_install_version` above this one does the same parsing but returns `None` instead of raising. They are deliberately kept separate (warn vs. enforce).

---

## 3. `src/ansys/dynamicreporting/core/adr_service.py`

This file wires the new exception through the high-level `Service` so it is never swallowed into the generic "invalid server" error. The pattern repeats three times.

```python
from .exceptions import (
    ...
    UnsupportedServerVersionError,
)
```
- Adds the new exception to the existing import block.

```python
        try:
            self.serverobj.validate()
        except UnsupportedServerVersionError:
            raise
        except Exception as e:
            self.logger.error(f"Can not validate dynamic reporting server.\nError: {str(e)}")
            raise NotValidServer
```
- `try: self.serverobj.validate()` — validates the connected server (unchanged call).
- `except UnsupportedServerVersionError: raise` — **new**: if validation failed specifically because the server version is unsupported, let that precise exception propagate unchanged. Without this, the next handler would rewrite it.
- `except Exception as e:` / `raise NotValidServer` — unchanged fallback: any other validation failure is logged and turned into the generic `NotValidServer`. Ordering matters: the specific handler must come first.

The same two-line `except UnsupportedServerVersionError: raise` guard is added in the `launch_local_database_server` call path lower in the file, for the same reason. Three docstrings (`get_server`, `start`, and the launch path) also gain a `Raises` entry documenting `UnsupportedServerVersionError`, so the public method contracts now advertise the new failure.

---

## 4. `src/ansys/dynamicreporting/core/serverless/_compat.py`

The module's job widened from "fix settings" to "fix settings and dependency APIs", and a NumPy runtime shim was added.

```python
"""Serverless runtime compatibility shims.

Translate product settings and dependency APIs so they remain compatible with
the versions installed in the client's venv. ...
"""
```
- Docstring rewritten to say the module now also adapts dependency APIs (the NumPy shim), not only settings.

```python
RuntimeCompatCleanup = Callable[[], None]
_NUMPY_STRING_ALIAS_PRODUCT_VERSION = 261
```
- `RuntimeCompatCleanup = Callable[[], None]` — a named type alias for "a function that takes nothing and returns nothing". Used as the return type of the shim so callers know they get a cleanup callback.
- `_NUMPY_STRING_ALIAS_PRODUCT_VERSION = 261` — the only product version that needs this shim, named as a constant instead of a bare `261` scattered in code.

```python
def apply_runtime_compatibility_shims(product_version: int) -> RuntimeCompatCleanup:
    """... Restore the alias and NumPy 1.25 print formatting before importing the
    product's Django modules, and return a cleanup callback ..."""

    def _noop_runtime_compatibility_cleanup() -> None:
        return

    if product_version != _NUMPY_STRING_ALIAS_PRODUCT_VERSION:
        return _noop_runtime_compatibility_cleanup
```
- `def apply_runtime_compatibility_shims(product_version: int)` — entry point; called once during `setup()` with the resolved install version.
- `def _noop_runtime_compatibility_cleanup() -> None: return` — a do-nothing cleanup used when there is nothing to undo, so the caller can always call the returned callback unconditionally.
- `if product_version != _NUMPY_STRING_ALIAS_PRODUCT_VERSION: return ...noop` — early exit for any version other than 26.1. Only 26.1 on this client needs the NumPy fix, so newer products pay no cost.

```python
    import numpy

    cleanup_callbacks: list[RuntimeCompatCleanup] = []

    def _restore_cleanup_callbacks() -> None:
        for cleanup in reversed(cleanup_callbacks):
            cleanup()
```
- `import numpy` — imported lazily, inside the function, so importing this module never forces NumPy to load.
- `cleanup_callbacks: list[...] = []` — collects one undo function per mutation actually applied.
- `def _restore_cleanup_callbacks(): for cleanup in reversed(cleanup_callbacks): cleanup()` — runs the undo functions in reverse order (last applied is undone first), which is the correct order for nested state changes.

```python
    try:
        if not hasattr(numpy, "string_"):
            setattr(numpy, "string_", numpy.bytes_)

            def _restore_string_alias() -> None:
                if getattr(numpy, "string_", None) is numpy.bytes_:
                    delattr(numpy, "string_")

            cleanup_callbacks.append(_restore_string_alias)
            logger.info("Compat shim: Restored 'numpy.string_' as 'numpy.bytes_' for ADR 26.1")
```
- `try:` — wraps every mutation so a failure can roll back (see the `except` below).
- `if not hasattr(numpy, "string_"):` — only act if the alias is missing. On NumPy 1.x `numpy.string_` still exists, so this is skipped; on NumPy 2.x it was removed, so we act. (Historically `numpy.string_` was an alias of `numpy.bytes_`.)
- `setattr(numpy, "string_", numpy.bytes_)` — restores the removed alias by pointing `numpy.string_` at `numpy.bytes_`, which is exactly what it used to be. ADR 26.1's template code reads `numpy.string_`.
- `def _restore_string_alias():` — the matching undo. `if getattr(numpy, "string_", None) is numpy.bytes_:` only deletes the alias if it is still the exact object we set (identity check), so we never remove an alias someone else installed. `delattr(numpy, "string_")` removes our addition.
- `cleanup_callbacks.append(_restore_string_alias)` — register the undo.
- `logger.info(...)` — record that the shim ran, for operators reading logs.

```python
        if _normalize_version(numpy.__version__) >= (2, 0):
            previous_legacy = numpy.get_printoptions().get("legacy", False)
            numpy.set_printoptions(legacy="1.25")

            def _restore_legacy_printoptions() -> None:
                numpy.set_printoptions(legacy=previous_legacy)

            cleanup_callbacks.append(_restore_legacy_printoptions)
            logger.info("Compat shim: Enabled NumPy 1.25 legacy printing for ADR 26.1")
```
- `if _normalize_version(numpy.__version__) >= (2, 0):` — only on NumPy 2.x. `_normalize_version("2.5.2")` yields the tuple `(2, 5, 2)`, and `(2, 5, 2) >= (2, 0)` is true; `(1, 26, 4) >= (2, 0)` is false.
- `previous_legacy = numpy.get_printoptions().get("legacy", False)` — remembers the current legacy print setting so it can be restored exactly.
- `numpy.set_printoptions(legacy="1.25")` — makes NumPy 2 print scalars the way NumPy 1.25 did. ADR 26.1's plot renderer inlines NumPy scalar text straight into JavaScript, so the older formatting matters.
- `def _restore_legacy_printoptions(): numpy.set_printoptions(legacy=previous_legacy)` — undo that restores the saved value.
- `cleanup_callbacks.append(...)` / `logger.info(...)` — register undo and log.

```python
    except BaseException:  # catch interrupts as well
        _restore_cleanup_callbacks()
        raise
```
- `except BaseException:` — catches everything, including `KeyboardInterrupt`/`SystemExit`, which normal `except Exception` misses. This is intentional: a Ctrl-C in the middle of mutating global NumPy state must still trigger cleanup.
- `_restore_cleanup_callbacks()` — undo whatever was applied so far.
- `raise` — re-raise the original error after cleaning up; the shim never hides a failure.

```python
    if not cleanup_callbacks:
        return _noop_runtime_compatibility_cleanup

    return _restore_cleanup_callbacks
```
- `if not cleanup_callbacks: return ...noop` — if nothing was actually changed (for example 26.1 on NumPy 1.x), hand back the no-op cleanup.
- `return _restore_cleanup_callbacks` — otherwise return the real cleanup; the caller stores it and calls it at teardown.

---

## 5. `src/ansys/dynamicreporting/core/serverless/adr.py`

The largest file. New imports, two new instance attributes, three new helpers for native `enve` importing and Python-version warnings, and a transactional rewrite of `setup()`.

### 5a. Imports and new instance attributes

```python
import importlib
import re
from typing import Any, Callable
```
- `importlib` — used by `_import_enve` to import modules by name at runtime.
- `re` — used by `_get_embedded_python_version` to parse a directory name.
- `Callable` — added to the typing import for the new attribute/return annotations.

```python
        self._runtime_compat_restore: Callable[[], None] | None = None
        self._embedded_python_version: tuple[int, int] | None = None
```
- `self._runtime_compat_restore: Callable[[], None] | None = None` — holds the cleanup callback returned by the NumPy shim, or `None` before setup. Declared with its type at construction, as the typing rules require.
- `self._embedded_python_version: tuple[int, int] | None = None` — caches the Python version the product bundles, filled in during setup.

### 5b. `_import_enve` — import native `enve` from candidate paths, cleaning up failures

```python
    @staticmethod
    def _import_enve(candidate_paths: Iterable[Path]) -> ImportError | None:
```
- A static method (no `self` needed) that tries to import the native `enve` module used by animation rendering. It returns the final `ImportError` if it never succeeds, or `None` on success.

```python
        try:
            importlib.import_module("enve")
        except ImportError as error:
            last_error = error
        else:
            return None
```
- First, try importing `enve` from whatever is already on `sys.path`. If that works (`else: return None`), stop. If not, remember the error in `last_error` and continue to the candidate directories.

```python
        for path in candidate_paths:
            if not path.is_dir():
                continue
```
- Loop over the product directories the caller supplied. Skip any that do not exist.

```python
            original_sys_path = sys.path.copy()
            original_udi_path = os.environ.get("CEI_UDILPATH")
            old_enve_modules = {
                name: module
                for name, module in sys.modules.items()
                if name in ("enve", "enve_common") or name.startswith("enve_common.")
            }
            for name in old_enve_modules:
                sys.modules.pop(name, None)
```
- `original_sys_path = sys.path.copy()` — snapshot `sys.path` so a failed attempt can be fully reverted.
- `original_udi_path = os.environ.get("CEI_UDILPATH")` — snapshot the env var that importing `enve` may set as a side effect.
- `old_enve_modules = {...}` — snapshot any already-loaded `enve` / `enve_common` modules, because a half-finished import can leave broken partial modules behind.
- `for name in old_enve_modules: sys.modules.pop(name, None)` — clear those modules so this attempt starts clean.

```python
            sys.path.insert(0, str(path))
            try:
                importlib.import_module("enve_common.enve")
            except ImportError:
                try:
                    importlib.import_module("enve")
                except ImportError as error:
                    last_error = error
                else:
                    return None
            else:
                return None
```
- `sys.path.insert(0, str(path))` — put this candidate directory first so its `enve` wins the import.
- `importlib.import_module("enve_common.enve")` — try the newer packaging layout first. On success `else: return None` (done; the path stays in place because we want `enve` importable afterward).
- If that fails, `importlib.import_module("enve")` — try the older layout. Success returns `None`; failure stores `last_error`.

```python
            sys.path[:] = original_sys_path
            for name in tuple(sys.modules):
                if name in ("enve", "enve_common") or name.startswith("enve_common."):
                    sys.modules.pop(name)
            sys.modules.update(old_enve_modules)
            if original_udi_path is None:
                os.environ.pop("CEI_UDILPATH", None)
            else:
                os.environ["CEI_UDILPATH"] = original_udi_path

        return last_error
```
- This block runs only when both imports for the candidate failed. It reverses everything the attempt touched:
- `sys.path[:] = original_sys_path` — restore the exact path list.
- the `for name in tuple(sys.modules)` loop removes any `enve`/`enve_common` modules this attempt loaded.
- `sys.modules.update(old_enve_modules)` — put back the modules that existed before the attempt.
- the `CEI_UDILPATH` block restores the env var (delete it if it was unset, otherwise put the old value back).
- `return last_error` — after all candidates fail, return the last error so the caller can warn. A successful candidate would have returned `None` earlier and left its path in place.

### 5c. `_get_embedded_python_version` — read the Python version the product bundles

```python
    @staticmethod
    def _get_embedded_python_version(
        ansys_installation: Path, ansys_version: int
    ) -> tuple[int, int] | None:
```
- Static helper returning `(major, minor)` of the product's bundled Python, or `None` if it cannot tell.

```python
        machine_directory = (
            "win64" if platform.system().lower().startswith("win") else "linux_2.6_64"
        )
        runtime_directory = (
            ansys_installation / f"apex{ansys_version}" / "machines" / machine_directory
        )
```
- `machine_directory = ...` — pick the platform's runtime folder name.
- `runtime_directory = ...` — build the path where the product keeps its Python runtimes, for example `.../apex261/machines/win64`.

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
- `try:` — the whole scan-and-parse loop is inside the guard, so a filesystem error raised while iterating returns `None` instead of escaping.
- `for runtime_path in runtime_directory.glob("[Pp]ython-*"):` — look for directories named like `Python-3.10` or `python-3.10`. `glob` is lazy, so the actual directory read happens here during iteration, which is exactly why the loop must sit inside the `try`.
- `if not runtime_path.is_dir(): continue` — skip anything that is not a directory.
- `match = re.fullmatch(r"python-(\d+)\.(\d+)(?:\.\d+)?", runtime_path.name, flags=re.IGNORECASE)` — parse the name case-insensitively, capturing major and minor and tolerating an optional patch.
- `if match: return (int(match.group(1)), int(match.group(2)))` — first match wins; return its `(major, minor)`.
- `except OSError: return None` — a scan error (for example a permission error during iteration) returns `None` gracefully. **This is the NB-2 fix:** originally only the `glob()` call was guarded, which could not catch iteration-time errors; the loop is now inside the `try`.
- `return None` — reached when the directory has no matching Python runtime folder.

### 5d. `_get_embedded_python_mismatch_message` and `_warn_for_embedded_python_mismatch`

```python
    @staticmethod
    def _get_embedded_python_mismatch_message(
        embedded_python_version: tuple[int, int] | None,
        active_python_version: tuple[int, int],
    ) -> str | None:
        if embedded_python_version is None or active_python_version == embedded_python_version:
            return None
        ...
        return ("Serverless ADR is running on Python ... but the Ansys installation bundles ...")
```
- Pure function: given the bundled version and the running version, return a warning string only when they are known and different. Returning `None` when they match (or are unknown) keeps the "should I warn?" decision in one testable place.

```python
    def _warn_for_embedded_python_mismatch(self) -> None:
        self._embedded_python_version = self._get_embedded_python_version(
            self._ansys_installation, self._ansys_version
        )
        active_python_version = (sys.version_info.major, sys.version_info.minor)
        warning_message = self._get_embedded_python_mismatch_message(
            self._embedded_python_version, active_python_version
        )
        if warning_message is None:
            return
        self._logger.warning(warning_message)
        warnings.warn(warning_message, UserWarning, stacklevel=2)
```
- Detects the bundled version and caches it on the instance.
- `active_python_version = (sys.version_info.major, sys.version_info.minor)` — the interpreter actually running.
- Ask the pure helper for a message; if `None`, do nothing.
- Otherwise emit it twice: once through the logger (operators) and once as a `UserWarning` (developers). `stacklevel=2` points the warning at the caller. (REVIEW.md NB-6 flags the double surface for confirmation.)

### 5e. `setup()` — now transactional

The interesting changes are the enve import call, the guarded product path + shim, and the rollback on failure. Key lines:

```python
        self._warn_for_embedded_python_mismatch()
        enve_error = self._import_enve(dirs_to_check)
        if enve_error is not None:
            msg = (
                "Animation rendering is unavailable because 'enve' could not be imported from "
                f"the Ansys installation: {enve_error}"
            )
            self._logger.warning(msg)
            warnings.warn(msg, UserWarning, stacklevel=2)
```
- `self._warn_for_embedded_python_mismatch()` — warn early if the interpreter does not match the product's bundled Python.
- `enve_error = self._import_enve(dirs_to_check)` — attempt the native import using the OS-specific candidate list built just above these lines.
- `if enve_error is not None:` — a failed import is not fatal (animations just will not render), so it logs and warns rather than raising. This is calmer than the old behavior, which warned from inside the import logic.

```python
        from ._compat import apply_runtime_compatibility_shims, sanitize_settings

        adr_path_added = False
        try:
            adr_path = (
                self._ansys_installation / f"nexus{self._ansys_version}" / "django"
            ).resolve(strict=True)
            adr_path_string = str(adr_path)
            if adr_path_string not in sys.path:
                sys.path.append(adr_path_string)
                adr_path_added = True

            self._runtime_compat_restore = apply_runtime_compatibility_shims(self._ansys_version)
            from ceireports import settings_serverless
        except (AttributeError, ImportError, OSError, TypeError, ValueError) as e:
            self._restore_runtime_compatibility_shims()
            if adr_path_added:
                sys.path.remove(adr_path_string)
            raise ImportError(f"Failed to initialize ADR from the Ansys installation: {e}") from e
```
- `adr_path_added = False` — a flag so we only undo a `sys.path` change we actually made.
- `adr_path = (... / f"nexus{self._ansys_version}" / "django").resolve(strict=True)` — resolve the product's Django folder; `strict=True` raises if it is missing. Resolving **before** enabling the shim is the point: a missing install fails here without ever touching global NumPy state.
- `if adr_path_string not in sys.path: sys.path.append(...); adr_path_added = True` — add the folder to the import path only if it is not already there, and record that we did.
- `self._runtime_compat_restore = apply_runtime_compatibility_shims(self._ansys_version)` — now that the install is known good, enable the NumPy shim and keep its cleanup callback.
- `from ceireports import settings_serverless` — import the product settings, which needs both the path and the shim.
- `except (AttributeError, ImportError, OSError, TypeError, ValueError) as e:` — a targeted set of failure types (not bare `Exception`).
- `self._restore_runtime_compatibility_shims()` — undo the NumPy shim so a failed setup leaves no global mutation behind.
- `if adr_path_added: sys.path.remove(adr_path_string)` — remove the path only if we added it.
- `raise ImportError(...) from e` — surface a clear, domain-appropriate error with the cause chained.

```python
        try:
            overrides = {}
            ...
            ADR._is_setup = True
            self._session = Session.create()
            self._dataset = Dataset.create()
        except Exception as e:
            ADR._is_setup = False
            self._session = None
            self._dataset = None
            self._restore_runtime_compatibility_shims()
            self._logger.debug("ADR could not complete setup.", exc_info=True)
            raise
```
- The rest of setup (settings, migrations, geometry checks, optional `collectstatic`, default session/dataset) runs inside a second `try`.
- On any failure it rolls back the global setup flag (`ADR._is_setup = False`), clears the half-built session/dataset, restores the NumPy shim, logs with traceback, and re-raises. So a failed `setup()` leaves the class and the process exactly as they were.

### 5f. `_restore_runtime_compatibility_shims` and `close()`

```python
    def _restore_runtime_compatibility_shims(self) -> None:
        if self._runtime_compat_restore is None:
            return
        restore = self._runtime_compat_restore
        self._runtime_compat_restore = None
        restore()
```
- Idempotent teardown of the NumPy shim. It reads the callback, nulls the attribute **before** calling it (so a second call is a no-op even if the callback fails), then runs it.

```python
    def close(self) -> None:
        ...
        try:
            connections.close_all()
        except DatabaseError:
            pass
        self._restore_runtime_compatibility_shims()
        ...
```
- `close()` now also restores the shim, so tearing an ADR instance down at process exit or end of test undoes the global NumPy changes. Safe to call repeatedly because of the idempotent helper.

### 5g. WeasyPrint PDF methods removed

Two public methods, `render_report_as_pdf` and `export_report_as_pdf` (both WeasyPrint), are deleted from the `ADR` class. The Playwright-based `render_report_as_browser_pdf` / `export_report_as_browser_pdf` remain and are now the only serverless PDF path. `_render_template_as_browser_pdf` (the private stager they share) is unchanged in behavior; it wraps failures in `ADRException` and cleans its scratch directory in a `finally`. This removes the `weasyprint` / `django-weasyprint` dependencies entirely. It is a breaking change versus the last stable release `v0.10.7`; the maintainer has confirmed it is intended for the unreleased `v1.0.0` major, with a changelog migration note (`render_report_as_pdf` → `render_report_as_browser_pdf`) to be added at release time. See REVIEW.md → Backwards Compatibility.

---

## 6. `src/ansys/dynamicreporting/core/serverless/template.py`

The WeasyPrint method on the serverless `Template` class is removed:

```python
    def render_pdf(self, *, context=None, item_filter: str = "", request=None) -> bytes:
        ...
        from weasyprint import HTML
        ...
        return HTML(string=static_html).write_pdf()
```
- The entire `render_pdf` method (about 40 lines) is deleted. It was the only importer of `weasyprint` in the package, which is why the dependency can be dropped. Callers that want a PDF now go through the ADR browser-PDF methods.

---

## 7. `src/ansys/dynamicreporting/core/utils/html_export_constants.py`

Three shared constants are added.

```python
MATHJAX_OPTIONAL_FILES = frozenset(
    {
        "website/scripts/mathjax/LICENSE",
        "website/scripts/mathjax/images/MenuArrow-15.png",
        "website/scripts/mathjax/images/CloseX-31.png",
    }
)
```
- Two MathJax v2 menu images are added to the **optional** set. Files in this set do not produce a "missing file" warning when absent, because not every install ships them.

```python
CONTEXT_MENU_PATH = "nexus/novnc/vendor/jQuery-contextMenu"
```
- A single source-of-truth path (relative to a versioned `ansys###` static root) for the 26.1 viewer's context-menu assets. Both exporters below import this instead of repeating the literal.

---

## 8. `src/ansys/dynamicreporting/core/serverless/html_exporter.py` (offline exporter)

This exporter copies static files from a local install into an output folder. Three additions.

```python
from ..utils.html_export_constants import (
    CONTEXT_MENU_JS,
    CONTEXT_MENU_PATH,
    ...
)
```
- Imports the shared path constant.

```python
        self._copy_legacy_context_menu_assets()
```
- Called from the main copy routine, right after the viewer JS is copied, so the 26.1 context-menu files land in the bundle.

```python
    def _copy_legacy_context_menu_assets(self) -> None:
        """Copy context-menu files required by older viewer loaders when available."""
        context_menu_path = f"ansys{self._ansys_version}/{CONTEXT_MENU_PATH}/"
        context_menu_dir = self._static_dir / context_menu_path
        if not context_menu_dir.is_dir() and str(self._ansys_version) != "261":
            return
        self._copy_static_files(
            CONTEXT_MENU_JS,
            context_menu_path,
            context_menu_path,
        )
```
- `context_menu_path = f"ansys{self._ansys_version}/{CONTEXT_MENU_PATH}/"` — the version-specific sub-path, for example `ansys261/nexus/novnc/vendor/jQuery-contextMenu/`.
- `context_menu_dir = self._static_dir / context_menu_path` — the concrete source directory in the install. Combining a forward-slash string with `Path` is Windows-safe.
- `if not context_menu_dir.is_dir() and str(self._ansys_version) != "261": return` — skip only when the directory is absent **and** we are not on 26.1. Newer products (27.1) may not ship the folder, so skipping is fine there; on 26.1 the copy is attempted even from a partial tree so each missing file is reported.
- `self._copy_static_files(CONTEXT_MENU_JS, context_menu_path, context_menu_path)` — copy the known context-menu file list from that source sub-path to the same relative target sub-path.

```python
                # Example: "/ansys271/nexus/threejs/libs/draco/" becomes
                # "./ansys271//nexus/threejs/libs/draco/"; // is intentional and browser-collapsed.
                s = s.replace(
                    f"'/ansys{ver}/nexus/threejs/libs/draco/'",
                    f"'./ansys{ver}//nexus/threejs/libs/draco/'",
                )
                s = s.replace(
                    f'"/ansys{ver}/nexus/threejs/libs/draco/"',
                    f'"./ansys{ver}//nexus/threejs/libs/draco/"',
                )
```
- The leading comment (added as the NB-5 fix) gives the worked example: server-absolute `"/ansys271/nexus/threejs/libs/draco/"` becomes relative `"./ansys271//nexus/threejs/libs/draco/"`, and states that the double slash is intentional and browser-collapsed.
- The two `replace` calls change server-absolute Draco decoder URLs into relative ones so the offline bundle loads them from disk. Both the single-quote and double-quote spellings are handled because either can appear in the JS. They sit next to the pre-existing images rewrite, which uses the same `//` convention.

```python
        common_directories = [
            "webfonts",
            f"ansys{self._ansys_version}/nexus/images",
            f"ansys{self._ansys_version}/nexus/utils",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf",
        ]
        if str(self._ansys_version) == "261":
            common_directories.append(f"ansys{self._ansys_version}/{CONTEXT_MENU_PATH}")

        for d in common_directories:
            (self._output_dir / d).mkdir(parents=True, exist_ok=True)
```
- The always-created directory list is pulled into a named variable.
- On 26.1 only, the context-menu directory is appended, so the output layout matches the pre-noVNC-removal structure even when the source install's context-menu tree is incomplete.
- The `for` loop creates each directory (`parents=True, exist_ok=True` is idempotent and cross-platform).

---

## 9. `src/ansys/dynamicreporting/core/utils/report_download_html.py` (remote downloader)

Same idea as the offline exporter, but assets come from a remote server over HTTP. Note this class stores `self._ansys_version` as a **string** (empty string for very old servers), so its 26.1 checks compare against `"261"`.

```python
from .html_export_constants import (
    CONTEXT_MENU_JS,
    CONTEXT_MENU_PATH,
    ...
)
```
- Imports the shared constants.

```python
        self._download_legacy_context_menu_assets()
```
- Invoked in the main download routine, after the viewer JS, mirroring the offline exporter.

```python
    def _download_legacy_context_menu_assets(self) -> None:
        """Download the v261 viewer dependencies that newer products removed."""
        if self._ansys_version != "261":
            return
        context_menu_path = f"/ansys{self._ansys_version}/{CONTEXT_MENU_PATH}/"
        self._download_static_files(
            CONTEXT_MENU_JS,
            context_menu_path,
            context_menu_path.lstrip("/"),
            "legacy viewer context-menu assets",
            warn_on_missing=True,
        )
```
- `if self._ansys_version != "261": return` — only 26.1 needs these; every other version returns immediately.
- `context_menu_path = f"/ansys{self._ansys_version}/{CONTEXT_MENU_PATH}/"` — the server URL sub-path (leading slash because it is a URL).
- `self._download_static_files(..., context_menu_path.lstrip("/"), ..., warn_on_missing=True)` — download the file list; the local target strips the leading slash so it is a relative folder, and `warn_on_missing=True` asks the helper to print a message for each file the server does not have.

```python
    def _download_static_files(
        self, files, source_path, target_path, comment, *, warn_on_missing: bool = False
    ):
        ...
                    self._write_binary_file(filename, data)
                except Exception as e:
                    print(f"Unable to download {comment}: {f}\nError: {e}")
            elif warn_on_missing:
                print(f"Unable to get {comment}: {url} ({resp.status_code})")
```
- The existing helper gains a keyword-only `warn_on_missing` flag (default `False`, so existing callers are unaffected).
- `elif warn_on_missing:` — when a file returns a non-OK HTTP status and the caller asked to be warned, print the URL and status code. Without the flag, missing files stay silent as before.

```python
            # Example: "/ansys271/nexus/threejs/libs/draco/" becomes
            # "./ansys271//nexus/threejs/libs/draco/"; // is intentional and browser-collapsed.
            data = data.replace(
                f"'/ansys{ansys_version}/nexus/threejs/libs/draco/'",
                f"'./ansys{ansys_version}//nexus/threejs/libs/draco/'",
            )
            data = data.replace(
                f'"/ansys{ansys_version}/nexus/threejs/libs/draco/"',
                f'"./ansys{ansys_version}//nexus/threejs/libs/draco/"',
            )
```
- The same Draco path rewrite as the offline exporter, applied to downloaded content, for the same reason. The same worked-example comment (the NB-5 fix) is present here too.

```python
        if self._ansys_version == "261":
            self._make_dir(
                [
                    self._directory,
                    f"ansys{self._ansys_version}",
                    *CONTEXT_MENU_PATH.split("/"),
                ]
            )
```
- On 26.1, pre-create the context-menu directory. `CONTEXT_MENU_PATH.split("/")` turns the slash path into individual components so `_make_dir` builds it portably. This preserves the expected layout even if the server cannot provide every file.

---

## 10. `src/ansys/dynamicreporting/core/utils/report_remote_server.py`

The low-level remote `Server`. This is where the version gate is enforced and where the lock handling was extended.

```python
import warnings
...
from ..compatibility import DEFAULT_ANSYS_INSTALL_VERSION, validate_supported_server_install_version
from ..exceptions import ADRException, InvalidAnsysPath, UnsupportedServerVersionError
```
- Adds the `warnings` module, the new validator, and the new exception to imports.

### 10a. `api_version` property

```python
    @property
    def api_version(self) -> float:
        """Return the validated server API version.

        Raises
        ------
        UnsupportedServerVersionError
            If the server reports a missing, malformed, or unsupported Ansys version.
        """
        if self._api_version is None:
            self.validate()
        return self._api_version
```
- `def api_version(self) -> float:` — the property is annotated to return a float and its docstring now documents the new failure. Previously this did a bare `float(self.get_api_version()["version"])`.
- `if self._api_version is None: self.validate()` — on first access it calls `self.validate()`, which parses the version **and** validates the advertised `ansys_version`. Consequence: first access to `.api_version` can now raise `UnsupportedServerVersionError`. For supported servers (lines 26, 27) nothing changes.
- The `Raises` section is the NB-3 documentation fix; the ordering inside `validate` (below) is the NB-1 fix that keeps this gate idempotent.

### 10b. `get_server_name` passthrough

```python
        if self.cur_servername is None:
            try:
                self.validate()
            except UnsupportedServerVersionError:
                raise
            except Exception as e:
                logger.debug(f"Warning: {str(e)}")
                pass
```
- Adds the same "let the specific exception through, swallow everything else" guard so an unsupported server is reported instead of being hidden behind the name lookup.

### 10c. `validate`

```python
    def validate(self) -> float:
        """Validate the server connection and advertised product compatibility.

        Raises
        ------
        UnsupportedServerVersionError
            If the server reports a missing, malformed, or unsupported Ansys version.
        """
        server_info = self.get_api_version()
        if "server_name" in server_info:
            self.cur_servername = server_info["server_name"]
        ansys_version = validate_supported_server_install_version(server_info.get("ansys_version"))
        api_version = float(server_info["version"])
        self._api_version = api_version
        self._ansys_version = ansys_version
        return self._api_version
```
- `def validate(self) -> float:` — annotated return type, and the docstring now documents `UnsupportedServerVersionError`.
- `server_info = self.get_api_version()` — one HTTP call for the server's `/item/api_version/` payload.
- `if "server_name" in server_info: self.cur_servername = ...` — cache the server name if present.
- `ansys_version = validate_supported_server_install_version(server_info.get("ansys_version"))` — validate the reported install version **first**. This raises `UnsupportedServerVersionError` for a missing, malformed, or unsupported version, before anything is cached.
- `api_version = float(server_info["version"])` — parse the API version into a local.
- `self._api_version = api_version` / `self._ansys_version = ansys_version` — assign both cached values together, only after both computed successfully.
- **This is the NB-1 fix.** The earlier code assigned `self._api_version` before the validation line, so a raise left `_api_version` cached (making the `api_version` gate non-idempotent and letting `_download_report_as_html_bundle` read stale state). Computing both values before assigning either means a raise now leaves both attributes untouched.

### 10d. `_download_report_as_html_bundle` (private helper)

The signature was fully typed during the review loop, and the docstring now advertises the new failure:

```python
    def _download_report_as_html_bundle(
        self,
        report_guid: str | uuid.UUID,
        directory_name: str | os.PathLike[str],
        query: dict[str, object] | None = None,
        item_filter: str | None = None,
        filename: str = "index.html",
        no_inline_files: bool = False,
        ansys_version: int | str | None = None,
    ) -> None:
        """Download a standalone HTML bundle for a report-generation request.
        ...
        Raises
        ------
        UnsupportedServerVersionError
            If the server reports a missing, malformed, or unsupported Ansys version.
        """
```
- The parameters are now typed: `directory_name` accepts `str | os.PathLike[str]` because callers pass `Path` objects; `ansys_version: int | str | None` matches the validator's input; `report_guid: str | uuid.UUID` is a permissive but accurate union. `-> None` because the method downloads and returns nothing.
- The `Raises` section documents `UnsupportedServerVersionError` (part of the NB-4 / DOC-2 documentation fix).

The version-resolution body (unchanged in behavior by the fixes):

```python
        try:
            connected_ansys_version = (
                self._ansys_version
                if self._api_version is not None
                else self.get_api_version().get("ansys_version")
            )
        except Exception:
            if ansys_version is None:
                raise
            connected_ansys_version = None
```
- Determine the server's version once. If validation already ran (`_api_version is not None`), reuse the cached `self._ansys_version` instead of making another HTTP call. Otherwise probe `get_api_version()` for `ansys_version`.
- `except Exception:` — if the probe fails: re-raise when there is no explicit override to fall back to, otherwise record `None` and continue (the override will be used).

```python
        resolved_ansys_version = ansys_version
        if resolved_ansys_version is None:
            resolved_ansys_version = validate_supported_server_install_version(
                connected_ansys_version
            )
            self._ansys_version = resolved_ansys_version
```
- Default to the caller's explicit `ansys_version`.
- When the caller gave none, validate the connected version and use it, caching it back on the instance. This is stricter than the old `get("ansys_version", self._ansys_version)` fallback: an unsupported/missing server version now raises instead of silently using the client's install version. (REVIEW.md NB-4.)

```python
        else:
            if connected_ansys_version is not None and str(connected_ansys_version) != str(
                resolved_ansys_version
            ):
                warning_message = (
                    f"Explicit HTML export ansys_version {resolved_ansys_version} does not match "
                    f"connected server version {connected_ansys_version}; continuing with the "
                    "override."
                )
                logger.warning(warning_message)
                warnings.warn(warning_message, UserWarning, stacklevel=2)
```
- When the caller **did** pass an explicit version, keep it as the source of truth, but if the connected server advertises a different version, warn (through both the logger and `warnings.warn`) that the override is winning. Probe failures are ignored here on purpose, because the override exists exactly for servers whose `/item/api_version/` is unavailable or wrong.

```python
        worker = ReportDownloadHTML(
            url=url,
            directory=directory_path,
            filename=filename,
            no_inline_files=no_inline_files,
            ansys_version=resolved_ansys_version,
        )
        worker.download()
```
- Build the downloader with the resolved version and run it. Unchanged except that `ansys_version` is now the validated/resolved value.

### 10e. `launch_local_database_server` lock handling

Two new exception handlers release the file lock and honor `raise_exception`, matching the file's existing "release on every exit path" pattern.

```python
    except UnsupportedServerVersionError:
        if local_lock:
            local_lock.release()
        if raise_exception:
            raise
        return False
```
- In the pre-launch "is a server already running here?" check: if the already-running server reports an unsupported version, release the lock and either re-raise or return `False`. This handler is placed **before** the generic `except Exception` so it is not swallowed by the "could not connect, so go ahead and launch" fallback.

```python
        except exceptions.PermissionDenied:
            stop_background_local_server(db_dir)
            if local_lock:
                local_lock.release()
            raise exceptions.ServerConnectionError(
                "Access to server denied.  Potential username/password error."
            )
        except UnsupportedServerVersionError:
            stop_background_local_server(db_dir)
            if local_lock:
                local_lock.release()
            if raise_exception:
                raise
            return False
```
- In the post-launch validation loop (after we started our own server): the `PermissionDenied` branch now also calls `local_lock.release()` (previously it could leave the lock held), and a new `UnsupportedServerVersionError` branch stops the server we just launched, releases the lock, and re-raises or returns `False`. Each branch exits the function after releasing, so there is no double release; this matches the acquire-once / release-on-each-exit structure used throughout the function.

---

## 11. Configuration and documentation changes

- **`pyproject.toml`:** removes `django-weasyprint>=2.4.0,<2.5.0` and `weasyprint>=67.0` from dependencies (the WeasyPrint path is gone), and adds `link-mode = "copy"` under `[tool.uv]` (tooling: tells uv to copy rather than hardlink packages, which avoids cross-filesystem issues). The `playwright==1.60.0` pin stays; it powers the remaining PDF path.
- **`AGENTS.md`:** the export/rendering dependency line changes from `python-pptx, weasyprint, django-weasyprint` to `python-pptx, qtpy, playwright`, matching reality after the removal.
- **`doc/source/serverless/caveats.rst`:** the compat-shim sentence now reads "known product-setting and dependency API transitions", reflecting that `_compat.py` handles the NumPy shim in addition to settings. The `Caveats` title underline is lengthened by one `=` (cosmetic; both lengths are valid RST).
- **`doc/source/examples_source/25-intermediate/00-tagging.py`:** the `Tagging` title underline is lengthened by one `=` (cosmetic, unrelated to the branch's purpose).
- **`.gitignore`:** adds `.python-version` so a local pyenv/uv Python pin is not committed.
- **`uv.lock`:** regenerated to drop the WeasyPrint dependency tree and refresh pins. Machine-generated; review by trusting the resolver plus the passing focused tests.

---

## 12. Tests (what each new/changed test proves)

No tests were changed by this review. Summary of the branch's test additions:

- **`tests/serverless/test_compat.py`** — proves the NumPy shim: sets the alias and legacy printing on NumPy 2 for 26.1, rolls both back on `restore()`, leaves an existing alias untouched, does nothing for a newer product, and rolls back partial changes if `set_printoptions` fails mid-shim. It fakes `numpy` as an injected module and patches `_get_installed_versions`, never the functions under test.
- **`tests/serverless/test_adr_setup.py`** — proves `setup()` is transactional: NumPy-compat errors become an `ImportError` with the right cause and no leftover `sys.path` entry; a failed `enve` import warns without leaving failure state; a failed settings import rolls back the shim (the restore callback is invoked and `_runtime_compat_restore` is reset). It builds a bare `ADR` and patches collaborators (`_import_enve`, `apply_runtime_compatibility_shims`, `builtins.__import__`).
- **`tests/test_compatibility.py`** — parametrized accept/reject matrix for `validate_supported_server_install_version` (supported release accepted; `None`/`"abc"`/`"1"`/`"2710"` rejected; unsupported-but-parseable rejected), plus a `Service.connect` test proving `UnsupportedServerVersionError` survives instead of becoming `NotValidServer`.
- **`tests/test_report_remote_server.py`** — proves `validate` records the supported version and exposes it, that missing/malformed/unsupported versions raise from `validate`, `get_server_name`, and the `api_version` property, and that `_download_report_as_html_bundle` uses the connected version, reuses the cached version without re-probing, rejects a missing server version, and keeps an explicit override when the probe fails.
- **`tests/serverless/test_html_exporter.py`, `tests/test_download_html.py`** — cover the 26.1 context-menu asset copy/download and directory creation, including the partial-tree and missing-file-warning behavior.
- **`tests/serverless/test_adr.py`, `tests/serverless/test_template.py`, `tests/test_report.py`** — updated for the removal of the WeasyPrint methods and to exercise the browser-PDF path via monkeypatching `_OfflinePlaywrightPDFRenderer.render_pdf` (a collaborator of the code under test, which is acceptable).

See REVIEW.md → Test Review for the quality assessment. All focused unit tests I ran pass (49 + 14; the single error is a pre-existing Docker-only integration test).
