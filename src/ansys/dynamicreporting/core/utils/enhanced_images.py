"""
Methods that generate enhanced images.

A group of functions that mainly create:
1. RGB buffer
2. Pick data buffer
3. Variable data buffer

Then combine these 3 buffers along with a JSON metadata to generate a 3-page
enhanced image.
"""
import io
import json
from typing import Dict, Tuple, Union

from PIL import Image, TiffImagePlugin
from ansys.dpf import core as dpf
from ansys.dpf.core import vtk_helper
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy


def setup_render_routine(poly_data: vtk.vtkPolyData) -> Tuple[vtk.vtkRenderer, vtk.vtkRenderWindow]:
    """
    Set up VTK render routine, including mapper, actor, renderer and render window.

    Parameters
    ----------
    poly_data: vtk.vtkPolyData
        A VTK poly data object.

    Returns
    -------
    Tuple[vtk.vtkRenderer, vtk.vtkRenderWindow]
        A pair of VTK renderer and render windown object.
    """
    # Mapper and actor
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(poly_data)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    # Create the renderer, render window, and interactor
    renderer = vtk.vtkRenderer()
    render_window = vtk.vtkRenderWindow()
    render_window.SetOffScreenRendering(1)  # Set it to 0 if there is an interactor
    render_window.SetMultiSamples(0)
    renderer.ResetCamera()
    render_window.AddRenderer(renderer)
    renderer.AddActor(actor)

    # Uncomment the following 2 lines to get an interactor
    # render_window_interactor = vtk.vtkRenderWindowInteractor()
    # render_window_interactor.SetRenderWindow(render_window)

    return renderer, render_window  # , render_windowdow_interactor


def get_vtk_scalar_mode(poly_data: vtk.vtkPolyData, var_name: str) -> int:
    """
    Given the var_name, get the scalar mode this var_name belongs to.

    Parameters
    ----------
    poly_data: vtk.vtkPolyData
        A VTK poly data object.
    var_name: str
        Variable name.

    Returns
    -------
    int
        An integer indicating the VTK scalar mode.
        VTK_SCALAR_MODE_USE_POINT_FIELD_DATA or VTK_SCALAR_MODE_USE_CELL_FIELD_DATA.

    Raises
    ------
    ValueError
        If the given var_name is in neither point data nor cell data,
        meaning the poly_data object does not have this variable.
    """
    point_data = poly_data.GetPointData()
    cell_data = poly_data.GetCellData()
    point_data_array = point_data.GetArray(var_name)
    cell_data_array = cell_data.GetArray(var_name)
    if point_data_array is not None:
        return vtk.VTK_SCALAR_MODE_USE_POINT_FIELD_DATA
    if cell_data_array is not None:
        return vtk.VTK_SCALAR_MODE_USE_CELL_FIELD_DATA
    raise ValueError(f"{var_name} does not belong to point data, nor cell data")


def setup_value_pass(
    poly_data: vtk.vtkPolyData, renderer: vtk.vtkRenderer, var_name: str
) -> vtk.vtkValuePass:
    """
    Bind the variable data (point or cell) to value pass, in order to render the given
    variable to each pixel.

    Parameters
    ----------
    poly_data: vtk.vtkPolyData
        A VTK poly data object.
    renderer: vtk.vtkRenderer
        A VTK renderer object.
    var_name: str
        Variable name.

    Returns
    -------
    vtk.vtkValuePass
        An integer indicating the VTK scalar mode.
        VTK_SCALAR_MODE_USE_POINT_FIELD_DATA or VTK_SCALAR_MODE_USE_CELL_FIELD_DATA.
    """
    value_pass = vtk.vtkValuePass()
    vtk_scalar_mode = get_vtk_scalar_mode(poly_data, var_name)
    value_pass.SetInputArrayToProcess(vtk_scalar_mode, var_name)
    value_pass.SetInputComponentToProcess(0)

    passes = vtk.vtkRenderPassCollection()
    passes.AddItem(value_pass)

    sequence = vtk.vtkSequencePass()
    sequence.SetPasses(passes)

    camera_pass = vtk.vtkCameraPass()
    camera_pass.SetDelegatePass(sequence)
    renderer.SetPass(camera_pass)

    return value_pass


