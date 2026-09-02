# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#

"""Unit tests for serverless ADR initialization."""

import asyncio
import os
import sys
from types import ModuleType

import pytest

from ansys.dynamicreporting.core.serverless import ADR


@pytest.fixture
def clean_async_environment(monkeypatch):
    """Unset the override and clean up values added by ADR during a test."""
    monkeypatch.delenv("DJANGO_ALLOW_ASYNC_UNSAFE", raising=False)
    yield
    os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)


@pytest.fixture(params=[None, "", "caller-value"])
def jupyter_async_environment(monkeypatch, request, clean_async_environment):
    """Run in an IPykernel shell with an unset or caller-supplied override."""
    initial_value = request.param
    if initial_value is not None:
        monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", initial_value)

    shell = type("ZMQInteractiveShell", (), {})()
    ipython = ModuleType("IPython")
    monkeypatch.setattr(ipython, "get_ipython", lambda: shell, raising=False)
    monkeypatch.setitem(sys.modules, "IPython", ipython)
    return initial_value


@pytest.mark.unit
def test_setup_allows_django_sync_operations_in_jupyter(
    monkeypatch, jupyter_async_environment, setup_runtime
):
    """Notebook setup keeps the override until close restores the caller's value."""
    from django.utils.asyncio import async_unsafe

    import ansys.dynamicreporting.core.serverless.adr as adr_module

    adr = setup_runtime
    session = object()
    close_values = []

    @async_unsafe("Synchronous test operation")
    def create_session():
        return session

    monkeypatch.setattr(adr_module.Session, "create", create_session)
    monkeypatch.setattr(
        adr_module.connections,
        "close_all",
        lambda: close_values.append(os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")),
    )

    async def run_operation():
        adr.setup()
        assert ADR._is_setup is True
        assert adr._session is session
        assert adr._dataset is not None
        assert create_session() is session

        with pytest.raises(RuntimeError, match="ADR has already been configured"):
            adr.setup()

        active_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
        assert active_value == "true"
        adr.close()

    asyncio.run(run_operation())
    assert close_values == ["true"]
    restored_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    assert restored_value == jupyter_async_environment
    assert adr._runtime_compat_restore is None

    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "after-close")
    adr.close()

    assert close_values == ["true", "after-close"]
    current_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    assert current_value == "after-close"


@pytest.mark.unit
@pytest.mark.parametrize("product_version", [261, 271])
def test_runtime_shims_override_and_restore_jupyter_environment(
    jupyter_async_environment, product_version
):
    """Notebook support applies to both product lines and backs up any value."""
    from ansys.dynamicreporting.core.serverless._compat import apply_runtime_compatibility_shims

    restore = apply_runtime_compatibility_shims(product_version)
    try:
        active_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
        assert active_value == "true"
    finally:
        restore()

    restored_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    assert restored_value == jupyter_async_environment


@pytest.mark.unit
@pytest.mark.parametrize("shell_name", [None, "TerminalInteractiveShell", "missing-ipython"])
@pytest.mark.parametrize("initial_value", [None, "", "caller-value"])
def test_runtime_shims_leave_non_notebook_environment_unchanged(
    monkeypatch, clean_async_environment, shell_name, initial_value
):
    """Regular Python and terminal IPython keep their existing Django behavior."""
    from ansys.dynamicreporting.core.serverless._compat import apply_runtime_compatibility_shims

    environment_variable = "DJANGO_ALLOW_ASYNC_UNSAFE"
    if initial_value is not None:
        monkeypatch.setenv(environment_variable, initial_value)

    if shell_name == "missing-ipython":
        monkeypatch.setitem(sys.modules, "IPython", None)
    else:
        shell = None if shell_name is None else type(shell_name, (), {})()
        ipython = ModuleType("IPython")
        monkeypatch.setattr(ipython, "get_ipython", lambda: shell, raising=False)
        monkeypatch.setitem(sys.modules, "IPython", ipython)

    restore = apply_runtime_compatibility_shims(271)
    active_value = os.environ.get(environment_variable)
    assert active_value == initial_value
    monkeypatch.setenv(environment_variable, "after-setup")
    restore()

    current_value = os.environ.get(environment_variable)
    assert current_value == "after-setup"


