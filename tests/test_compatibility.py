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

import warnings

import pytest

import ansys.dynamicreporting.core.adr_service as adr_service_module
import ansys.dynamicreporting.core.serverless.adr as serverless_adr_module
from ansys.dynamicreporting.core import (
    BUNDLED_PRODUCT_RELEASE,
    DEFAULT_ANSYS_VERSION,
    SUPPORTED_PRODUCT_LINES,
    SUPPORTED_PRODUCT_RELEASE_POLICY,
    __ansys_version__,
    __ansys_version_str__,
    ansys_version,
    get_compatibility_info,
)
from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.compatibility import (
    DEFAULT_ANSYS_INSTALL_RELEASE,
    ProductCompatibility,
    bundled_product_release_for_client_major,
    get_client_major_epoch,
    get_compatibility_warning_for_install_version,
    install_version_to_product_release,
    is_supported_product_release,
    parse_product_release,
    product_line_for_client_major,
    product_release_to_install_version,
    supported_product_lines_for_client_major,
)
from ansys.dynamicreporting.core.common_utils import InstallResolution
from ansys.dynamicreporting.core.serverless import ADR


def _current_supported_lines() -> tuple[str, str]:
    """Return the support window for the installed client major."""

    return supported_product_lines_for_client_major(get_client_major_epoch())


def _unsupported_newer_install_version() -> int:
    """Build an install version just beyond the current support window."""

    newest_supported_line = int(_current_supported_lines()[1])
    return product_release_to_install_version(f"{newest_supported_line + 1}.1")


def test_parse_product_release():
    assert parse_product_release("27.1") == ("27", 1)
    assert parse_product_release("27.2") == ("27", 2)


@pytest.mark.parametrize("invalid_release", ["27", "2027.1", "27.0", "foo"])
def test_parse_product_release_rejects_invalid_values(invalid_release):
    with pytest.raises(ValueError):
        parse_product_release(invalid_release)


def test_install_version_conversion_round_trip():
    assert product_release_to_install_version("27.1") == 271
    assert install_version_to_product_release(271) == "27.1"


def test_supported_product_release_uses_annual_lines():
    supported_lines = _current_supported_lines()
    oldest_supported_line, newest_supported_line = (int(line) for line in supported_lines)

    # This assertion follows the installed client line, so it stays correct
    # when the repo advances from 0.x to 1.x and beyond.
    assert is_supported_product_release(f"{oldest_supported_line}.1", supported_lines)
    assert is_supported_product_release(f"{newest_supported_line}.1", supported_lines)
    assert not is_supported_product_release(f"{oldest_supported_line - 1}.1", supported_lines)
    assert not is_supported_product_release(f"{newest_supported_line + 1}.1", supported_lines)


def test_product_epoch_helpers_follow_major_mapping():
    assert product_line_for_client_major(0) == "26"
    assert bundled_product_release_for_client_major(0) == "26.1"
    assert supported_product_lines_for_client_major(0) == ("25", "26")
    assert product_line_for_client_major(1) == "27"
    assert bundled_product_release_for_client_major(1) == "27.1"
    assert supported_product_lines_for_client_major(1) == ("26", "27")
    assert product_line_for_client_major(2) == "28"
    assert bundled_product_release_for_client_major(2) == "28.1"
    assert supported_product_lines_for_client_major(2) == ("27", "28")


def test_product_epoch_helpers_reject_negative_major():
    with pytest.raises(ValueError):
        product_line_for_client_major(-1)


def test_major_zero_support_window_matches_current_policy():
    supported_lines = supported_product_lines_for_client_major(0)
    assert is_supported_product_release("25.1", supported_lines)
    assert is_supported_product_release("25.2", supported_lines)
    assert is_supported_product_release("26.1", supported_lines)
    assert not is_supported_product_release("24.1", supported_lines)
    assert not is_supported_product_release("27.1", supported_lines)


def test_major_one_support_window_matches_current_policy():
    supported_lines = supported_product_lines_for_client_major(1)
    assert is_supported_product_release("26.1", supported_lines)
    assert is_supported_product_release("27.1", supported_lines)
    assert not is_supported_product_release("25.2", supported_lines)
    assert not is_supported_product_release("28.1", supported_lines)


def test_public_compatibility_surface_is_consistent():
    compatibility = get_compatibility_info()
    current_major = get_client_major_epoch()

    assert isinstance(compatibility, ProductCompatibility)
    assert compatibility.bundled_product_release == BUNDLED_PRODUCT_RELEASE
    assert compatibility.supported_product_lines == SUPPORTED_PRODUCT_LINES
    assert compatibility.support_policy == SUPPORTED_PRODUCT_RELEASE_POLICY
    assert BUNDLED_PRODUCT_RELEASE == bundled_product_release_for_client_major(current_major)
    assert SUPPORTED_PRODUCT_LINES == supported_product_lines_for_client_major(current_major)
    assert DEFAULT_ANSYS_VERSION == str(
        product_release_to_install_version(DEFAULT_ANSYS_INSTALL_RELEASE)
    )
    assert ansys_version == "2027R1"
    assert __ansys_version__ == DEFAULT_ANSYS_VERSION
    assert __ansys_version_str__ == "2027 R1"


