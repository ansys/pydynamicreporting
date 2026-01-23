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

import pytest

from ansys.dynamicreporting.core.utils import geofile_processing as gp


def return_file_paths(request):
    test_path = join(request.fspath.dirname, "test_data")
    image_file = join(test_path, "aa_00_0_alpha1.png")
    scene_file = join(join(test_path, "scenes"), "scene.avz")
    ens_file = join(test_path, "dam_break.ens")
    evsn_file = join(test_path, "ami.evsn")
    scdoc_file = join(test_path, "viewer_test.scdoc")
    csf_file = join(test_path, "flow2d.csf")
    img_proxy = join(join(test_path, "scenes"), "proxy.png")
    return [image_file, scene_file, ens_file, evsn_file, scdoc_file, csf_file, img_proxy]


@pytest.mark.ado_test
def test_get_evsn_proxy_image(request) -> None:
    try:
        result = gp.get_evsn_proxy_image(filename=return_file_paths(request)[6])
        assert result is None
    except Exception as e:
        pytest.fail(f"get_evsn_proxy_image raised an unexpected exception: {e}")


@pytest.mark.ado_test
def test_get_evsn_proxy_error(request) -> None:
    succ = gp.get_evsn_proxy_image(filename=return_file_paths(request)[5]) is None
    assert succ


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
def test_rebuild_3d_geom_ens(request) -> None:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[2], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "dam_break")
    assert isdir(new_dir)


@pytest.mark.ado_test
def test_rebuild_3d_geom_evsn(request) -> None:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[3], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "ami")
    assert isdir(new_dir)


@pytest.mark.ado_test
def test_rebuild_3d_geom_scdoc(request) -> None:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[4], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "viewer_test")
    assert isdir(new_dir)


def test_rebuild_3d_geom_scdoc_second(request) -> None:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[4], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "viewer_test")
    assert isdir(new_dir)


def test_rebuild_3d_geom_csf(request, get_exec) -> None:
    exec_basis = get_exec
    if exec_basis:
        _ = gp.rebuild_3d_geometry(
            csf_file=return_file_paths(request)[5], unique_id="abc", exec_basis=exec_basis
        )
        test_path = join(request.fspath.dirname, "test_data")
        new_dir = join(test_path, "flow2d")
        assert isdir(new_dir)
    else:
        # If there is no local installation, then skip this as we do not have
        # the cei_apex???_udrw3avz executable available
        assert True