@pytest.mark.unit
@pytest.mark.parametrize("failure_type", [RuntimeError, KeyboardInterrupt])
def test_setup_leaves_jupyter_environment_unchanged_before_runtime_initialization(
    tmp_path, monkeypatch, jupyter_async_environment, failure_type
):
    """Preliminary installation checks run before any notebook environment change."""
    adr = object.__new__(ADR)
    adr._ansys_installation = tmp_path
    adr._ansys_version = 261
    monkeypatch.setattr(ADR, "_is_setup", False)

    failure = failure_type("embedded Python check failed")

    def fail_embedded_python_check():
        actual_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
        assert actual_value == jupyter_async_environment
        raise failure

    monkeypatch.setattr(adr, "_warn_for_embedded_python_mismatch", fail_embedded_python_check)

    with pytest.raises(failure_type) as exc_info:
        adr.setup()

    assert exc_info.value is failure
    final_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    assert final_value == jupyter_async_environment


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
def test_setup_warns_when_enve_import_fails(tmp_path, monkeypatch):
    """A failed native import warns without retaining process-wide failure state."""
    from unittest.mock import Mock

    import ansys.dynamicreporting.core.serverless._compat as compat_module

    installation = tmp_path / "Ansys"
    adr_path = installation / "nexus261" / "django"
    adr_path.mkdir(parents=True)

    adr = object.__new__(ADR)
    adr._ansys_installation = installation
    adr._ansys_version = 261
    adr._runtime_compat_restore = None
    adr._logger = Mock()
    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(adr, "_warn_for_embedded_python_mismatch", lambda: None)

    enve_error = ImportError("DLL load failed while importing enve: missing dependency")
    monkeypatch.setattr(adr, "_import_enve", lambda _: enve_error)

    setup_error = ImportError("serverless settings could not be imported")

    def raise_setup_error(_):
        raise setup_error

    monkeypatch.setattr(compat_module, "apply_runtime_compatibility_shims", raise_setup_error)

    with pytest.warns(UserWarning, match="Animation rendering is unavailable") as warnings_record:
        with pytest.raises(ImportError, match="Failed to initialize ADR") as exc_info:
            adr.setup()

    assert exc_info.value.__cause__ is setup_error
    assert str(enve_error) in str(warnings_record[0].message)
    assert warnings_record[0].filename == __file__
    adr._logger.warning.assert_called_once()
    assert not hasattr(adr, "_enve_import_error")
    assert str(adr_path) not in sys.path


@pytest.mark.unit
@pytest.mark.parametrize("failure_type", [ImportError, RuntimeError, KeyboardInterrupt])
def test_setup_rolls_back_runtime_compatibility_after_settings_import_failure(
    monkeypatch, jupyter_async_environment, setup_runtime, failure_type
):
    """A failed settings import must not leave process-wide setup state behind."""
    import builtins

    adr = setup_runtime
    adr_path = adr._ansys_installation / "nexus261" / "django"
    failure = failure_type("serverless settings could not be imported")
    original_import = builtins.__import__

    def fail_settings_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ceireports":
            active_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
            assert active_value == "true"
            raise failure
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fail_settings_import)

    with pytest.raises(failure_type) as exc_info:
        adr.setup()

    if failure_type is ImportError:
        assert exc_info.value.__cause__ is failure
        assert "Failed to initialize ADR" in str(exc_info.value)
    else:
        assert exc_info.value is failure
    assert adr._runtime_compat_restore is None
    assert str(adr_path) not in sys.path
    final_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    assert final_value == jupyter_async_environment