def get_rgb_value(render_window: vtk.vtkRenderWindow) -> np.ndarray:
    """
    Get the RGB value from the render window. It starts from explicitly calling render
    window's Render function.

    Parameters
    ----------
    render_window: vtk.vtkRender
        A VTK poly data object.

    Returns
    -------
    vtk.vtkValuePass
        A VTK value pass object for the following around of rendering.
    """
    render_window.Render()

    width, height = render_window.GetSize()

    # Capture the rendering result
    window_to_image_filter = vtk.vtkWindowToImageFilter()
    window_to_image_filter.SetInput(render_window)
    window_to_image_filter.Update()

    # Get the image data
    image_data = window_to_image_filter.GetOutput()

    # Convert VTK image data to a NumPy array
    width, height, _ = image_data.GetDimensions()
    vtk_array = image_data.GetPointData().GetScalars()
    np_array = vtk_to_numpy(vtk_array)

    # Reshape the array to a 3D array (height, width, 3) for RGB
    np_array = np_array.reshape(height, width, -1)

    # If an interactor in involved, uncomment the next line
    # render_window_interactor.Start()

    return np_array


def render_pick_data(
    poly_data: vtk.vtkPolyData, renderer: vtk.vtkRenderer, render_window: vtk.vtkRenderWindow
) -> np.ndarray:
    """
    Generate a buffer containing pick data from around of rendering by the value pass.

    Parameters
    ----------
    poly_data: vtk.vtkPolyData
        A VTK poly data object.
    renderer: vtk.vtkRenderer
        A VTK renderer object.
    render_window: vtk.vtkRender
        A VTK poly data object.

    Returns
    -------
    np.ndarray
        A numpy array as RGB format but only R and B channels are effective.
        Specifically, R channel stores the lower 8 bits of the pick data; G channel
        stores the higher 8.
    """
    value_pass = setup_value_pass(poly_data, renderer, "Pick Data")

    render_window.Render()

    buffer = value_pass.GetFloatImageDataArray(renderer)
    np_buffer = vtk_to_numpy(buffer)

    # Use NaN mask to eliminate NaN in np_buffer
    width, height = render_window.GetSize()
    np_buffer = np_buffer.reshape(height, width)
    nan_mask = np.isnan(np_buffer)
    np_buffer = np.where(nan_mask, 0, np_buffer)  # Reset NaN to 0

    np_buffer = np_buffer.astype(np.int16)
    pick_buffer = np.zeros((height, width, 4), dtype=np.uint8)

    # Store the lower 8 bits to pick_buffer's R channel
    pick_buffer[:, :, 0] = np_buffer & 0xFF
    # Store the higher 8 bits to pick_buffer's G channel
    pick_buffer[:, :, 1] = (np_buffer >> 8) & 0xFF

    return pick_buffer


def render_var_data(
    poly_data: vtk.vtkPolyData,
    renderer: vtk.vtkRenderer,
    render_window: vtk.vtkRenderWindow,
    var_name: str,
) -> np.ndarray:
    """
    Generate a buffer containing variable data from a round of rendering by the value
    pass.

    Parameters
    ----------
    poly_data: vtk.vtkPolyData
        A VTK poly data object.
    renderer: vtk.vtkRenderer
        A VTK renderer object.
    render_window: vtk.vtkRender
        A VTK poly data object.
    var_name: str
        The variable name.

    Returns
    -------
    np.ndarray
        A numpy array as float32 format. Each value represents the variable data on a pixel.
    """
    value_pass = setup_value_pass(poly_data, renderer, var_name)

    render_window.Render()

    buffer = value_pass.GetFloatImageDataArray(renderer)
    np_buffer = vtk_to_numpy(buffer)
    width, height = render_window.GetSize()
    np_buffer = np_buffer.reshape(height, width)
    return np_buffer


def form_enhanced_image(
    json_data: Dict,
    rgb_buffer: np.ndarray,
    pick_buffer: np.ndarray,
    var_buffer: np.ndarray,
    output: Union[str, io.BytesIO],
) -> None:
    """
    A helper function. Build up an enhanced image and output to either a TIFF file on
    disk or to a byte buffer.

    Parameters
    ----------
    json_data: Dict
        A dictionary that contains "parts" and "variables" sections.
    rgb_buffer: np.ndarray
        A int8 buffer with RGB values. Its dimension is [height, width, 3].
    pick_buffer: np.ndarray
        A int8 buffer with pick data. Its dimension is [height, width, 3].
    var_buffer: np.ndarray
        A float32 buffer with variable data. Its dimension is [height, width].
    output: Union[str, io.BytesIo]
        Specify the output to be either a file name or a byte buffer.
    """
    # json_data as metadata called image_description to store in the enhanced image
    image_description = json.dumps(json_data)

    # Create 3 images for each page
    rgb_image = Image.fromarray(rgb_buffer, mode="RGB")
    pick_image = Image.fromarray(pick_buffer, mode="RGBA")
    var_image = Image.fromarray(var_buffer, mode="F")

    # Set up the metadata
    tiffinfo = TiffImagePlugin.ImageFileDirectory_v2()
    tiffinfo[TiffImagePlugin.IMAGEDESCRIPTION] = image_description

    rgb_image.save(
        output,
        format="TIFF",
        save_all=True,
        append_images=[pick_image, var_image],
        tiffinfo=tiffinfo,
    )


