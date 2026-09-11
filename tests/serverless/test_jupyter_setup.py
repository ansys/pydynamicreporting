# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#

"""Regression tests for serverless ADR in Jupyter."""

import asyncio
import builtins
import os
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from ansys.dynamicreporting.core.serverless import ADR
import ansys.dynamicreporting.core.serverless._compat as compat_module


class ZMQInteractiveShell:
    """Stand in for ipykernel's public shell type."""


class CustomZMQInteractiveShell(ZMQInteractiveShell):
    """Represent an application-specific shell subclass."""


def _install_ipython_shell(monkeypatch, shell):
    ipython = ModuleType("IPython")
    monkeypatch.setattr(ipython, "get_ipython", lambda: shell, raising=False)

    zmqshell = ModuleType("ipykernel.zmqshell")
    monkeypatch.setattr(zmqshell, "ZMQInteractiveShell", ZMQInteractiveShell, raising=False)
    ipykernel = ModuleType("ipykernel")
    monkeypatch.setattr(ipykernel, "__path__", [], raising=False)
    monkeypatch.setattr(ipykernel, "zmqshell", zmqshell, raising=False)

    monkeypatch.setitem(sys.modules, "IPython", ipython)
    monkeypatch.setitem(sys.modules, "ipykernel", ipykernel)
    monkeypatch.setitem(sys.modules, "ipykernel.zmqshell", zmqshell)


@pytest.fixture
def clean_async_environment(monkeypatch):
    monkeypatch.delenv("DJANGO_ALLOW_ASYNC_UNSAFE", raising=False)


@pytest.mark.unit
@pytest.mark.parametrize(
    "initial_value",
    [None, "caller-value"],
)
def test_runtime_shims_allow_django_sync_operations_in_ipykernel(
    monkeypatch, clean_async_environment, initial_value
):
    """The shim enables Django calls and restores the exact prior value."""
    from django.utils.asyncio import async_unsafe

    if initial_value is not None:
        monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", initial_value)
    _install_ipython_shell(monkeypatch, CustomZMQInteractiveShell())

    @async_unsafe("Synchronous test operation")
    def synchronous_operation():
        return "completed"

    async def run_operation():
        restore = compat_module.apply_runtime_compatibility_shims(271)
        try:
            assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == "true"
            assert synchronous_operation() == "completed"
        finally:
            restore()

    asyncio.run(run_operation())

    assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == initial_value


@pytest.mark.unit
@pytest.mark.parametrize(
    "shell_case",
    ["same-name", "missing-ipython"],
)
def test_runtime_shims_leave_other_async_environments_unchanged(
    monkeypatch, clean_async_environment, shell_case
):
    """Only genuine IPykernel shells receive the Django override."""
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "caller-value")

    if shell_case == "missing-ipython":
        monkeypatch.setitem(sys.modules, "IPython", None)
    else:
        shell = type("ZMQInteractiveShell", (), {})()
        _install_ipython_shell(monkeypatch, shell)

    async def apply_and_restore_shims():
        restore = compat_module.apply_runtime_compatibility_shims(271)
        assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == "caller-value"
        monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "after-setup")
        restore()

    asyncio.run(apply_and_restore_shims())

    assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == "after-setup"


@pytest.mark.unit
def test_runtime_shims_leave_idle_ipykernel_unchanged(monkeypatch, clean_async_environment):
    """An IPykernel shell without a running event loop keeps Django's guard."""
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "caller-value")
    _install_ipython_shell(monkeypatch, ZMQInteractiveShell())

    restore = compat_module.apply_runtime_compatibility_shims(271)
    assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == "caller-value"
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "after-setup")
    restore()

    assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == "after-setup"


@pytest.mark.unit
@pytest.mark.parametrize("failure_stage", ["settings-import", "settings-processing"])
def test_setup_restores_jupyter_environment_after_interrupt(
    tmp_path, monkeypatch, clean_async_environment, failure_stage
):
    """Both setup cleanup boundaries restore the notebook environment."""
    installation = tmp_path / "Ansys"
    adr_path = installation / "nexus271" / "django"
    adr_path.mkdir(parents=True)

    adr = object.__new__(ADR)
    adr._ansys_installation = installation
    adr._ansys_version = 271
    adr._runtime_compat_restore = None
    adr._session = None
    adr._dataset = None
    adr._logger = Mock()

    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(adr, "_warn_for_embedded_python_mismatch", lambda: None)
    monkeypatch.setattr(adr, "_import_enve", lambda _: None)
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "caller-value")
    _install_ipython_shell(monkeypatch, ZMQInteractiveShell())

    failure = KeyboardInterrupt("setup interrupted")

    if failure_stage == "settings-import":
        original_import = builtins.__import__

        def fail_settings_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "ceireports":
                assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == "true"
                raise failure
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fail_settings_import)
    else:

        class InterruptingSettings:
            def __dir__(self):
                assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == "true"
                raise failure

        ceireports = ModuleType("ceireports")
        ceireports.settings_serverless = InterruptingSettings()
        monkeypatch.setitem(sys.modules, "ceireports", ceireports)

    async def run_setup():
        adr.setup()

    with pytest.raises(KeyboardInterrupt) as exc_info:
        asyncio.run(run_setup())

    assert exc_info.value is failure
    assert ADR._is_setup is False
    assert adr._session is None
    assert adr._dataset is None
    assert adr._runtime_compat_restore is None
    assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") == "caller-value"
    if failure_stage == "settings-import":
        assert str(adr_path) not in sys.path