@pytest.fixture
def setup_runtime(tmp_path, monkeypatch):
    """Isolate product imports while running ADR's setup and runtime shims."""
    import django
    from types import ModuleType, SimpleNamespace
    from unittest.mock import Mock

    import ansys.dynamicreporting.core.serverless._compat as compat_module
    import ansys.dynamicreporting.core.serverless.adr as adr_module

    installation = tmp_path / "Ansys"
    adr_path = installation / "nexus261" / "django"
    adr_path.mkdir(parents=True)
    media_directory = tmp_path / "media"
    media_directory.mkdir()

    adr = object.__new__(ADR)
    adr._ansys_installation = installation
    adr._ansys_version = 261
    adr._db_directory = None
    adr._databases = {}
    adr._media_directory = media_directory
    adr._static_directory = None
    adr._media_url = "/media/"
    adr._static_url = "/static/"
    adr._debug = None
    adr._in_memory = False
    adr._session = None
    adr._dataset = None
    adr._runtime_compat_restore = None
    adr._tmp_dirs = []
    adr._logger = Mock()

    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(adr, "_warn_for_embedded_python_mismatch", lambda: None)
    monkeypatch.setattr(adr, "_import_enve", lambda _: None)
    monkeypatch.setattr(ADR, "get_database_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(adr_module.report_utils, "apply_timezone_workaround", lambda: None)
    monkeypatch.setattr(compat_module, "sanitize_settings", lambda overrides: overrides)
    monkeypatch.setattr(adr_module.connections, "close_all", lambda: None)

    settings_serverless = ModuleType("ceireports.settings_serverless")
    settings_serverless.SECRET_KEY = "test-secret"
    ceireports = ModuleType("ceireports")
    ceireports.settings_serverless = settings_serverless
    monkeypatch.setitem(sys.modules, "ceireports", ceireports)
    monkeypatch.setitem(sys.modules, "ceireports.settings_serverless", settings_serverless)

    data_module = ModuleType("data")
    data_module.__path__ = []
    geometry_module = ModuleType("data.geofile_rendering")
    geometry_module.do_geometry_update_check = lambda _: None
    monkeypatch.setitem(sys.modules, "data", data_module)
    monkeypatch.setitem(sys.modules, "data.geofile_rendering", geometry_module)

    fake_settings = SimpleNamespace(configured=False)
    fake_settings.configure = lambda **kwargs: setattr(fake_settings, "configured", True)
    fake_django_conf = ModuleType("django.conf")
    fake_django_conf.settings = fake_settings
    monkeypatch.setitem(sys.modules, "django.conf", fake_django_conf)
    monkeypatch.setattr(django, "setup", lambda: None)

    monkeypatch.setattr(
        adr_module,
        "Session",
        SimpleNamespace(create=lambda: object()),
    )
    monkeypatch.setattr(adr_module, "Dataset", SimpleNamespace(create=lambda: object()))

    yield adr

    adr._restore_runtime_compatibility_shims()


@pytest.mark.unit
@pytest.mark.parametrize("failure_type", [RuntimeError, KeyboardInterrupt])
def test_setup_rolls_back_state_after_dataset_creation_failure(
    monkeypatch, jupyter_async_environment, setup_runtime, failure_type
):
    """A late setup failure must restore session, dataset, and runtime state."""
    import ansys.dynamicreporting.core.serverless.adr as adr_module

    adr = setup_runtime
    dataset_error = failure_type("dataset creation failed")

    def create_dataset():
        assert ADR._is_setup is True
        assert adr._session is not None
        active_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
        assert active_value == "true"
        raise dataset_error

    monkeypatch.setattr(adr_module.Dataset, "create", create_dataset)

    with pytest.raises(failure_type) as exc_info:
        adr.setup()

    assert exc_info.value is dataset_error
    assert ADR._is_setup is False
    assert adr._session is None
    assert adr._dataset is None
    assert adr._runtime_compat_restore is None
    final_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    assert final_value == jupyter_async_environment


@pytest.mark.unit
@pytest.mark.parametrize("failure_type", [TypeError, KeyboardInterrupt])
def test_setup_restores_jupyter_environment_after_runtime_shim_failure(
    monkeypatch, jupyter_async_environment, setup_runtime, failure_type
):
    """A partial NumPy shim failure also restores the notebook environment."""
    fake_numpy = ModuleType("numpy")
    fake_numpy.__version__ = "2.0.0"
    fake_numpy.bytes_ = object()
    fake_numpy.get_printoptions = lambda: {"legacy": False}
    failure = failure_type("NumPy print options failed")

    def fail_print_options(**kwargs):
        active_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
        assert active_value == "true"
        assert fake_numpy.string_ is fake_numpy.bytes_
        raise failure

    fake_numpy.set_printoptions = fail_print_options
    monkeypatch.setitem(sys.modules, "numpy", fake_numpy)

    expected_error = ImportError if failure_type is TypeError else failure_type
    with pytest.raises(expected_error) as exc_info:
        setup_runtime.setup()

    if failure_type is TypeError:
        assert exc_info.value.__cause__ is failure
    else:
        assert exc_info.value is failure
    assert not hasattr(fake_numpy, "string_")
    assert setup_runtime._runtime_compat_restore is None
    restored_value = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    assert restored_value == jupyter_async_environment
