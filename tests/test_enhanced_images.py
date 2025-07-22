import json
import os

from PIL import Image
from PIL.TiffTags import TAGS
from ansys.dpf import core as dpf
from ansys.dpf.core import examples
import pytest

from ansys.dynamicreporting.core.utils import enhanced_images as ei
from ansys.dynamicreporting.core.utils import report_utils as ru


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
    file_path = examples.find_electric_therm()
    model = dpf.Model(file_path)

    results = model.results
    disp = results.displacement()
    fields = disp.outputs.fields_container()

    return model, fields[0]


@pytest.mark.ado_test
def test_generate_enhanced_image_vector_var_none_component(dpf_model_vector_var):
    model, field = dpf_model_vector_var

    with pytest.raises(ValueError) as exc_info:
        ei.generate_enhanced_image_as_tiff(
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
        ei.generate_enhanced_image_as_tiff(
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
    

def check_enhanced(image):
    assert image is not None
    image.seek(0)
    result = ru.is_enhanced(image)
    assert result is not None


@pytest.mark.ado_test
def test_generate_enhanced_image_vector_var_all_components(dpf_model_vector_var):
    model, field = dpf_model_vector_var
    
    buffer_x = ei.generate_enhanced_image_in_memory(model, field, "DPF Sample", "displacement X", component='X')
    with Image.open(buffer_x) as image_x:
        check_enhanced(image_x)
        
    buffer_y = ei.generate_enhanced_image_in_memory(model, field, "DPF Sample", "displacement Y", component='Y')
    with Image.open(buffer_y) as image_y:
        check_enhanced(image_y)
        
    buffer_z = ei.generate_enhanced_image_in_memory(model, field, "DPF Sample", "displacement Z", component='Z')
    with Image.open(buffer_z) as image_z:
        check_enhanced(image_z)     
    

def setup_dpf_tiff_generation(dpf_model_scalar_var):
    model, field = dpf_model_scalar_var

    tiff_name = "dpf_find_electric_therm.tiff"
    ei.generate_enhanced_image_as_tiff(model, field, "DPF Sample", "var", tiff_name)

    image = Image.open(tiff_name)
    yield image
    image.close()


def setup_dpf_inmem_generation(dpf_model_scalar_var):
    model, field = dpf_model_scalar_var
    buffer = ei.generate_enhanced_image_in_memory(model, field, "DPF Sample", "var")

    image = Image.open(buffer)
    yield image
    image.close()


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
