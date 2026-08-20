# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#

"""Unit tests for serverless ADR initialization failures."""

import sys

import pytest

from ansys.dynamicreporting.core.serverless import ADR


@pytest.mark.unit
@pytest.mark.parametrize("compatibility_error", [AttributeError, TypeError, ValueError])
def test_setup_wraps_runtime_compatibility_errors(tmp_path, monkeypatch, compatibility_error):
    """Expected NumPy compatibility errors should have an ADR initialization error."""
    import ansys.dynamicreporting.core.serverless._compat as compat_module

    installation = tmp_path / "Ansys"
    adr_path = installation / "nexus261" / "django"
    adr_path.mkdir(parents=True)

    adr = object.__new__(ADR)
    adr._ansys_installation = installation
    adr._ansys_version = 261
    adr._runtime_compat_restore = None
    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(adr, "_warn_for_embedded_python_mismatch", lambda: None)
    monkeypatch.setattr(adr, "_import_enve", lambda _: None)

    error = compatibility_error("unsupported NumPy compatibility operation")

    def raise_compatibility_error(_):
        raise error

    monkeypatch.setattr(
        compat_module,
        "apply_runtime_compatibility_shims",
        raise_compatibility_error,
    )

    with pytest.raises(ImportError, match="Failed to initialize ADR") as exc_info:
        adr.setup()

    assert exc_info.value.__cause__ is error
    assert str(adr_path) not in sys.path


@pytest.mark.unit
def test_setup_rolls_back_runtime_compatibility_after_settings_import_failure(
    tmp_path, monkeypatch
):
    """A failed settings import must not leave process-wide setup state behind."""
    import builtins

    import ansys.dynamicreporting.core.serverless._compat as compat_module

    installation = tmp_path / "Ansys"
    adr_path = installation / "nexus261" / "django"
    adr_path.mkdir(parents=True)

    adr = object.__new__(ADR)
    adr._ansys_installation = installation
    adr._ansys_version = 261
    adr._runtime_compat_restore = None
    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(adr, "_warn_for_embedded_python_mismatch", lambda: None)
    monkeypatch.setattr(adr, "_import_enve", lambda _: None)

    restore_calls: list[str] = []
    monkeypatch.setattr(
        compat_module,
        "apply_runtime_compatibility_shims",
        lambda _: lambda: restore_calls.append("restored"),
    )
    original_import = builtins.__import__

    def fail_settings_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ceireports":
            raise ImportError("serverless settings could not be imported")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_settings_import)

    with pytest.raises(ImportError, match="Failed to initialize ADR") as exc_info:
        adr.setup()

    assert isinstance(exc_info.value.__cause__, ImportError)
    assert restore_calls == ["restored"]
    assert adr._runtime_compat_restore is None
    assert str(adr_path) not in sys.path
