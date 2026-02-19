# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from pathlib import Path

import pytest

from ansys.dynamicreporting.core import DEFAULT_ANSYS_VERSION
from ansys.dynamicreporting.core.common_utils import get_install_info, get_install_version
from ansys.dynamicreporting.core.exceptions import InvalidAnsysPath

CURRENT_VERSION = int(DEFAULT_ANSYS_VERSION)


# ansys_installation provided, valid using the legacy "CEI" folder.
@pytest.mark.ado_test
def test_get_install_info_valid_cei(tmp_path):
    # Create a fake installation directory with a legacy "CEI" subfolder.
    install_dir = tmp_path / f"install_v{CURRENT_VERSION}"
    install_dir.mkdir()
    cei_dir = install_dir / "CEI"
    cei_dir.mkdir()
    # Create the expected nexus folder structure inside CEI.
    nexus_dir = cei_dir / f"nexus{CURRENT_VERSION}" / "django"
    nexus_dir.mkdir(parents=True)
    manage_py = nexus_dir / "manage.py"
    manage_py.write_text("dummy content")

    install, ver = get_install_info(ansys_installation=str(install_dir))
    # Expect that get_install_info selects the CEI folder and extracts the version.
    assert install == str(cei_dir)
    assert ver == CURRENT_VERSION


# ansys_installation provided, valid using the new "ADR" folder (v271+ layout).
@pytest.mark.ado_test
def test_get_install_info_valid_adr(tmp_path):
    # Create a fake installation directory with the new "ADR" subfolder.
    install_dir = tmp_path / f"install_v{CURRENT_VERSION}"
    install_dir.mkdir()
    adr_dir = install_dir / "ADR"
    adr_dir.mkdir()
    # Create the expected nexus folder structure inside ADR.
    nexus_dir = adr_dir / f"nexus{CURRENT_VERSION}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    install, ver = get_install_info(ansys_installation=str(install_dir))
    # ADR/ should be selected as the installation directory.
    assert install == str(adr_dir)
    assert ver == CURRENT_VERSION


# When both "ADR" and "CEI" exist, "ADR" (new layout) takes priority.
@pytest.mark.ado_test
def test_get_install_info_adr_takes_priority_over_cei(tmp_path):
    install_dir = tmp_path / f"install_v{CURRENT_VERSION}"
    install_dir.mkdir()
    # Create both ADR and CEI subdirectories with valid nexus structures.
    for subdir in ["ADR", "CEI"]:
        d = install_dir / subdir
        d.mkdir()
        nexus_dir = d / f"nexus{CURRENT_VERSION}" / "django"
        nexus_dir.mkdir(parents=True)
        (nexus_dir / "manage.py").write_text("dummy content")

    install, ver = get_install_info(ansys_installation=str(install_dir))
    # ADR/ should take priority over CEI/ since it is checked first.
    assert install == str(install_dir / "ADR")
    assert ver == CURRENT_VERSION


# ansys_installation provided, valid using the base directory (when neither ADR nor CEI folder exists).
@pytest.mark.ado_test
def test_get_install_info_valid_base(tmp_path):
    # Create a fake installation directory without an "ADR" or "CEI" subfolder.
    install_dir = tmp_path / f"install_v{CURRENT_VERSION}"
    install_dir.mkdir()
    # Create the required nexus folder structure directly in the base installation directory.
    nexus_dir = install_dir / f"nexus{CURRENT_VERSION}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    install, ver = get_install_info(ansys_installation=str(install_dir))
    # Since neither 'install_dir/ADR' nor 'install_dir/CEI' exist, pick install_dir.
    assert install == str(install_dir)
    assert ver == CURRENT_VERSION


# ansys_installation provided, but missing required nexus folder structure → raises InvalidAnsysPath.
@pytest.mark.ado_test
def test_get_install_info_invalid_missing_manage(tmp_path):
    install_dir = tmp_path / f"install_v{CURRENT_VERSION}"
    install_dir.mkdir()
    # Create "ADR" and "CEI" folders but do not create the required nexus folder structure.
    (install_dir / "ADR").mkdir()
    (install_dir / "CEI").mkdir()

    with pytest.raises(InvalidAnsysPath):
        get_install_info(ansys_installation=str(install_dir))


# ansys_installation is None, but PYADR_ANSYS_INSTALLATION is set to a valid installation (ADR layout).
@pytest.mark.ado_test
def test_get_install_info_env_pyadr_valid_adr(tmp_path, monkeypatch):
    env_dir = tmp_path / f"env_install_v{CURRENT_VERSION}"
    env_dir.mkdir()
    # Create a valid ADR structure (new layout) inside the env directory.
    adr_dir = env_dir / "ADR"
    adr_dir.mkdir()
    nexus_dir = adr_dir / f"nexus{CURRENT_VERSION}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    monkeypatch.setenv("PYADR_ANSYS_INSTALLATION", str(env_dir))
    install, ver = get_install_info()
    # ADR/ is checked first, so it should be selected.
    assert install == str(adr_dir)
    assert ver == CURRENT_VERSION


