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

import json
from pathlib import Path

import pytest

from ansys.dynamicreporting.core import DEFAULT_ANSYS_VERSION
from ansys.dynamicreporting.core.compatibility import (
    AUTO_DETECT_INSTALL_VERSIONS,
    DEFAULT_ANSYS_INSTALL_VERSION,
)
import ansys.dynamicreporting.core.common_utils as common_utils_module
from ansys.dynamicreporting.core.common_utils import (
    PlaywrightBrowserBinaryInfo,
    get_install_info,
    get_install_version,
    resolve_playwright_browsers_path,
)
from ansys.dynamicreporting.core.exceptions import InvalidAnsysPath

CURRENT_VERSION = int(DEFAULT_ANSYS_VERSION)


def _packaged_playwright_metadata(
    *,
    machine_arch: str,
    revision: str = "1223",
    packaged_binary_dir: str | None = None,
    playwright_version: str = "1.60.0",
    browser_name: str | None = None,
    browser_version: str = "148.0.7778.96",
    build_commit: str = "",
) -> dict[str, str]:
    """Build packaged Playwright metadata from the production dataclass schema."""
    return PlaywrightBrowserBinaryInfo(
        path=Path("playwright-browsers"),
        build_commit=build_commit,
        browser_name=browser_name or PlaywrightBrowserBinaryInfo.EXPECTED_BROWSER_NAME,
        browser_version=browser_version,
        machine_arch=machine_arch,
        packaged_binary_dir=packaged_binary_dir or f"chromium_headless_shell-{revision}",
        playwright_version=playwright_version,
        revision=revision,
    ).to_metadata_dict()


def _create_packaged_playwright_binary(
    machine_root: Path,
    *,
    machine_arch: str,
    revision: str = "1223",
    packaged_binary_dir: str | None = None,
    write_metadata: bool = True,
    create_marker: bool = True,
) -> Path:
    """Create a minimal packaged Playwright binary that matches the ADR layout contract."""
    browser_binary_dir = machine_root / "playwright-browsers"
    packaged_dir_name = packaged_binary_dir or f"chromium_headless_shell-{revision}"
    packaged_dir = browser_binary_dir / packaged_dir_name
    packaged_dir.mkdir(parents=True)
    if create_marker:
        (packaged_dir / "INSTALLATION_COMPLETE").write_text("", encoding="utf-8")

    if write_metadata:
        metadata = _packaged_playwright_metadata(
            machine_arch=machine_arch,
            revision=revision,
            packaged_binary_dir=packaged_dir_name,
        )
        (browser_binary_dir / "playwright_browser_metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return browser_binary_dir


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


# ansys_installation provided, valid using the new "ADR" folder layout.
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


@pytest.mark.ado_test
def test_get_install_info_implicit_falls_back_to_261_when_271_is_unavailable(monkeypatch, tmp_path):
    released_dir = tmp_path / "v261" / "ADR"
    released_dir.mkdir(parents=True)

    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)
    monkeypatch.delenv(f"AWP_ROOT{CURRENT_VERSION}", raising=False)
    monkeypatch.setenv("AWP_ROOT261", str(released_dir.parent))
    monkeypatch.delenv("CEIDEVROOTDOS", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "enve", None)

    # With no bundled-line install available, the released compatibility
    # fallback should still keep implicit discovery useful.
    install, ver = get_install_info()
    assert install == str(released_dir)
    assert ver == 261


@pytest.mark.ado_test
def test_get_install_info_implicit_prefers_271_over_261(monkeypatch, tmp_path):
    compatibility_dir = tmp_path / "v261" / "ADR"
    compatibility_dir.mkdir(parents=True)
    bundled_dir = tmp_path / "v271" / "ADR"
    bundled_dir.mkdir(parents=True)

    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)
    monkeypatch.setenv("AWP_ROOT261", str(compatibility_dir.parent))
    monkeypatch.setenv("AWP_ROOT271", str(bundled_dir.parent))
    monkeypatch.delenv("AWP_ROOT251", raising=False)
    monkeypatch.delenv("CEIDEVROOTDOS", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "enve", None)

    # Keep the default constructors aligned with the historical bundled-line
    # behavior from ``main`` whenever both installs are present.
    install, ver = get_install_info()
    assert install == str(bundled_dir)
    assert ver == 271