def generate_enhanced_image(
    model: dpf.Model, var_field: dpf.Field, part_name: str, output: Union[str, io.BytesIO]
) -> Tuple[Dict, np.ndarray, np.ndarray, np.ndarray]:
    """
    Esstential helper function for DPF inputs. Generate json metadata, rgb buffer, pick
    data buffer and variable data buffer from a DPF model object and a DPF field object.

    Parameters
    ----------
    model: dpf.Model
        A DPF model object.
    var_field: dpf.Field
        A DPF field object that comes from the given model. The field is essentially
        the variable in interest to visualize in an enhanced image.
    part_name: str
        The name of the part. It will showed on the interactive enhanced image in ADR.

    Returns
    -------
    Tuple[Dict, np.ndarray, np.ndarray, np.ndarray]
        A tuple of JSON metadata, rgb buffer, pick data buffer and variable data buffer
    """
    # Todo: vector data support: is_scalar_data = var_data.ndim == 1

    # Get components for metadata
    var_unit: str = var_field.unit
    var_name = var_field.name
    var_meshed_region = var_field.meshed_region
    dpf_unit_system = model.metadata.result_info.unit_system_name
    unit_system_to_name = dpf_unit_system.split(":", 1)[0]

    mats: dpf.PropertyField = var_meshed_region.property_field("mat")  # Pick data

    # Convert DPF to a pyvista UnstructuredGrid, which inherits from vtk
    grid = vtk_helper.dpf_mesh_to_vtk(var_meshed_region)
    # Add pick data
    grid = vtk_helper.append_field_to_grid(mats, var_meshed_region, grid, "Pick Data")
    # Add variable data
    grid = vtk_helper.append_field_to_grid(var_field, var_meshed_region, grid, var_name)

    # Create a vtkGeometryFilter to convert UnstructuredGrid to PolyData
    geometry_filter = vtk.vtkGeometryFilter()
    geometry_filter.SetInputData(grid)
    geometry_filter.Update()
    poly_data = geometry_filter.GetOutput()

    renderer, render_window = setup_render_routine(poly_data)
    rgb_buffer = get_rgb_value(render_window)
    pick_buffer = render_pick_data(grid, renderer, render_window)
    var_buffer = render_var_data(grid, renderer, render_window, var_name)

    # Todo: automatic colorby_var support
    # global colorby_var_id
    # colorby_var_int = colorby_var_id
    # colorby_var_id += 1
    # colorby_var_decimal = 0 if is_scalar_data else 1
    # Todo: .1, .2, .3 corresponds to x, y, z dimension. Only supports scalar for now
    # colorby_var = f"{colorby_var_int}.{colorby_var_decimal}"

    # For now, it only supports one part with one variable
    json_data = {
        "parts": [
            {
                "name": part_name,
                "id": str(mats.data[0]),
                "colorby_var": "1.0",  # colorby_var
            }
        ],
        "variables": [
            {
                "name": var_name,
                "id": str(mats.data[0]),
                "pal_id": "1",  # colorby_var_int,
                "unit_dims": "",
                "unit_system_to_name": unit_system_to_name,
                "unit_label": var_unit,
            }
        ],
    }

    form_enhanced_image(json_data, rgb_buffer, pick_buffer, var_buffer, output)


def generate_enhanced_image_as_tiff(
    model: dpf.Model, var_field: dpf.Field, part_name: str, output_file_name: str
):
    """
    Generate an enhanced image in the format of TIFF file on disk given DPF inputs.

    Parameters
    ----------
    model: dpf.Model
        A DPF model object.
    var_field: dpf.Field
        A DPF field object that comes from the given model. The field is essentially
        the variable in interest to visualize in an enhanced image.
    part_name: str
        The name of the part. It will showed on the interactive enhanced image in ADR.
    output_file_name: str
        output TIFF file name with extension of .tiff or .tif
    """
    generate_enhanced_image(model, var_field, part_name, output_file_name)


def generate_enhanced_image_in_memory(
    model: dpf.Model, var_field: dpf.Field, part_name: str
) -> Image:
    """
    Generate an enhanced image as a PIL Image object given DPF inputs.

    Parameters
    ----------
    model: dpf.Model
        A DPF model object.
    var_field: dpf.Field
        A DPF field object that comes from the given model. The field is essentially
        the variable in interest to visualize in an enhanced image.
    part_name: str
        The name of the part. It will showed on the interactive enhanced image in ADR.

    Returns
    -------
    Image
        A PIL Image object that represents the enhanced image.
    """
    # Create an in-memory bytes buffer
    buffer = io.BytesIO()
    generate_enhanced_image(model, var_field, part_name, buffer)
    buffer.seek(0)
    image = Image.open(buffer)
    return image
