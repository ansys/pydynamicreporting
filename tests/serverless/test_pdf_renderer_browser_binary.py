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
from ansys.dynamicreporting.core.serverless import pdf_renderer as pdf_renderer_module
from ansys.dynamicreporting.core.serverless.pdf_renderer import PlaywrightBrowserBinaryInfo
from ansys.dynamicreporting.core.serverless.pdf_renderer import (
    resolve_playwright_browser_binary_info,
)

_BROWSER_METADATA_FILENAME = "playwright_browser_metadata.json"
_PACKAGED_BROWSER_DIR_NAME = "packaged-browser-dir"
_SECOND_PACKAGED_BROWSER_DIR_NAME = "second-packaged-browser-dir"
_MISMATCHED_PACKAGED_BROWSER_DIR_NAME = "mismatched-packaged-browser-dir"
_DEFAULT_INSTALL_VERSION = int(DEFAULT_ANSYS_VERSION)


def _fake_install_dir(tmp_path: Path, version: int = _DEFAULT_INSTALL_VERSION) -> Path:
    """Return a synthetic ADR install directory for one install version."""
    return tmp_path / f"v{version}" / "ADR"


def _machine_root(
    tmp_path: Path,
    machine_arch: str,
    *,
    version: int = _DEFAULT_INSTALL_VERSION,
) -> Path:
    """Return the machine-scoped packaged-browser root for one fake install."""
    return _fake_install_dir(tmp_path, version) / f"apex{version}" / "machines" / machine_arch


def _packaged_browser_metadata(
    *,
    machine_arch: str,
    packaged_binary_dir: str | None = None,
    browser_name: str | None = None,
) -> dict[str, str]:
    """Build the product metadata JSON that points at one packaged browser directory."""
    return PlaywrightBrowserBinaryInfo(
        path=Path("playwright-browsers"),
        browser_name=browser_name or PlaywrightBrowserBinaryInfo.EXPECTED_BROWSER_NAME,
        machine_arch=machine_arch,
        packaged_binary_dir=(
            _PACKAGED_BROWSER_DIR_NAME if packaged_binary_dir is None else packaged_binary_dir
        ),
    ).to_metadata_dict()


def _create_packaged_browser_binary(
    machine_root: Path,
    *,
    machine_arch: str,
    packaged_binary_dir: str | None = None,
    write_metadata: bool = True,
    create_marker: bool = True,
) -> Path:
    """Create ``playwright-browsers/<packaged dir>`` with optional metadata and marker."""
    browser_binary_dir = machine_root / "playwright-browsers"
    packaged_dir_name = (
        _PACKAGED_BROWSER_DIR_NAME if packaged_binary_dir is None else packaged_binary_dir
    )
    packaged_dir = browser_binary_dir / packaged_dir_name
    packaged_dir.mkdir(parents=True)
    if create_marker:
        # Playwright writes this marker after a complete browser install; the resolver treats
        # its absence as an incomplete product package even when the directory exists.
        (packaged_dir / "INSTALLATION_COMPLETE").write_text("", encoding="utf-8")

    if write_metadata:
        # The JSON lives next to the packaged directories and must describe the exact directory
        # that should be passed to Playwright through PLAYWRIGHT_BROWSERS_PATH.
        metadata = _packaged_browser_metadata(
            machine_arch=machine_arch,
            packaged_binary_dir=packaged_dir_name,
        )
        _metadata_path(browser_binary_dir).write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return browser_binary_dir


def _metadata_path(browser_binary_dir: Path) -> Path:
    """Return the metadata file path inside one packaged browser binary directory."""
    return browser_binary_dir / _BROWSER_METADATA_FILENAME


