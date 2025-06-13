import json

from PIL import Image
from PIL.TiffTags import TAGS
from ansys.dpf import core as dpf
from ansys.dpf.core import examples
import pytest

from ansys.dynamicreporting.core.utils import enhanced_images as ei
from ansys.dynamicreporting.core.utils import report_utils as ru


def get_dpf_model_field_example():
    model = dpf.Model(examples.find_electric_therm())

    results = model.results
    electric_potential = results.electric_potential()
    fields = electric_potential.outputs.fields_container()
    potential = fields[0]

    return model, potential


def setup_dpf_tiff_generation():
    model, field = get_dpf_model_field_example()

    tiff_name = "dpf_find_electric_therm.tiff"
    ei.generate_enhanced_image_as_tiff(model, field, "DPF Sample", "var", tiff_name)

    image = Image.open(tiff_name)
    yield image
    image.close()


def setup_dpf_inmem_generation():
    model, field = get_dpf_model_field_example()
    buffer = ei.generate_enhanced_image_in_memory(model, field, "DPF Sample", "var")

    image = Image.open(buffer)
    yield image
    image.close()


@pytest.fixture(params=[setup_dpf_tiff_generation, setup_dpf_inmem_generation])
def setup_generation_flow(request):
    try:
        return next(request.param())
    # The exception is raised when DPF server is not found due to unset env var
    # In this case, we return None in order to skip the test.
    except ValueError:
        return None


@pytest.mark.ado_test
def test_basic_format(setup_generation_flow):
    image = setup_generation_flow
    if image is None:
        assert True
    else:
        image.seek(0)
        result = ru.is_enhanced(image)
        assert result is not None


@pytest.mark.ado_test
def test_image_description(setup_generation_flow):
    image = setup_generation_flow
    if image is None:
        assert True
    else:
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