@pytest.mark.ado_test
def test_get_install_info_implicit_ignores_unsupported_versions(monkeypatch, tmp_path):
    supported_versions = {int(version) for version in AUTO_DETECT_INSTALL_VERSIONS}
    # Pick a version outside the configured implicit probe window so the test
    # continues to validate the support contract as releases advance.
    unsupported_version = max(supported_versions) + 10
    unsupported_dir = tmp_path / f"v{unsupported_version}" / "ADR"
    unsupported_dir.mkdir(parents=True)

    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)
    monkeypatch.delenv(f"AWP_ROOT{CURRENT_VERSION}", raising=False)
    for version in AUTO_DETECT_INSTALL_VERSIONS:
        monkeypatch.delenv(f"AWP_ROOT{version}", raising=False)
    monkeypatch.setenv(f"AWP_ROOT{unsupported_version}", str(unsupported_dir.parent))
    monkeypatch.delenv("CEIDEVROOTDOS", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "enve", None)
    # Redirect default filesystem probes to a non-existent path so a real
    # machine-wide Ansys installation does not interfere with this test.
    monkeypatch.setattr(
        common_utils_module,
        "_default_install_root",
        lambda version: tmp_path / "nonexistent" / f"v{version}",
    )

    # When only an unsupported install root is present, implicit discovery
    # must ignore it and fall back to the package default version metadata.
    install, ver = get_install_info()
    assert install is None
    assert ver == int(DEFAULT_ANSYS_INSTALL_VERSION)


@pytest.mark.ado_test
def test_get_install_info_explicit_version_does_not_probe_other_versions(monkeypatch, tmp_path):
    target_dir = tmp_path / "v261" / "ADR"
    target_dir.mkdir(parents=True)
    ignored_dir = tmp_path / "v271" / "ADR"
    ignored_dir.mkdir(parents=True)

    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)
    monkeypatch.setenv("AWP_ROOT261", str(target_dir.parent))
    monkeypatch.setenv("AWP_ROOT271", str(ignored_dir.parent))
    monkeypatch.delenv("CEIDEVROOTDOS", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "enve", None)

    install, ver = get_install_info(ansys_version=261)
    assert install == str(target_dir)
    assert ver == 261


@pytest.mark.ado_test
def test_get_install_info_explicit_271_is_still_supported(monkeypatch, tmp_path):
    target_dir = tmp_path / "v271" / "ADR"
    target_dir.mkdir(parents=True)

    monkeypatch.delenv("PYADR_ANSYS_INSTALLATION", raising=False)
    monkeypatch.setenv("AWP_ROOT271", str(target_dir.parent))
    monkeypatch.delenv("CEIDEVROOTDOS", raising=False)
    monkeypatch.setitem(__import__("sys").modules, "enve", None)

    install, ver = get_install_info(ansys_version=271)
    assert install == str(target_dir)
    assert ver == 271


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


@pytest.mark.ado_test
@pytest.mark.parametrize("falsy_version", [0, False])
def test_get_install_info_falsy_ansys_version_falls_back_to_default_layout(tmp_path, falsy_version):
    install_dir = tmp_path / "install_no_version"
    install_dir.mkdir()
    for version in (DEFAULT_ANSYS_INSTALL_VERSION, "271"):
        nexus_dir = install_dir / f"nexus{version}" / "django"
        nexus_dir.mkdir(parents=True)
        (nexus_dir / "manage.py").write_text("dummy content")

    install, ver = get_install_info(
        ansys_installation=str(install_dir), ansys_version=falsy_version
    )

    assert install == str(install_dir)
    assert ver == int(DEFAULT_ANSYS_INSTALL_VERSION)


@pytest.mark.ado_test
def test_get_install_info_detects_version_from_install_layout(tmp_path):
    install_dir = tmp_path / "install_no_version"
    install_dir.mkdir()
    nexus_dir = install_dir / "nexus271" / "django"
    nexus_dir.mkdir(parents=True)
    (nexus_dir / "manage.py").write_text("dummy content")

    install, ver = get_install_info(ansys_installation=str(install_dir))

    assert install == str(install_dir)
    assert ver == 271


@pytest.mark.ado_test
def test_get_install_version_from_layout_returns_none_when_ambiguous(tmp_path, caplog):
    install_dir = tmp_path / "install_no_version"
    install_dir.mkdir()
    for version in ("261", "271"):
        nexus_dir = install_dir / f"nexus{version}" / "django"
        nexus_dir.mkdir(parents=True)
        (nexus_dir / "manage.py").write_text("dummy content")

    with caplog.at_level("WARNING"):
        detected_version = common_utils_module._get_install_version_from_layout(install_dir)

    assert detected_version is None
    assert "Detected multiple ADR layout versions" in caplog.text
    assert str(sorted([261, 271])) in caplog.text