def test_compatibility_info_derives_from_client_major():
    compatibility = get_compatibility_info("1.2.2")
    assert compatibility.client_major_epoch == 1
    assert compatibility.bundled_product_release == "27.1"
    assert compatibility.supported_product_lines == ("26", "27")

    next_major = get_compatibility_info("2.0.0")
    assert next_major.client_major_epoch == 2
    assert next_major.bundled_product_release == "28.1"
    assert next_major.supported_product_lines == ("27", "28")


def test_get_compatibility_warning_for_install_version():
    assert get_compatibility_warning_for_install_version(261) is None
    assert get_compatibility_warning_for_install_version(None) is None
    warning_message = get_compatibility_warning_for_install_version(
        _unsupported_newer_install_version()
    )
    assert warning_message is not None
    assert "outside the supported window" in warning_message


def test_get_compatibility_warning_skips_unparsable_install_version():
    # Unparsable versions should fail-open (return None) instead of raising,
    # so existing workflows are not disrupted by unexpected version formats.
    assert get_compatibility_warning_for_install_version("abc") is None
    assert get_compatibility_warning_for_install_version("1") is None


@pytest.mark.parametrize("invalid_version", ["ab", "1", "  ", "12.3"])
def test_install_version_to_product_release_rejects_invalid_input(invalid_version):
    with pytest.raises(ValueError):
        install_version_to_product_release(invalid_version)


def test_service_warns_for_unsupported_product_release(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    # Patch install discovery directly so this test exercises only the warning
    # behavior and not the machine-specific installation search logic.
    monkeypatch.setattr(
        adr_service_module,
        "resolve_install_info",
        lambda ansys_installation=None, ansys_version=None: InstallResolution(
            install_dir=str(install_dir),
            version=_unsupported_newer_install_version(),
        ),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Service(ansys_installation=str(install_dir))

    assert any("outside the supported window" in str(w.message) for w in caught)


def test_service_does_not_warn_for_supported_product_release(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    monkeypatch.setattr(
        adr_service_module,
        "resolve_install_info",
        lambda ansys_installation=None, ansys_version=None: InstallResolution(
            install_dir=str(install_dir),
            version=261,
        ),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Service(ansys_installation=str(install_dir))

    assert not any("outside the supported window" in str(w.message) for w in caught)


def test_service_warns_for_implicit_default_install_when_unsupported(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    monkeypatch.setattr(
        adr_service_module,
        "resolve_install_info",
        lambda ansys_installation=None, ansys_version=None: InstallResolution(
            install_dir=str(install_dir),
            version=_unsupported_newer_install_version(),
        ),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Service()

    assert any("outside the supported window" in str(w.message) for w in caught)


def test_serverless_warns_for_unsupported_product_release(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    monkeypatch.setattr(ADR, "_instance", None)
    monkeypatch.setattr(ADR, "_is_setup", False)
    # Reset the singleton and patch install discovery so the warning path is
    # tested deterministically without relying on a real ADR installation.
    monkeypatch.setattr(
        serverless_adr_module,
        "resolve_install_info",
        lambda ansys_installation=None, ansys_version=None: InstallResolution(
            install_dir=str(install_dir),
            version=_unsupported_newer_install_version(),
        ),
    )

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ADR(ansys_installation=str(install_dir), in_memory=True)
    finally:
        ADR._instance = None
        ADR._is_setup = False

    assert any("outside the supported window" in str(w.message) for w in caught)


def test_serverless_warns_for_implicit_default_install_when_unsupported(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    monkeypatch.setattr(ADR, "_instance", None)
    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(
        serverless_adr_module,
        "resolve_install_info",
        lambda ansys_installation=None, ansys_version=None: InstallResolution(
            install_dir=str(install_dir),
            version=_unsupported_newer_install_version(),
        ),
    )

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ADR(in_memory=True)
    finally:
        ADR._instance = None
        ADR._is_setup = False

    assert any("outside the supported window" in str(w.message) for w in caught)


def test_serverless_does_not_warn_when_install_version_is_unknown(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    monkeypatch.setattr(ADR, "_instance", None)
    monkeypatch.setattr(ADR, "_is_setup", False)
    monkeypatch.setattr(
        serverless_adr_module,
        "resolve_install_info",
        lambda ansys_installation=None, ansys_version=None: InstallResolution(
            install_dir=str(install_dir),
            version=None,
        ),
    )

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ADR(ansys_installation=str(install_dir), in_memory=True)
    finally:
        ADR._instance = None
        ADR._is_setup = False

    assert not any("outside the supported window" in str(w.message) for w in caught)