# The serverless renderer always passes an already-resolved concrete ADR/CEI install directory
# plus an int install version, so these tests feed that same production-shaped input (a directory
# named ``ADR`` containing ``apex<version>/machines/<arch>``) rather than a higher-level ``v###`` root.


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_finds_full_install_layout(tmp_path, monkeypatch):
    install_dir = _fake_install_dir(tmp_path)
    browser_binary_dir = _create_packaged_browser_binary(
        _machine_root(tmp_path, "win64"),
        machine_arch="win64",
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
    )

    assert binary_info is not None
    assert binary_info.path == browser_binary_dir


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_uses_linux_machine_layout(tmp_path, monkeypatch):
    install_dir = _fake_install_dir(tmp_path)
    browser_binary_dir = _create_packaged_browser_binary(
        _machine_root(tmp_path, "linux_2.6_64"),
        machine_arch="linux_2.6_64",
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Linux")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
    )

    assert binary_info is not None
    assert binary_info.path == browser_binary_dir


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_returns_none_on_unsupported_platform(
    tmp_path, monkeypatch
):
    install_dir = _fake_install_dir(tmp_path)
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Darwin")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
    )

    assert binary_info is None


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_returns_none_without_required_inputs(monkeypatch):
    # On a supported platform the resolver still needs both a concrete install directory and a
    # version to build the machine-scoped binary path; neither input is inferred when omitted.
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=None, ansys_version=_DEFAULT_INSTALL_VERSION
        )
        is None
    )
    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation="unused-install-dir", ansys_version=None
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_returns_none_when_binary_absent(
    tmp_path, monkeypatch
):
    # A valid install that simply does not ship a Playwright binary must resolve to None rather
    # than pointing Playwright at a non-existent browser directory. Create the machine directory
    # but no playwright-browsers child.
    install_dir = _fake_install_dir(tmp_path)
    _machine_root(tmp_path, "win64").mkdir(parents=True)
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
    )

    assert binary_info is None


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_requires_metadata_file(tmp_path, monkeypatch):
    install_dir = _fake_install_dir(tmp_path)
    _create_packaged_browser_binary(
        _machine_root(tmp_path, "win64"),
        machine_arch="win64",
        write_metadata=False,
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
    )

    assert binary_info is None


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_requires_installation_complete_marker(
    tmp_path, monkeypatch
):
    install_dir = _fake_install_dir(tmp_path)
    _create_packaged_browser_binary(
        _machine_root(tmp_path, "win64"),
        machine_arch="win64",
        create_marker=False,
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
    )

    assert binary_info is None


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_accepts_metadata_matching_packaged_dir(
    tmp_path, monkeypatch
):
    install_dir = _fake_install_dir(tmp_path)
    machine_root = _machine_root(tmp_path, "win64")
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_browser_binary(machine_root, machine_arch="win64")
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
    )
    assert binary_info is not None
    assert binary_info.path == browser_binary_dir
    assert binary_info.browser_name == PlaywrightBrowserBinaryInfo.EXPECTED_BROWSER_NAME
    assert binary_info.machine_arch == "win64"
    assert binary_info.packaged_binary_dir == _PACKAGED_BROWSER_DIR_NAME


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_unreadable_metadata(tmp_path, monkeypatch):
    install_dir = _fake_install_dir(tmp_path)
    machine_root = _machine_root(tmp_path, "win64")
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_browser_binary(machine_root, machine_arch="win64", write_metadata=False)
    # Metadata is present but not valid JSON, so the binary path cannot be trusted.
    _metadata_path(browser_binary_dir).write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_non_object_metadata(tmp_path, monkeypatch):
    install_dir = _fake_install_dir(tmp_path)
    machine_root = _machine_root(tmp_path, "win64")
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_browser_binary(machine_root, machine_arch="win64", write_metadata=False)
    # Valid JSON, but a list instead of the expected metadata object.
    _metadata_path(browser_binary_dir).write_text("[]", encoding="utf-8")
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_browser_name_mismatch(
    tmp_path, monkeypatch
):
    install_dir = _fake_install_dir(tmp_path)
    machine_root = _machine_root(tmp_path, "win64")
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_browser_binary(machine_root, machine_arch="win64", write_metadata=False)
    metadata = _packaged_browser_metadata(machine_arch="win64", browser_name="chromium")
    _metadata_path(browser_binary_dir).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_empty_packaged_dir(tmp_path, monkeypatch):
    install_dir = _fake_install_dir(tmp_path)
    machine_root = _machine_root(tmp_path, "win64")
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_browser_binary(machine_root, machine_arch="win64", write_metadata=False)
    metadata = _packaged_browser_metadata(machine_arch="win64", packaged_binary_dir="")
    _metadata_path(browser_binary_dir).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_machine_arch_mismatch(
    tmp_path, monkeypatch
):
    install_dir = _fake_install_dir(tmp_path)
    # Binary sits under win64 but its metadata advertises a different machine arch.
    _create_packaged_browser_binary(
        _machine_root(tmp_path, "win64"),
        machine_arch="linux_2.6_64",
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_multiple_packaged_dirs(
    tmp_path, monkeypatch
):
    install_dir = _fake_install_dir(tmp_path)
    browser_binary_dir = _create_packaged_browser_binary(
        _machine_root(tmp_path, "win64"),
        machine_arch="win64",
    )
    # A second packaged directory breaks the "exactly one browser directory" contract.
    (browser_binary_dir / _SECOND_PACKAGED_BROWSER_DIR_NAME).mkdir()
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_packaged_dir_name_mismatch(
    tmp_path, monkeypatch
):
    install_dir = _fake_install_dir(tmp_path)
    machine_root = _machine_root(tmp_path, "win64")
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_browser_binary(machine_root, machine_arch="win64", write_metadata=False)
    # Metadata names a packaged directory that does not exist on disk.
    metadata = _packaged_browser_metadata(
        machine_arch="win64",
        packaged_binary_dir=_MISMATCHED_PACKAGED_BROWSER_DIR_NAME,
    )
    _metadata_path(browser_binary_dir).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=_DEFAULT_INSTALL_VERSION
        )
        is None
    )