# The serverless renderer always passes an already-resolved concrete ADR/CEI install directory
# plus an int install version, so these tests feed that same production-shaped input (a directory
# named ``ADR`` containing ``apex271/machines/<arch>``) rather than a higher-level ``v###`` root.


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_finds_full_install_layout(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    browser_binary_dir = _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="win64",
    )
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    browser_path = resolve_playwright_browsers_path(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert browser_path == browser_binary_dir


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_uses_linux_machine_layout(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    browser_binary_dir = _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "linux_2.6_64",
        machine_arch="linux_2.6_64",
    )
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Linux")

    browser_path = resolve_playwright_browsers_path(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert browser_path == browser_binary_dir


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_returns_none_on_unsupported_platform(
    tmp_path, monkeypatch
):
    install_dir = tmp_path / "v271" / "ADR"
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Darwin")

    browser_path = resolve_playwright_browsers_path(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert browser_path is None


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_returns_none_without_required_inputs(monkeypatch):
    # On a supported platform the resolver still needs both a concrete install directory and a
    # version to build the machine-scoped binary path; neither input is inferred when omitted.
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    assert resolve_playwright_browsers_path(ansys_installation=None, ansys_version=271) is None
    assert (
        resolve_playwright_browsers_path(ansys_installation="C:/v271/ADR", ansys_version=None)
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_returns_none_when_binary_absent(tmp_path, monkeypatch):
    # A valid install that simply does not ship a Playwright binary must resolve to None rather
    # than pointing Playwright at a non-existent browser directory. Create the machine directory
    # but no playwright-browsers child.
    install_dir = tmp_path / "v271" / "ADR"
    (install_dir / "apex271" / "machines" / "win64").mkdir(parents=True)
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    browser_path = resolve_playwright_browsers_path(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert browser_path is None


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_requires_metadata_file(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="win64",
        write_metadata=False,
    )
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    browser_path = resolve_playwright_browsers_path(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert browser_path is None


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_requires_installation_complete_marker(
    tmp_path, monkeypatch
):
    install_dir = tmp_path / "v271" / "ADR"
    _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="win64",
        create_marker=False,
    )
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    browser_path = resolve_playwright_browsers_path(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert browser_path is None


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_requires_playwright_version_metadata(
    tmp_path, monkeypatch
):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64", write_metadata=False)
    metadata = _packaged_playwright_metadata(machine_arch="win64", playwright_version="")
    (browser_binary_dir / "playwright_browser_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browsers_path(ansys_installation=str(install_dir), ansys_version=271)
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_rejects_unreadable_metadata(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64", write_metadata=False)
    # Metadata is present but not valid JSON, so the binary path cannot be trusted.
    (browser_binary_dir / "playwright_browser_metadata.json").write_text(
        "{ not valid json", encoding="utf-8"
    )
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browsers_path(ansys_installation=str(install_dir), ansys_version=271)
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_rejects_non_object_metadata(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64", write_metadata=False)
    # Valid JSON, but a list instead of the expected metadata object.
    (browser_binary_dir / "playwright_browser_metadata.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browsers_path(ansys_installation=str(install_dir), ansys_version=271)
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_rejects_machine_arch_mismatch(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    # Binary sits under win64 but its metadata advertises a different machine arch.
    _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="linux_2.6_64",
    )
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browsers_path(ansys_installation=str(install_dir), ansys_version=271)
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_rejects_multiple_packaged_dirs(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    browser_binary_dir = _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="win64",
    )
    # A second packaged directory breaks the "exactly one browser directory" contract.
    (browser_binary_dir / "chromium_headless_shell-0001").mkdir()
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browsers_path(ansys_installation=str(install_dir), ansys_version=271)
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browsers_path_rejects_packaged_dir_name_mismatch(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64", write_metadata=False)
    # Metadata names a packaged directory that does not exist on disk.
    metadata = _packaged_playwright_metadata(
        machine_arch="win64",
        packaged_binary_dir="chromium_headless_shell-0000",
    )
    (browser_binary_dir / "playwright_browser_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(common_utils_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browsers_path(ansys_installation=str(install_dir), ansys_version=271)
        is None
    )


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
