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

from PIL import Image
from PIL.TiffTags import TAGS
from ansys.dpf import core as dpf
from ansys.dpf.core import examples
import pytest

from ansys.dynamicreporting.core.utils import enhanced_images as ei
from ansys.dynamicreporting.core.utils import report_utils as ru


def _generate_enhanced_image_as_tiff(*args, **kwargs):
    generate_tiff = getattr(ei, "generate_enhanced_image_as_tiff", None)
    if generate_tiff is None:
        raise RuntimeError("Enhanced TIFF generator is unavailable.")
    return generate_tiff(*args, **kwargs)


def _generate_enhanced_image_in_memory(*args, **kwargs):
    generate_in_memory = getattr(ei, "generate_enhanced_image_in_memory", None)
    if generate_in_memory is None:
        raise RuntimeError("Enhanced in-memory image generator is unavailable.")
    return generate_in_memory(*args, **kwargs)


def create_sample_sphere():
    import vtk

    sphere = vtk.vtkSphereSource()
    sphere.Update()
    add_var_as_cell_data(sphere.GetOutput(), "Pick Data", lambda i: 3456)
    add_var_as_cell_data(sphere.GetOutput(), "Temperature", lambda i: i / 10000)
    return sphere


def add_var_as_cell_data(poly_data, var_name, val_calculator):
    import vtk

    arr = vtk.vtkFloatArray()
    arr.SetName(var_name)
    arr.SetNumberOfComponents(1)
    num_cells = poly_data.GetNumberOfCells()
    arr.SetNumberOfTuples(num_cells)
    for i in range(num_cells):
        if i % 2 == 0:
            j = i
        else:
            j = -i
        arr.SetValue(i, val_calculator(j))
    poly_data.GetCellData().AddArray(arr)


def check_enhanced(image):
    assert image is not None
    image.seek(0)
    result = ru.is_enhanced(image)
    assert result is not None


def setup_dpf_tiff_generation(dpf_model_scalar_var):
    model, field = dpf_model_scalar_var

    tiff_name = "dpf_find_electric_therm.tiff"
    _generate_enhanced_image_as_tiff(model, field, "DPF Sample", "var", tiff_name)

    image = Image.open(tiff_name)
    yield image
    image.close()


def setup_dpf_inmem_generation(dpf_model_scalar_var):
    model, field = dpf_model_scalar_var
    buffer = _generate_enhanced_image_in_memory(model, field, "DPF Sample", "var")

    image = Image.open(buffer)
    yield image
    image.close()


@pytest.fixture
def dpf_model_scalar_var():
    file_path = examples.find_electric_therm()
    model = dpf.Model(file_path)

    results = model.results
    electric_potential = results.electric_potential()
    fields = electric_potential.outputs.fields_container()
    potential = fields[0]

    return model, potential


@pytest.fixture
def dpf_model_vector_var():
    file_path = examples.find_simple_bar()
    model = dpf.Model(file_path)
    results = model.results
    disp = results.displacement()
    fields = disp.outputs.fields_container()

    return model, fields[0]


@pytest.fixture
def dpf_model_elem_var():
    file_path = examples.find_simple_bar()
    model = dpf.Model(file_path)
    results = model.results
    elemental_volume = results.elemental_volume()
    fields = elemental_volume.outputs.fields_container()

    return model, fields[0]


@pytest.mark.ado_test
def test_generate_enhanced_image_vector_var_none_component(dpf_model_vector_var):
    model, field = dpf_model_vector_var

    with pytest.raises(ValueError) as exc_info:
        _generate_enhanced_image_as_tiff(
            model,
            field,
            "DPF Sample",
            "var",
            "output.tiff",
            component=None,  # Intentionally not specifying a component
        )

    # Assert the exception message
    assert (
        "Error when generating an enhanced image: The field data is a vector variable. "
        "Currently, we do not fully support vector variables. "
        "Please specify which component you want to plot upon: 'X', 'Y', or 'Z'."
    ) in str(exc_info.value)


@pytest.mark.ado_test
def test_generate_enhanced_image_vector_var_wrong_component(dpf_model_vector_var):
    model, field = dpf_model_vector_var

    with pytest.raises(ValueError) as exc_info:
        _generate_enhanced_image_as_tiff(
            model,
            field,
            "DPF Sample",
            "var",
            "output.tiff",
            component="W",  # Intentionally wrong component
        )

    # Assert the exception message
    assert (
        "Error when generating an enhanced image: "
        "The parameter 'component' only accepts 'X', 'Y', or 'Z'."
    ) in str(exc_info.value)


@pytest.mark.ado_test
def test_generate_enhanced_image_vector_var_all_components(dpf_model_vector_var):
    model, field = dpf_model_vector_var

    buffer_x = _generate_enhanced_image_in_memory(
        model, field, "DPF Sample", "displacement X", component="X"
    )
    with Image.open(buffer_x) as image_x:
        check_enhanced(image_x)

    buffer_y = _generate_enhanced_image_in_memory(
        model, field, "DPF Sample", "displacement Y", component="Y"
    )
    with Image.open(buffer_y) as image_y:
        check_enhanced(image_y)

    buffer_z = _generate_enhanced_image_in_memory(
        model, field, "DPF Sample", "displacement Z", component="Z"
    )
    with Image.open(buffer_z) as image_z:
        check_enhanced(image_z)


@pytest.mark.ado_test
def test_generate_enhanced_image_elem_var(dpf_model_elem_var):
    model, field = dpf_model_elem_var

    buffer = _generate_enhanced_image_in_memory(model, field, "DPF Sample", "element vol")
    with Image.open(buffer) as image:
        check_enhanced(image)


@pytest.fixture(params=["tiff", "inmem"])
def setup_generation_flow(request, dpf_model_scalar_var):
    if request.param == "tiff":
        yield from setup_dpf_tiff_generation(dpf_model_scalar_var)
    else:
        yield from setup_dpf_inmem_generation(dpf_model_scalar_var)


@pytest.mark.ado_test
def test_basic_format(setup_generation_flow):
    image = setup_generation_flow
    check_enhanced(image)


@pytest.mark.ado_test
def test_image_description(setup_generation_flow):
    image = setup_generation_flow
    assert image is not None
    image.seek(0)
    metadata_dict = {TAGS[key]: image.tag[key] for key in image.tag_v2}
    image_description = json.loads(metadata_dict["ImageDescription"][0])
    part_info = image_description["parts"][0]
    var_info = image_description["variables"][0]

    assert (
        part_info["name"] == "DPF Sample"
        and part_info["id"] == "3456"
        and part_info["colorby_var"] == "1.0"
    )

    assert (
        var_info["name"] == "var"
        and var_info["id"] == "3456"
        and var_info["pal_id"] == "1"
        and var_info["unit_dims"] == ""
        and var_info["unit_system_to_name"] == "MKS"
        and var_info["unit_label"] == "V"
    )
