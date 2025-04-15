import os
from pathlib import Path

import pytest

from ansys.dynamicreporting.core import DEFAULT_ANSYS_VERSION
from ansys.dynamicreporting.core.common_utils import get_install_info
from ansys.dynamicreporting.core.exceptions import InvalidAnsysPath

CURRENT_VERSION = int(DEFAULT_ANSYS_VERSION)


# Test 1: ansys_installation provided, valid using the "CEI" folder.
@pytest.mark.ado_test
def test_get_install_info_valid_cei(tmp_path):
    version = 252
    # Create a fake installation directory with a "CEI" subfolder.
    install_dir = tmp_path / f"install_v{version}"
    install_dir.mkdir()
    cei_dir = install_dir / "CEI"
    cei_dir.mkdir()
    # Create the expected nexus folder structure inside CEI.
    nexus_dir = cei_dir / f"nexus{version}" / "django"
    nexus_dir.mkdir(parents=True)
    manage_py = nexus_dir / "manage.py"
    manage_py.write_text("dummy content")

    install, ver = get_install_info(ansys_installation=str(install_dir))
    # Expect that get_install_info selects the CEI folder and extracts the version.
    assert install == str(cei_dir)
    assert ver == version


# Test 2: ansys_installation provided, valid using the base directory (when CEI folder is absent).
@pytest.mark.ado_test
def test_get_install_info_valid_base(tmp_path):
    version = 252
    # Create a fake installation directory without a "CEI" subfolder.
    install_dir = tmp_path / f"install_v{version}"
    install_dir.mkdir()
    # Create the required nexus folder structure directly in the base installation directory.
    nexus_dir = install_dir / f"nexus{version}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    install, ver = get_install_info(ansys_installation=str(install_dir))
    # Since 'install_dir/CEI' does not exist, the function should pick install_dir.
    assert install == str(install_dir)
    assert ver == version


# Test 3: ansys_installation provided, but missing required nexus folder structure → raises InvalidAnsysPath.
@pytest.mark.ado_test
def test_get_install_info_invalid_missing_manage(tmp_path):
    version = 252
    install_dir = tmp_path / f"install_v{version}"
    install_dir.mkdir()
    # Create a "CEI" folder but do not create the required nexus folder structure.
    (install_dir / "CEI").mkdir()

    with pytest.raises(InvalidAnsysPath):
        get_install_info(ansys_installation=str(install_dir))


# Test 4: ansys_installation is None, but PYADR_ANSYS_INSTALLATION is set to a valid installation.
@pytest.mark.ado_test
def test_get_install_info_env_pyadr_valid(tmp_path, monkeypatch):
    version = 252
    env_dir = tmp_path / f"env_install_v{version}"
    env_dir.mkdir()
    # Create a valid CEI structure inside the env directory.
    cei_dir = env_dir / "CEI"
    cei_dir.mkdir()
    nexus_dir = cei_dir / f"nexus{version}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    monkeypatch.setenv("PYADR_ANSYS_INSTALLATION", str(env_dir))
    install, ver = get_install_info()
    assert install == str(cei_dir)
    assert ver == version


# Test 5: ansys_installation is None and AWP_ROOT{CURRENT_VERSION} is set to a valid installation.
@pytest.mark.ado_test
def test_get_install_info_env_awp_valid(tmp_path, monkeypatch):
    version = 252
    awp_var = f"AWP_ROOT{CURRENT_VERSION}"
    awp_dir = tmp_path / f"awp_install_v{version}"
    awp_dir.mkdir()
    # Create a valid CEI structure.
    cei_dir = awp_dir / "CEI"
    cei_dir.mkdir()
    nexus_dir = cei_dir / f"nexus{version}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    monkeypatch.setenv(awp_var, str(awp_dir))
    # Ensure PYADR_ANSYS_INSTALLATION is not set.
    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)

    install, ver = get_install_info()
    assert install == str(cei_dir)
    assert ver == version


# Test 6: ansys_installation is None and no valid installation is found.
# We simulate this by forcing all candidate directories to report they are not directories.
@pytest.mark.ado_test
def test_get_install_info_none_no_valid(monkeypatch):
    # Remove relevant environment variables.
    for var in ["PYADR_ANSYS_INSTALLATION", f"AWP_ROOT{CURRENT_VERSION}", "CEIDEVROOTDOS"]:
        monkeypatch.delenv(var, raising=False)
    # Override is_dir to always return False.
    monkeypatch.setattr(Path, "is_dir", lambda self: False)

    install, ver = get_install_info()
    # No directory found; installation should be None and version defaults to CURRENT_VERSION.
    assert install is None
    assert ver == CURRENT_VERSION


# Test 7: ansys_installation provided with no version in its path but with a provided ansys_version.
@pytest.mark.ado_test
def test_get_install_info_provided_ansys_version(tmp_path):
    provided_version = 300
    # Create a directory without a version pattern in its name.
    install_dir = tmp_path / "install_no_version"
    install_dir.mkdir()
    # Do not create a CEI folder so that the base directory itself is used.
    # Create the required nexus folder structure using the provided version.
    nexus_dir = install_dir / f"nexus{provided_version}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    install, ver = get_install_info(
        ansys_installation=str(install_dir), ansys_version=provided_version
    )
    # Expect the base directory is returned and version equals the provided version.
    assert install == str(install_dir)
    assert ver == provided_version