# ansys_installation is None, but PYADR_ANSYS_INSTALLATION is set to a valid installation (legacy CEI layout).
@pytest.mark.ado_test
def test_get_install_info_env_pyadr_valid_cei(tmp_path, monkeypatch):
    env_dir = tmp_path / f"env_install_v{CURRENT_VERSION}"
    env_dir.mkdir()
    # Create a valid CEI structure (legacy layout) inside the env directory.
    cei_dir = env_dir / "CEI"
    cei_dir.mkdir()
    nexus_dir = cei_dir / f"nexus{CURRENT_VERSION}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    monkeypatch.setenv("PYADR_ANSYS_INSTALLATION", str(env_dir))
    install, ver = get_install_info()
    # Only CEI/ exists, so it should be selected as fallback.
    assert install == str(cei_dir)
    assert ver == CURRENT_VERSION


# ansys_installation is None and AWP_ROOT{CURRENT_VERSION} with ADR layout.
@pytest.mark.ado_test
def test_get_install_info_env_awp_valid_adr(tmp_path, monkeypatch):
    awp_var = f"AWP_ROOT{CURRENT_VERSION}"
    awp_dir = tmp_path / f"awp_install_v{CURRENT_VERSION}"
    awp_dir.mkdir()
    # Create a valid ADR structure (new layout).
    adr_dir = awp_dir / "ADR"
    adr_dir.mkdir()
    nexus_dir = adr_dir / f"nexus{CURRENT_VERSION}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    monkeypatch.setenv(awp_var, str(awp_dir))
    # Ensure PYADR_ANSYS_INSTALLATION is not set.
    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)

    install, ver = get_install_info()
    # ADR/ should be selected.
    assert install == str(adr_dir)
    assert ver == CURRENT_VERSION


# ansys_installation is None and AWP_ROOT{CURRENT_VERSION} with legacy CEI layout.
@pytest.mark.ado_test
def test_get_install_info_env_awp_valid_cei(tmp_path, monkeypatch):
    awp_var = f"AWP_ROOT{CURRENT_VERSION}"
    awp_dir = tmp_path / f"awp_install_v{CURRENT_VERSION}"
    awp_dir.mkdir()
    # Create a valid CEI structure (legacy layout).
    cei_dir = awp_dir / "CEI"
    cei_dir.mkdir()
    nexus_dir = cei_dir / f"nexus{CURRENT_VERSION}" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    monkeypatch.setenv(awp_var, str(awp_dir))
    # Ensure PYADR_ANSYS_INSTALLATION is not set.
    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)

    install, ver = get_install_info()
    # Only CEI/ exists, so it should be selected as fallback.
    assert install == str(cei_dir)
    assert ver == CURRENT_VERSION


# ansys_installation is None and no valid installation is found.
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


# ansys_installation provided with no version in its path but with a provided ansys_version.
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


# Test the branch for a valid 'enve' candidate.
@pytest.mark.ado_test
def test_get_install_info_with_enve(monkeypatch, tmp_path):
    # Create a fake candidate directory for enve.home().
    fake_enve_dir = tmp_path / "fake_enve_home" / "v253"
    fake_enve_dir.mkdir(parents=True)

    # Create a fake enve module with a home() function returning our candidate.
    fake_enve = type("FakeEnve", (), {"home": lambda: fake_enve_dir})
    monkeypatch.setitem(__import__("sys").modules, "enve", fake_enve)

    # Remove interfering environment variables.
    for var in ["PYADR_ANSYS_INSTALLATION", "CEIDEVROOTDOS", f"AWP_ROOT{CURRENT_VERSION}"]:
        monkeypatch.delenv(var, raising=False)

    # Monkeypatch Path.is_dir so that our fake enve candidate is the only valid directory.
    def fake_is_dir(self):
        if str(self) == str(fake_enve_dir):
            return True
        return False

    monkeypatch.setattr(Path, "is_dir", fake_is_dir)

    install, ver = get_install_info()
    assert install == str(fake_enve_dir)
    # get_install_version should extract 253 from "v253".
    assert ver == 253


@pytest.mark.ado_test
def test_get_install_info_with_ceidev(monkeypatch, tmp_path):
    # Create a candidate directory for CEIDEVROOTDOS.
    ceidev_dir = tmp_path / "ceidev_install" / f"v{CURRENT_VERSION}"
    ceidev_dir.mkdir(parents=True)

    # Set the environment variable CEIDEVROOTDOS to our candidate.
    monkeypatch.setenv("CEIDEVROOTDOS", str(ceidev_dir))

    # Remove other environment variables that may interfere.
    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)
    monkeypatch.delenv(f"AWP_ROOT{CURRENT_VERSION}", raising=False)

    # Force the import of 'enve' to fail (so its candidate is not added).
    monkeypatch.setitem(__import__("sys").modules, "enve", None)

    def fake_is_dir(self):
        if str(self) == str(ceidev_dir):
            return True
        # For all other paths (e.g. the common default), return False.
        return False

    monkeypatch.setattr(Path, "is_dir", fake_is_dir)

    install, ver = get_install_info()
    assert install == str(ceidev_dir)
    assert ver == CURRENT_VERSION
