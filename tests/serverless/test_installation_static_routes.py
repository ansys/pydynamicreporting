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

from ansys.dynamicreporting.core.exceptions import ImproperlyConfiguredError
from ansys.dynamicreporting.core.serverless import ADR


def _make_adr(
    tmp_path: Path, version: int = 261, static_url: str = "/static/"
) -> tuple[ADR, Path, Path]:
    installation_root = tmp_path / f"product-{version}"
    static_root = installation_root / f"nexus{version}" / "django" / "static"
    version_static_root = static_root / f"ansys{version}"
    version_static_root.mkdir(parents=True)

    adr = object.__new__(ADR)
    adr._ansys_installation = installation_root
    adr._ansys_version = version
    adr._static_url = static_url
    return adr, static_root.resolve(), version_static_root.resolve()


@pytest.mark.unit
def test_get_installation_static_routes_is_available_before_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_root = tmp_path / "ANSYS Student" / "v261"
    product_root = release_root / "CEI"
    django_root = product_root / "nexus261" / "django"
    static_root = django_root / "static"
    version_static_root = static_root / "ansys261"
    version_static_root.mkdir(parents=True)
    (django_root / "manage.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(ADR, "_instance", None)
    monkeypatch.setattr(ADR, "_is_setup", False)

    adr = ADR(ansys_installation=str(release_root), in_memory=True)
    try:
        assert not adr.is_setup
        assert adr.ansys_installation == str(product_root)
        assert adr.get_installation_static_routes() == {
            "/static/": str(static_root.resolve()),
            "/ansys261/": str(version_static_root.resolve()),
        }
    finally:
        for tmp_dir in adr._tmp_dirs:
            tmp_dir.cleanup()


@pytest.mark.unit
@pytest.mark.parametrize("version", [261, 271])
def test_get_installation_static_routes_uses_versioned_installation(
    tmp_path: Path, version: int
) -> None:
    adr, static_root, version_static_root = _make_adr(tmp_path, version=version)

    assert adr.get_installation_static_routes() == {
        "/static/": str(static_root),
        f"/ansys{version}/": str(version_static_root),
    }


@pytest.mark.unit
def test_get_installation_static_routes_adds_canonical_aliases(tmp_path: Path) -> None:
    adr, static_root, version_static_root = _make_adr(
        tmp_path, version=271, static_url="/adr-assets/"
    )

    assert adr.get_installation_static_routes() == {
        "/adr-assets/": str(static_root),
        "/static/": str(static_root),
        "/ansys271/": str(version_static_root),
    }


@pytest.mark.unit
def test_get_installation_static_routes_returns_independent_dictionaries(tmp_path: Path) -> None:
    adr, static_root, version_static_root = _make_adr(tmp_path)

    first_routes = adr.get_installation_static_routes()
    first_routes.clear()

    assert adr.get_installation_static_routes() == {
        "/static/": str(static_root),
        "/ansys261/": str(version_static_root),
    }


@pytest.mark.unit
def test_get_installation_static_routes_rejects_missing_installation(tmp_path: Path) -> None:
    adr, _, _ = _make_adr(tmp_path)
    missing_installation = tmp_path / "missing-installation"
    adr._ansys_installation = missing_installation

    with pytest.raises(ImproperlyConfiguredError, match="installation directory does not exist"):
        adr.get_installation_static_routes()


@pytest.mark.unit
def test_get_installation_static_routes_rejects_missing_static_root(tmp_path: Path) -> None:
    adr, static_root, version_static_root = _make_adr(tmp_path)
    version_static_root.rmdir()
    static_root.rmdir()

    with pytest.raises(ImproperlyConfiguredError, match="static directory does not exist"):
        adr.get_installation_static_routes()


@pytest.mark.unit
def test_get_installation_static_routes_rejects_missing_version_root(tmp_path: Path) -> None:
    adr, _, version_static_root = _make_adr(tmp_path)
    version_static_root.rmdir()

    with pytest.raises(
        ImproperlyConfiguredError, match="versioned static directory does not exist"
    ):
        adr.get_installation_static_routes()


@pytest.mark.unit
@pytest.mark.parametrize(
    "static_url",
    [
        "/",
        "static/",
        "/static",
        "//cdn.example/static/",
        "https://example.com/static/",
        "/static/?v=1",
        "/static/#fragment",
        "\\static\\",
        "/static/../assets/",
    ],
)
def test_get_installation_static_routes_rejects_invalid_prefix(
    tmp_path: Path, static_url: str
) -> None:
    adr, _, _ = _make_adr(tmp_path, static_url=static_url)

    with pytest.raises(ImproperlyConfiguredError, match="static_url"):
        adr.get_installation_static_routes()


@pytest.mark.unit
@pytest.mark.parametrize(
    "static_url",
    [
        "/static/nested/",
        "/ansys261/",
        "/ansys261/nexus/",
    ],
)
def test_get_installation_static_routes_rejects_overlapping_prefix(
    tmp_path: Path, static_url: str
) -> None:
    adr, _, _ = _make_adr(tmp_path, static_url=static_url)

    with pytest.raises(ImproperlyConfiguredError, match="overlaps"):
        adr.get_installation_static_routes()
