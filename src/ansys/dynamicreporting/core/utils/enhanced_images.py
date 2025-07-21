"""
Methods that generate enhanced images.

A group of functions that mainly create:
1. RGB buffer
2. Pick data buffer
3. Variable data buffer

Then combine these 3 buffers along with a JSON metadata to generate a 3-page
enhanced image.
"""

from collections.abc import Callable
import io
import json
import logging

from PIL import Image, TiffImagePlugin
import numpy as np

try:
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy

    HAS_VTK = True
except ImportError as e:  # pragma: no cover
    HAS_VTK = False
    logging.warning(e)

try:
    from ansys.dpf import core as dpf
    from ansys.dpf.core import vtk_helper

    HAS_DPF = True
except (ImportError, ValueError) as e:  # pragma: no cover
    HAS_DPF = False
    logging.warning(e)


if HAS_VTK and HAS_DPF:

    def generate_enhanced_image_as_tiff(
        model: dpf.Model,
        var_field: dpf.Field,
        part_name: str,
        var_name: str,
        output_file_name: str,
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
        component: str = None,
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
        var_name: str
            The name of the variable. It will showed on the interactive enhanced image in ADR.
        output_file_name: str
            output TIFF file name with extension of .tiff or .tif.
        rotation: Tuple[float, float, float]
            Rotation degrees about X, Y, Z axes. Note not in radians.
        component: str
            For vector variable, specify which component to plot, 'X', 'Y' or 'Z'.
            Leave it unfilled if it is a scalar variable.
        """
        _generate_enhanced_image(
            model, [(var_field, component)], part_name, var_name, output_file_name, rotation
        )

    # def generate_enhanced_image_as_tiff_multi_var_pages(
    #     model: dpf.Model,
    #     var_fields: list[Tuple[dpf.Field, str]],  # a list of dpf.Field and component
    #     part_name: str,
    #     var_name: str,
    #     output_file_name: str,
    #     rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    # ):
    #     _generate_enhanced_image(
    #         model, var_fields, part_name, var_name, output_file_name, rotation
    #     )

    def generate_enhanced_image_in_memory(
        model: dpf.Model,
        var_field: dpf.Field,
        part_name: str,
        var_name: str,
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
        component: str = None,
    ) -> io.BytesIO:
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
         var_name: str
            The name of the variable. It will showed on the interactive enhanced image in ADR.
        rotation: Tuple[float, float, float]
            Rotation degrees about X, Y, Z axes. Note not in radians.
        component: str
            For vector variable, specify which component to plot, 'X', 'Y' or 'Z'
            Leave it unfilled if it is a scalar variable.

        Returns
        -------
        buffer
            A IO buffer that represents the enhanced image.
            The returned buffer can be opened by PIL Image.open
        """
        # Create an in-memory bytes buffer
        buffer = io.BytesIO()
        _generate_enhanced_image(
            model, [(var_field, component)], part_name, var_name, buffer, rotation
        )
        buffer.seek(0)
        return buffer

    def _setup_render_routine(
        poly_data: vtk.vtkPolyData, rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    ) -> tuple[vtk.vtkRenderer, vtk.vtkRenderWindow]:
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
        actor.RotateX(rotation[0])
        actor.RotateY(rotation[1])
        actor.RotateZ(rotation[2])

        # Create renderer and render window
        renderer = vtk.vtkRenderer()
        renderer.SetBackground(1, 1, 1)  # White background
        renderer.AddActor(actor)

        render_window = vtk.vtkRenderWindow()
        render_window.SetOffScreenRendering(1)
        render_window.SetSize(3840, 2160)

        render_window.AddRenderer(renderer)

        # Enable depth peeling for accurate depth sorting
        renderer.SetUseDepthPeeling(True)  # For transparency
        renderer.SetOcclusionRatio(0.1)
        renderer.SetMaximumNumberOfPeels(100)

        # Reset the camera after setting up the scene
        renderer.ResetCamera()

        # Uncomment the following 2 lines to get an interactor
        # render_window_interactor = vtk.vtkRenderWindowInteractor()
        # render_window_interactor.SetRenderWindow(render_window)

        return renderer, render_window  # , render_windodow_interactor

    def _get_vtk_scalar_mode(poly_data: vtk.vtkPolyData, var_name: str) -> int:
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

    def _setup_value_pass(
        poly_data: vtk.vtkPolyData, renderer: vtk.vtkRenderer, var_name: str
    ) -> vtk.vtkValuePass:
        """
        -------------------------------------------------------------------------------------
        IMPORTANT

        11/20/2024
        VTK has a bug in vtkValuePass, resulting in rendering inconsistency by depth buffer.
        VTK version before 9.3.1 (inclusive) has this problem.
        -------------------------------------------------------------------------------------

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
        vtk_scalar_mode = _get_vtk_scalar_mode(poly_data, var_name)
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

    def _get_rgb_value(render_window: vtk.vtkRenderWindow) -> np.ndarray:
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

    def _add_pick_data(poly_data: vtk.vtkPolyData, part_id: int):
        arr = vtk.vtkIntArray()
        arr.SetName("Pick Data")
        arr.SetNumberOfComponents(1)
        num_points = poly_data.GetNumberOfPoints()
        arr.SetNumberOfTuples(num_points)
        for i in range(num_points):
            arr.SetValue(i, part_id)
        poly_data.GetPointData().AddArray(arr)
        poly_data.Modified()

    def _render_pick_data(
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
        value_pass = _setup_value_pass(poly_data, renderer, "Pick Data")

        render_window.Render()

        buffer = value_pass.GetFloatImageDataArray(renderer)
        np_buffer = vtk_to_numpy(buffer)

        # Use NaN mask to eliminate NaN in np_buffer
        width, height = render_window.GetSize()
        np_buffer = np_buffer.reshape(height, width)
        nan_mask = np.isnan(np_buffer)
        np_buffer = np.where(nan_mask, 0, np_buffer)  # Reset NaN to 0
        np_buffer = np.round(np_buffer).astype(np.int16)  # Round it up before casting
        pick_buffer = np.zeros((height, width, 4), dtype=np.uint8)

        # Store the lower 8 bits to pick_buffer's R channel
        pick_buffer[:, :, 0] = np_buffer & 0xFF
        # Store the higher 8 bits to pick_buffer's G channel
        pick_buffer[:, :, 1] = (np_buffer >> 8) & 0xFF

        return pick_buffer

    def _render_var_data(
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
        value_pass = _setup_value_pass(poly_data, renderer, var_name)

        render_window.Render()

        buffer = value_pass.GetFloatImageDataArray(renderer)
        np_buffer = vtk_to_numpy(buffer)
        width, height = render_window.GetSize()
        np_buffer = np_buffer.reshape(height, width)
        return np_buffer

    def _form_enhanced_image(
        json_data: dict,
        rgb_buffer: np.ndarray,
        pick_buffer: np.ndarray,
        var_buffers: list[np.ndarray],
        output: str | io.BytesIO,
    ) -> None:
        """
        A helper function. Build up an enhanced image and output to either a TIFF file on
        disk or to a byte buffer.

        Parameters
        ----------
        json_data: Dict
            A dictionary that contains "parts" and "variables" sections.
        rgb_buffer: np.ndarray
            An int8 buffer with RGB values. Its dimension is [height, width, 3].
        pick_buffer: np.ndarray
            An int8 buffer with pick data. Its dimension is [height, width, 3].
        var_buffers: list[np.ndarray]
            A list of float32 buffers with variable data. Each buffer's dimension is [height, width].
        output: Union[str, io.BytesIo]
            Specify the output to be either a file name or a byte buffer.
        """
        # json_data as metadata called image_description to store in the enhanced image
        image_description = json.dumps(json_data)

        # Create the RGB and pick images
        rgb_image = Image.fromarray(rgb_buffer, mode="RGB")
        pick_image = Image.fromarray(pick_buffer, mode="RGBA")

        # Convert variable buffers to images
        var_images = [Image.fromarray(var_buffer, mode="F") for var_buffer in var_buffers]

        # Set up the metadata
        tiffinfo = TiffImagePlugin.ImageFileDirectory_v2()
        tiffinfo[TiffImagePlugin.IMAGEDESCRIPTION] = image_description

        # Save the TIFF file with all images
        rgb_image.save(
            output,
            format="TIFF",
            save_all=True,
            append_images=[pick_image] + var_images,
            tiffinfo=tiffinfo,
        )

    def _trim_vector_data(
        var_name: str, col: int, get_data: Callable[[], vtk.vtkDataSetAttributes]
    ) -> None:
        data = get_data()
        vtk_array = data.GetArray(var_name)
        var_array = vtk_to_numpy(vtk_array)
        idx_array = var_array[:, col]

        trimmed_vtk_array = numpy_to_vtk(idx_array, deep=True)
        trimmed_vtk_array.SetName(var_name)
        data.RemoveArray(var_name)
        data.AddArray(trimmed_vtk_array)

    def _generate_enhanced_image(
        model: dpf.Model,
        var_fields: list[tuple[dpf.Field, str]],  # a list of dpf.Field and component
        part_name: str,
        var_name: str,
        output: str | io.BytesIO,
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        """
        Essential helper function for DPF inputs. Generate json metadata, rgb buffer, pick
        data buffer and variable data buffer from a DPF model object and a DPF field object.

        Parameters
        ----------
        model: dpf.Model
            A DPF model object.
        var_field: list[Tuple[dpf.Field, str]]
            A list of dpf.Field and component pairs, where,
            1. the component is denoted as a string of 'X', 'Y' or 'Z' to indicate which component to plot
               if the field is a vector variable. Otherwise, leave it as None if scalar.
            2. the DPF field object comes from the given model. The field is essentially the variable
               in interest to visualize in an enhanced image.
        part_name: str
            The name of the part. It will showed on the interactive enhanced image in ADR.
        var_name: str
            The name of the variable. It will showed on the interactive enhanced image in ADR.
        rotation: Tuple[float, float, float]
            Rotation degrees about X, Y, Z axes. Note not in radians.
        """
        count = 0
        rgb_buffer = None
        pick_buffer = None
        var_buffers = []
        json_data_variables = []
        for var_field, component in var_fields:
            # Todo: vector data support: is_scalar_data = var_data.ndim == 1
            is_vector_var = var_field.data.ndim > 1
            if is_vector_var:  # if it is a vector variable
                if component is None:
                    raise ValueError(
                        "Error when generating an enhanced image: The field data is a vector variable. "
                        "Currently, we do not fully support vector variables. "
                        "Please specify which component you want to plot upon: 'X', 'Y', or 'Z'."
                    )
                if component not in ("X", "Y", "Z"):
                    raise ValueError(
                        "Error when generating an enhanced image: "
                        "The parameter 'component' only accepts 'X', 'Y', or 'Z'."
                    )

            # Get components for metadata
            var_unit: str = var_field.unit
            dpf_unit_system = model.metadata.result_info.unit_system_name
            unit_system_to_name = dpf_unit_system.split(":", 1)[0]
            meshed_region = model.metadata.meshed_region  # Whole mesh region
            json_data_variables.append(
                {
                    "name": var_name,
                    "id": "3456",  # Todo: optimize hardcoded part ID
                    "pal_id": "1",  # colorby_var_int,
                    "unit_dims": "",
                    "unit_system_to_name": unit_system_to_name,
                    "unit_label": var_unit,
                }
            )

            # Convert DPF to a pyvista UnstructuredGrid, which inherits from vtk
            grid = vtk_helper.dpf_mesh_to_vtk(meshed_region)
            # Add variable data
            grid = vtk_helper.append_field_to_grid(var_field, meshed_region, grid, var_name)

            geometry_filter = vtk.vtkGeometryFilter()
            geometry_filter.SetInputData(grid)
            geometry_filter.Update()
            poly_data = geometry_filter.GetOutput()

            # Extract the required component from the vector data
            if is_vector_var:
                if component == "X":
                    col = 0
                elif component == "Y":
                    col = 1
                else:
                    col = 2

                vtk_scalar_mode = _get_vtk_scalar_mode(poly_data, var_name)
                if vtk_scalar_mode == vtk.VTK_SCALAR_MODE_USE_POINT_FIELD_DATA:
                    _trim_vector_data(var_name, col, poly_data.GetPointData)
                else:
                    _trim_vector_data(var_name, col, poly_data.GetCellData)

            renderer, render_window = _setup_render_routine(poly_data, rotation)
            if count == 0:
                rgb_buffer = _get_rgb_value(render_window)
                # Assign the pick data
                _add_pick_data(poly_data, 3456)
                pick_buffer = _render_pick_data(poly_data, renderer, render_window)

            var_buffer = _render_var_data(poly_data, renderer, render_window, var_name)
            var_buffers.append(var_buffer)
            count += 1

        json_data = {
            "parts": [
                {
                    "name": part_name,
                    "id": "3456",  # Todo: optimize hardcoded part ID
                    "colorby_var": "1.0",  # colorby_var
                }
            ],
            "variables": json_data_variables,
        }

        _form_enhanced_image(json_data, rgb_buffer, pick_buffer, var_buffers, output)
