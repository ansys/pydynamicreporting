# Single simulation report

Basic report template for a single simulation. The report covers from the problem statement to the mesh and solver settings, and simulation results.

## Structure of the report

The generated report will have the following structure:

```text
Report
├── Logo
├── Title
├── Header
├── Table of Content
├── System Information
├── Geometry and Mesh
│   ├── Mesh Size
│   ├── Mesh Quality
│   ├── Orthogonal Quality
├── Simulation Setup
│   ├── Physics
│   |   ├── Models
│   |   ├── Material Properties
│   |   ├── Bounday Conditions
│   |   ├── Reference Values
│   ├── Solver Settings
├── Run Information
├── Solution Status
├── Plots
│   ├── Tabs of plots
├── Mesh
│   ├── Tabs of mesh images
├── Contours
│   ├── Tabs of contours images
├── Pathlines
│   ├── Tabs of pathline images
├── Scenes
│   ├── Tabs of 3D scenes
├── Animations
    ├── Tabs of animation files
```

You can add or modify the structure of the report by adding / removing / modifying the corresponding report templates.

## Filters

Each report section is populated with items from the database that pass the aggregated filters. You can modify these filters to fit your database.

At the top level, there is a filter for item tags containing the string 'simulation=runA'. The idea is to isolate items related to a specific simulation run. Only items that pass this filter will be added into the report.

The following tree displays the filter for each report leaf. This template mainly uses item names, types and tags to place them in the correct section.

```text
Report -> item tag contains "simulation=runA"
├── Logo -> item is an image with name "AnsysLogo" or "UserLogo"
├── Title -> item is of HTML type with name "ReportTitle"
├── Header -> item is a table with name "HeaderTableItem"
├── Table of Content -> NO ITEMS HERE. Table of Content is automatically generated
├── System Information -> Table item with name "SystemTableItem"
├── Geometry and Mesh
│   ├── Mesh Size -> Table item with name "MeshSizeTableItem"
│   ├── Mesh Quality -> Table item with name "MeshQualityTableItem"
│   ├── Orthogonal Quality -> Image item with name "MeshOrthogonalHistogram"
├── Simulation Setup
│   ├── Physics
│   |   ├── Models -> Table item with name "ModelsTableItem"
│   |   ├── Material Properties -> Tree item with name "MaterialsTreeItem"
│   |   ├── Bounday Conditions -> Tree item with name "BoundaryZonesTreeItem"
│   |   ├── Reference Values -> Table item with name "ReferenceValuesTableItem"
│   ├── Solver Settings -> Tree item with name "SolverSettingsTreeItem"
├── Run Information -> Table item with name "RunTableItem"
├── Solution Status -> Table item with name "SolverStatusTableItem"
├── Plots
│   ├── Tabs of plots -> Table item with name "residuals_plot"
├── Mesh
│   ├── Tabs of mesh images -> Image item with name "mesh1"
├── Contours
│   ├── Tabs of contours images -> Image item with name that contains "_contour1" or "_contour2"
├── Pathlines
│   ├── Tabs of pathline images -> Image item with name "pathlines-1" or "pathlines-2"
├── Scenes
│   ├── Tabs of 3D scenes -> Scene item with name that contains "scene-1" or "scene-2"
├── Animations
    ├── Tabs of animation files -> Animation item with name that contains "animation-1" or "animation-2"
```

For the tabs sections, you can create a new template child for each object you want to place in a separate tab. Remember to set the filters correctly on each child template. This is just an example to place one or two tabs on each of these sections.