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

from os.path import isdir, join
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ansys.dynamicreporting.core.utils import geofile_processing as gp


def return_file_paths(request):
    test_path = join(request.fspath.dirname, "test_data")
    image_file = join(test_path, "aa_00_0_alpha1.png")
    scene_file = join(join(test_path, "scenes"), "scene.avz")
    scdoc_file = join(test_path, "viewer_test.scdoc")
    csf_file = join(test_path, "flow2d.csf")
    img_proxy = join(join(test_path, "scenes"), "proxy.png")
    return [image_file, scene_file, scdoc_file, csf_file, img_proxy]


@pytest.mark.ado_test
def test_file_can_have_proxy(request) -> None:
    scene = gp.file_can_have_proxy(return_file_paths(request)[1])
    img = gp.file_can_have_proxy(return_file_paths(request)[0])
    assert scene is True and img is False


@pytest.mark.ado_test
def test_file_is_3d_geometry(request) -> None:
    scene = gp.file_is_3d_geometry(return_file_paths(request)[1], file_item_only=False)
    img = gp.file_is_3d_geometry(return_file_paths(request)[0])
    assert scene is True and img is False


@pytest.mark.ado_test
def test_get_avz_directory(request) -> None:
    avz_dir = gp.get_avz_directory(return_file_paths(request)[1])
    assert isinstance(avz_dir, str) and avz_dir != ""


@pytest.mark.ado_test
def test_rebuild_3d_geom_avz(request) -> None:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[1], unique_id="abc", exec_basis="avz"
    )
    test_path = join(join(request.fspath.dirname, "test_data"), "scenes")
    new_dir = join(test_path, "scene")
    assert isdir(new_dir)


@pytest.mark.ado_test
def test_rebuild_3d_geom_scdoc(request) -> None:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[2], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "viewer_test")
    assert isdir(new_dir)


def test_rebuild_3d_geom_scdoc_second(request) -> None:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[2], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "viewer_test")
    assert isdir(new_dir)


def test_rebuild_3d_geom_csf(request, get_exec) -> None:
    exec_basis = get_exec
    if exec_basis:
        _ = gp.rebuild_3d_geometry(
            csf_file=return_file_paths(request)[3], unique_id="abc", exec_basis=exec_basis
        )
        test_path = join(request.fspath.dirname, "test_data")
        new_dir = join(test_path, "flow2d")
        assert isdir(new_dir)
    else:
        # If there is no local installation, then skip this as we do not have
        # the cei_apex???_udrw3avz executable available
        assert True


@pytest.mark.ado_test
@pytest.mark.parametrize(
    ("settings_values", "expected_version"),
    [
        ({"ADR_VERSION": "271", "CEI_APEX_SUFFIX": "261"}, "271"),
        ({"CEI_APEX_SUFFIX": "261"}, "261"),
    ],
)
def test_rebuild_3d_geometry_uses_supported_version_setting(
    monkeypatch, tmp_path, settings_values, expected_version
) -> None:
    monkeypatch.setattr(gp, "settings", SimpleNamespace(**settings_values))
    monkeypatch.setattr(gp, "is_enve", False)
    monkeypatch.setattr(gp.platform, "system", lambda: "Linux")

    def create_empty_avz(command, **kwargs):
        with gp.zipfile.ZipFile(command[-1], "w"):
            pass
        return 0

    converter_call = Mock(side_effect=create_empty_avz)
    monkeypatch.setattr(gp.subprocess, "call", converter_call)
    csf_file = tmp_path / "scene.csf"
    csf_file.touch()
    product_root = tmp_path / "product"

    gp.rebuild_3d_geometry(csf_file=str(csf_file), exec_basis=str(product_root))

    converter_call.assert_called_once()
    assert converter_call.call_args.args[0][0] == str(
        product_root / "bin" / f"cei_apex{expected_version}_udrw2avz"
    )
