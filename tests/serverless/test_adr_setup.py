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
    adr._logger.warning.assert_called_once()
    assert not hasattr(adr, "_enve_import_error")
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


@pytest.mark.unit
def test_setup_rolls_back_state_after_dataset_creation_failure(tmp_path, monkeypatch):
    """A late setup failure must restore session, dataset, and runtime state."""
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
    adr._logger = Mock()

    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(adr, "_warn_for_embedded_python_mismatch", lambda: None)
    monkeypatch.setattr(adr, "_import_enve", lambda _: None)
    monkeypatch.setattr(ADR, "get_database_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(adr_module.report_utils, "apply_timezone_workaround", lambda: None)
    monkeypatch.setattr(compat_module, "sanitize_settings", lambda overrides: overrides)

    restore_calls: list[str] = []
    monkeypatch.setattr(
        compat_module,
        "apply_runtime_compatibility_shims",
        lambda _: lambda: restore_calls.append("restored"),
    )

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
    original_import = __import__

    def import_fake_django_conf(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "django.conf":
            return fake_django_conf
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", import_fake_django_conf)
    monkeypatch.setattr(django, "setup", lambda: None)

    session_sentinel = object()
    dataset_error = RuntimeError("dataset creation failed")

    monkeypatch.setattr(
        adr_module,
        "Session",
        SimpleNamespace(create=lambda: session_sentinel),
    )

    def create_dataset():
        assert ADR._is_setup is True
        assert adr._session is session_sentinel
        raise dataset_error

    monkeypatch.setattr(adr_module, "Dataset", SimpleNamespace(create=create_dataset))

    with pytest.raises(RuntimeError) as exc_info:
        adr.setup()

    assert exc_info.value is dataset_error
    assert ADR._is_setup is False
    assert adr._session is None
    assert adr._dataset is None
    assert restore_calls == ["restored"]
    assert adr._runtime_compat_restore is None


def _construct_adr_without_install(monkeypatch, tmp_path, **kwargs) -> ADR:
    """Build an ADR with directory handling only, stubbing installation discovery."""
    from ansys.dynamicreporting.core.common_utils import InstallResolution
    import ansys.dynamicreporting.core.serverless.adr as adr_module

    install_root = tmp_path / "install"
    install_root.mkdir(exist_ok=True)
    monkeypatch.setattr(
        adr_module,
        "resolve_install_info",
        lambda **_: InstallResolution(install_dir=str(install_root), version=261),
    )
    monkeypatch.setattr(adr_module, "get_compatibility_warning_for_install_version", lambda _: None)
    # Keep the secret key and directory variables from leaking between tests.
    for variable in (
        "CEI_NEXUS_SECRET_KEY",
        "CEI_NEXUS_LOCAL_DB_DIR",
        "CEI_NEXUS_LOCAL_MEDIA_DIR",
    ):
        monkeypatch.delenv(variable, raising=False)
    return ADR(**kwargs)


@pytest.mark.unit
@pytest.mark.parametrize("precreate", [False, True], ids=["missing", "existing-empty"])
def test_default_media_directory_is_created(tmp_path, monkeypatch, precreate):
    """A missing or existing-but-empty db_directory gets <db_directory>/media."""
    db_directory = tmp_path / "db"
    if precreate:
        db_directory.mkdir()

    adr = _construct_adr_without_install(monkeypatch, tmp_path, db_directory=str(db_directory))

    assert (db_directory / "media").is_dir()
    assert adr.media_directory == str(db_directory / "media")


@pytest.mark.unit
def test_missing_db_directory_gets_viewer_token(tmp_path, monkeypatch):
    """Only a newly created db_directory gets a secret key and viewer token."""
    db_directory = tmp_path / "db"

    _construct_adr_without_install(monkeypatch, tmp_path, db_directory=str(db_directory))

    assert (db_directory / "view_report.nexdb").is_file()


@pytest.mark.unit
def test_external_media_directory_is_not_duplicated_in_db_directory(tmp_path, monkeypatch):
    """With media outside the database, no stray <db_directory>/media is created."""
    db_directory = tmp_path / "db"
    media_directory = tmp_path / "elsewhere" / "media"

    adr = _construct_adr_without_install(
        monkeypatch,
        tmp_path,
        db_directory=str(db_directory),
        media_directory=str(media_directory),
    )

    assert media_directory.is_dir()
    assert adr.media_directory == str(media_directory)
    assert not (db_directory / "media").exists()


@pytest.mark.unit
def test_populated_db_directory_is_not_reinitialized(tmp_path, monkeypatch):
    """An existing database directory is used as-is, without a new viewer token."""
    db_directory = tmp_path / "db"
    (db_directory / "media").mkdir(parents=True)
    (db_directory / "db.sqlite3").touch()

    adr = _construct_adr_without_install(monkeypatch, tmp_path, db_directory=str(db_directory))

    assert not (db_directory / "view_report.nexdb").exists()
    assert adr.media_directory == str(db_directory / "media")
