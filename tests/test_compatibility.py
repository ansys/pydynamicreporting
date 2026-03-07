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
    get_compatibility_info,
)
from ansys.dynamicreporting.core import Service
from ansys.dynamicreporting.core.compatibility import (
    ProductCompatibility,
    get_compatibility_warning_for_install_version,
    install_version_to_product_release,
    is_supported_product_release,
    parse_product_release,
    product_release_to_install_version,
)
from ansys.dynamicreporting.core.serverless import ADR


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
    assert is_supported_product_release("26.1")
    assert is_supported_product_release("26.2")
    assert is_supported_product_release("27.1")
    assert is_supported_product_release("27.2")
    assert not is_supported_product_release("25.1")
    assert not is_supported_product_release("28.1")


def test_public_compatibility_surface_is_consistent():
    compatibility = get_compatibility_info()
    assert isinstance(compatibility, ProductCompatibility)
    assert compatibility.bundled_product_release == BUNDLED_PRODUCT_RELEASE
    assert compatibility.supported_product_lines == SUPPORTED_PRODUCT_LINES
    assert compatibility.support_policy == SUPPORTED_PRODUCT_RELEASE_POLICY
    assert DEFAULT_ANSYS_VERSION == str(product_release_to_install_version(BUNDLED_PRODUCT_RELEASE))
    assert __ansys_version__ == DEFAULT_ANSYS_VERSION
    assert __ansys_version_str__


def test_get_compatibility_warning_for_install_version():
    assert get_compatibility_warning_for_install_version(271) is None
    assert get_compatibility_warning_for_install_version(None) is None
    warning_message = get_compatibility_warning_for_install_version(252)
    assert warning_message is not None
    assert "outside the supported window" in warning_message


def test_service_warns_for_unsupported_product_release(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    # Patch install discovery directly so this test exercises only the warning
    # behavior and not the machine-specific installation search logic.
    monkeypatch.setattr(
        adr_service_module,
        "get_install_info",
        lambda ansys_installation=None, ansys_version=None: (str(install_dir), 252),
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
        "get_install_info",
        lambda ansys_installation=None, ansys_version=None: (str(install_dir), 271),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Service(ansys_installation=str(install_dir))

    assert not any("outside the supported window" in str(w.message) for w in caught)


def test_serverless_warns_for_unsupported_product_release(monkeypatch, tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    monkeypatch.setattr(ADR, "_instance", None)
    monkeypatch.setattr(ADR, "_is_setup", False)
    # Reset the singleton and patch install discovery so the warning path is
    # tested deterministically without relying on a real ADR installation.
    monkeypatch.setattr(
        serverless_adr_module,
        "get_install_info",
        lambda ansys_installation=None, ansys_version=None: (str(install_dir), 252),
    )

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ADR(ansys_installation=str(install_dir), in_memory=True)
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
        "get_install_info",
        lambda ansys_installation=None, ansys_version=None: (str(install_dir), None),
    )

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ADR(ansys_installation=str(install_dir), in_memory=True)
    finally:
        ADR._instance = None
        ADR._is_setup = False

    assert not any("outside the supported window" in str(w.message) for w in caught)
