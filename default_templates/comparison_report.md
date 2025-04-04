# Comparison report

Template for a report aggregating and comparing multiple simulations in the context of a parametric study. The user would be running multiple analysis of similar models / physics, and use this report template to visualize, compare and further analyze the results from all these design points into a single report.

## Structure of the report

The generated report will have the following structure:

```text
Report
├── Logo
├── Title
├── Header
├── Table of Content
├── Design Points Table
├── Base Case Simulation Setup
│   ├── Physics
│   |   ├── Models
│   |   ├── Material Properties
│   |   ├── Cell Zones Conditions
│   |   ├── Bounday Conditions
│   |   ├── Reference Values
│   ├── Solver Settings
├── Parametrics Plots
│   ├── ParametricPlotTabs
├── Mesh
│   ├── Mesh slider
│   ├── Mesh comparison
├── Contours
│   ├── Contours slider
│   ├── Contours comparison
├── Pathlines
│   ├── Pathlines slider
│   ├── Pathlines comparison
├── XY Plots
│   ├── Static Pressure
├── Scenes
│   ├── Scenes slider
│   ├── Scenes comparison
```

Note that the slide and comparison leafs (such as the Mesh slider and Mesh comparison) will display the same data in two different tabs, but in the slider case the images are collapsed into a single slider view, while in the comparison tab they are available side-by-side for quick comparison. The differences are set in the template properties.

Note that the "XY Plots" will do a merge of all tables coming from all design points to display the values all in a single plot for easier comparison between simulation results.

You can add or modify the structure of the report by adding / removing / modifying the corresponding report templates.

## Filters

Each report section is populated with items from the database that pass the aggregated filters. You can modify these filters to fit your database.

The report is written assuming that all data is tagged with a 'Design Point=DPX' tag that marks which design point each item refers to. Please adjust the filters accordingly if this isn't the case in you database.

At the top level, there is a filter for item tags containing the string 'Design Point' and 'ReportType=Parametric'.

The following tree displays the filter for each report leaf. This template mainly uses item names, types and tags to place them in the correct section.

```text
Report -> Items with  'Design Point' and 'ReportType=Parametric' in the tag
├── Logo -> Image itam with name "AnsysLogo" or "UserLogo"
├── Title -> HTML item with name "ReportTitle"
├── Header -> Table item with name "HeaderTableItem"
├── Table of Content -> NO ITEMS HERE. Table of Content is automatically generated
├── Design Points Table -> Table item with name "ParameterDesignPointsTable"
├── Base Case Simulation Setup
│   ├── Physics
│   |   ├── Models -> Table item with name "ModelsTableItem" and tags with "'Design Point'='Base DP'"
│   |   ├── Material Properties -> Tree item with name "MaterialsTreeItem" and tags with "'Design Point'='Base DP'"
│   |   ├── Cell Zones Conditions -> Tree item with name "CellZonesTreeItem" and tags with "'Design Point'='Base DP'"
│   |   ├── Bounday Conditions -> Tree item with name "BoundaryZonesTreeItem" and tags with "'Design Point'='Base DP'"
│   |   ├── Reference Values -> Tree item with name "ReferenceValuesTableItem" and tags with "'Design Point'='Base DP'"
│   ├── Solver Settings -> Tree item with name "SolverSettingsTreeItem" and tags with "'Design Point'='Base DP'"
├── Parametrics Plots
│   ├── ParametricPlotTabs -> Table item with name that contains '_parametric_plot'
├── Mesh
│   ├── Mesh slider -> Image items with "_mesh" in the name
│   ├── Mesh comparison -> Image items with "_mesh" in the name
├── Contours
│   ├── Contours slider -> Image items with "_contour" in the name
│   ├── Contours comparison -> Image items with "_contour" in the name
├── Pathlines
│   ├── Pathlines slider -> Image items with "_pathline" in the name
│   ├── Pathlines comparison -> Image items with "_pathline" in the name
├── XY Plots -> Table items with "_xyplot" in the name
│   ├── Static Pressure -> Items with "top-wall_xyplot" in the name
├── Scenes
│   ├── Scenes slider -> Image items with "_scene" in the name
│   ├── Scenes comparison -> Image items with "_scene" in the name
```
