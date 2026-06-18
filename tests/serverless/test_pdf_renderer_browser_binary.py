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

from ansys.dynamicreporting.core.serverless import pdf_renderer as pdf_renderer_module
from ansys.dynamicreporting.core.serverless.pdf_renderer import PlaywrightBrowserBinaryInfo
from ansys.dynamicreporting.core.serverless.pdf_renderer import (
    resolve_playwright_browser_binary_info,
)

_PACKAGED_BROWSER_DIR_NAME = "chromium_headless_shell-1223"


def _packaged_playwright_metadata(
    *,
    machine_arch: str,
    packaged_binary_dir: str | None = None,
    browser_name: str | None = None,
) -> dict[str, str]:
    """Build the required packaged Playwright metadata keys from the production schema."""
    return PlaywrightBrowserBinaryInfo(
        path=Path("playwright-browsers"),
        browser_name=browser_name or PlaywrightBrowserBinaryInfo.EXPECTED_BROWSER_NAME,
        machine_arch=machine_arch,
        packaged_binary_dir=(
            _PACKAGED_BROWSER_DIR_NAME if packaged_binary_dir is None else packaged_binary_dir
        ),
    ).to_metadata_dict()


def _create_packaged_playwright_binary(
    machine_root: Path,
    *,
    machine_arch: str,
    packaged_binary_dir: str | None = None,
    write_metadata: bool = True,
    create_marker: bool = True,
) -> Path:
    """Create a minimal packaged Playwright binary that matches the ADR layout contract."""
    browser_binary_dir = machine_root / "playwright-browsers"
    packaged_dir_name = (
        _PACKAGED_BROWSER_DIR_NAME if packaged_binary_dir is None else packaged_binary_dir
    )
    packaged_dir = browser_binary_dir / packaged_dir_name
    packaged_dir.mkdir(parents=True)
    if create_marker:
        (packaged_dir / "INSTALLATION_COMPLETE").write_text("", encoding="utf-8")

    if write_metadata:
        metadata = _packaged_playwright_metadata(
            machine_arch=machine_arch,
            packaged_binary_dir=packaged_dir_name,
        )
        (browser_binary_dir / "playwright_browser_metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return browser_binary_dir


# The serverless renderer always passes an already-resolved concrete ADR/CEI install directory
# plus an int install version, so these tests feed that same production-shaped input (a directory
# named ``ADR`` containing ``apex271/machines/<arch>``) rather than a higher-level ``v###`` root.


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_finds_full_install_layout(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    browser_binary_dir = _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="win64",
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert binary_info is not None
    assert binary_info.path == browser_binary_dir


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_uses_linux_machine_layout(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    browser_binary_dir = _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "linux_2.6_64",
        machine_arch="linux_2.6_64",
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Linux")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert binary_info is not None
    assert binary_info.path == browser_binary_dir


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_returns_none_on_unsupported_platform(
    tmp_path, monkeypatch
):
    install_dir = tmp_path / "v271" / "ADR"
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Darwin")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert binary_info is None


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_returns_none_without_required_inputs(monkeypatch):
    # On a supported platform the resolver still needs both a concrete install directory and a
    # version to build the machine-scoped binary path; neither input is inferred when omitted.
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(ansys_installation=None, ansys_version=271) is None
    )
    assert (
        resolve_playwright_browser_binary_info(ansys_installation="C:/v271/ADR", ansys_version=None)
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_returns_none_when_binary_absent(
    tmp_path, monkeypatch
):
    # A valid install that simply does not ship a Playwright binary must resolve to None rather
    # than pointing Playwright at a non-existent browser directory. Create the machine directory
    # but no playwright-browsers child.
    install_dir = tmp_path / "v271" / "ADR"
    (install_dir / "apex271" / "machines" / "win64").mkdir(parents=True)
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert binary_info is None


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_requires_metadata_file(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="win64",
        write_metadata=False,
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert binary_info is None


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_requires_installation_complete_marker(
    tmp_path, monkeypatch
):
    install_dir = tmp_path / "v271" / "ADR"
    _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="win64",
        create_marker=False,
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=271
    )

    assert binary_info is None


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_accepts_required_metadata(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64")
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    binary_info = resolve_playwright_browser_binary_info(
        ansys_installation=str(install_dir), ansys_version=271
    )
    assert binary_info is not None
    assert binary_info.path == browser_binary_dir


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_unreadable_metadata(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64", write_metadata=False)
    # Metadata is present but not valid JSON, so the binary path cannot be trusted.
    (browser_binary_dir / "playwright_browser_metadata.json").write_text(
        "{ not valid json", encoding="utf-8"
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=271
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_non_object_metadata(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64", write_metadata=False)
    # Valid JSON, but a list instead of the expected metadata object.
    (browser_binary_dir / "playwright_browser_metadata.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=271
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_browser_name_mismatch(
    tmp_path, monkeypatch
):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64", write_metadata=False)
    metadata = _packaged_playwright_metadata(machine_arch="win64", browser_name="chromium")
    (browser_binary_dir / "playwright_browser_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=271
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_empty_packaged_dir(tmp_path, monkeypatch):
    install_dir = tmp_path / "v271" / "ADR"
    machine_root = install_dir / "apex271" / "machines" / "win64"
    browser_binary_dir = machine_root / "playwright-browsers"
    _create_packaged_playwright_binary(machine_root, machine_arch="win64", write_metadata=False)
    metadata = _packaged_playwright_metadata(machine_arch="win64", packaged_binary_dir="")
    (browser_binary_dir / "playwright_browser_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=271
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_machine_arch_mismatch(
    tmp_path, monkeypatch
):
    install_dir = tmp_path / "v271" / "ADR"
    # Binary sits under win64 but its metadata advertises a different machine arch.
    _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="linux_2.6_64",
    )
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=271
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_multiple_packaged_dirs(
    tmp_path, monkeypatch
):
    install_dir = tmp_path / "v271" / "ADR"
    browser_binary_dir = _create_packaged_playwright_binary(
        install_dir / "apex271" / "machines" / "win64",
        machine_arch="win64",
    )
    # A second packaged directory breaks the "exactly one browser directory" contract.
    (browser_binary_dir / "chromium_headless_shell-0001").mkdir()
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=271
        )
        is None
    )


@pytest.mark.ado_test
def test_resolve_playwright_browser_binary_info_rejects_packaged_dir_name_mismatch(
    tmp_path, monkeypatch
):
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
    monkeypatch.setattr(pdf_renderer_module.platform, "system", lambda: "Windows")

    assert (
        resolve_playwright_browser_binary_info(
            ansys_installation=str(install_dir), ansys_version=271
        )
        is None
    )
