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
def test_get_evsn_proxy_image(request) -> bool:
    try:
        _ = gp.get_evsn_proxy_image(filename=return_file_paths(request)[6])
        success = True
    except Exception:
        success = False
    assert (_ is None) and success


@pytest.mark.ado_test
def test_get_evsn_proxy_error(request) -> bool:
    succ = gp.get_evsn_proxy_image(filename=return_file_paths(request)[5]) is None
    assert succ


@pytest.mark.ado_test
def test_file_can_have_proxy(request) -> bool:
    scene = gp.file_can_have_proxy(return_file_paths(request)[1])
    img = gp.file_can_have_proxy(return_file_paths(request)[0])
    assert scene is True and img is False


@pytest.mark.ado_test
def test_file_is_3d_geometry(request) -> bool:
    scene = gp.file_is_3d_geometry(return_file_paths(request)[1], file_item_only=False)
    img = gp.file_is_3d_geometry(return_file_paths(request)[0])
    assert scene is True and img is False


@pytest.mark.ado_test
def test_rebuild_3d_geom_avz(request) -> bool:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[1], unique_id="abc", exec_basis="avz"
    )
    test_path = join(join(request.fspath.dirname, "test_data"), "scenes")
    new_dir = join(test_path, "scene")
    assert isdir(new_dir)


@pytest.mark.ado_test
def test_rebuild_3d_geom_ens(request) -> bool:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[2], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "dam_break")
    assert isdir(new_dir)


@pytest.mark.ado_test
def test_rebuild_3d_geom_evsn(request) -> bool:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[3], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "ami")
    assert isdir(new_dir)


@pytest.mark.ado_test
def test_rebuild_3d_geom_scdoc(request) -> bool:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[4], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "viewer_test")
    assert isdir(new_dir)


def test_rebuild_3d_geom_scdoc_second(request) -> bool:
    _ = gp.rebuild_3d_geometry(
        csf_file=return_file_paths(request)[4], unique_id="abc", exec_basis="avz"
    )
    test_path = join(request.fspath.dirname, "test_data")
    new_dir = join(test_path, "viewer_test")
    assert isdir(new_dir)


def test_rebuild_3d_geom_csf(request, get_exec) -> bool:
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
