# PPTX export report

Report template for a report to export in PPTX. Please note that for this to work, the database needs to contain a PPTX file called "Simulation_Report_input_ppt.pptx" with master slides and placeholders that describe how each item will be rendered in the exported PPTX file.

## Structure of the report

For each leaf template, the properties need to include "source_slide" to point to which master slide to use from the input PPTX file as a source for this leaf.
The generated PPTX file will have the following structure:

```text
Report
├── ReportTitleText_template_ppt
├── TOC_template_ppt
├── Header_template_ppt
├── System Information_template_ppt
├── Geometry and Mesh_template_ppt
│   ├── Mesh Size_template_ppt
│   ├── Mesh Quality_template_ppt
│   ├── Orthogonal Quality_template_ppt
├── Simulation Setup_template_ppt
│   ├── Physics_template_ppt
│   ├── ├── Models_template_ppt
│   ├── ├── Material Properties_template_ppt
│   ├── ├── Cell Zones Conditions_template_ppt
│   ├── ├── Boundary Conditions_template_ppt
│   ├── ├── Reference Values_template_ppt
│   ├── Solver Settings_template_ppt
├── Run Information_template_ppt
├── Solution Status_template_ppt
├── Named Expressions_template_ppt
├── Report Definitions_template_ppt
├── Plots_template_ppt
│   ├── Residuals_template_ppt
│   ├── Residual Plots_template_ppt
│   ├── ├── Residual Plots_child_template_ppt
├── Mesh_template_ppt
│   ├── Mesh_child_template_ppt
├── Pathlines_template_ppt
│   ├── Pathlines_child_template_ppt
├── Contours_template_ppt
    ├── Contours_child_template_ppt
```

## Filters

Each report section is populated with items from the database that pass the aggregated filters. You can modify these filters to fit your database.

The following tree displays the filter for each report leaf. The idea is to use item names and types to place them in the correct section.

```text
Report
├── ReportTitleText_template_ppt
├── TOC_template_ppt
├── Header_template_ppt -> Table item with name "HeaderTableItem"
├── System Information_template_ppt -> Table item with name "SystemTableItem"
├── Geometry and Mesh_template_ppt
│   ├── Mesh Size_template_ppt -> Table item with name "MeshSizeTableItem"
│   ├── Mesh Quality_template_ppt -> Table item with name "MeshQualityTableItem"
│   ├── Orthogonal Quality_template_ppt -> Table item with name "MeshSizeTableItem"
├── Simulation Setup_template_ppt -> Table image with name "MeshOrthogonalHistogram"
│   ├── Physics_template_ppt
│   ├── ├── Models_template_ppt -> Table item with name "ModelsTableItem"
│   ├── ├── Material Properties_template_ppt -> Tree item with name "MaterialsTreeItem"
│   ├── ├── Cell Zones Conditions_template_ppt -> Tree item with name "CellZonesTreeItem"
│   ├── ├── Boundary Conditions_template_ppt -> Tree item with name "Boundary"
│   ├── ├── Reference Values_template_ppt -> Table item with name "ReferenceValuesTableItem"
│   ├── Solver Settings_template_ppt -> Tree item with name "SolverSettingsTreeItem"
├── Run Information_template_ppt -> Table item with name "RunTableItem"
├── Solution Status_template_ppt -> Table item with name "SolverStatusTableItem"
├── Named Expressions_template_ppt -> Table item with name "ExpressionsTableItem"
├── Report Definitions_template_ppt -> Table item with name "ReportDefinitionsTreeItem"
├── Plots_template_ppt
│   ├── Residuals_template_ppt -> Table item with name "residuals_plot"
│   ├── Residual Plots_template_ppt
│   ├── ├── Residual Plots_child_template_ppt -> Table item with name "_plot"
├── Mesh_template_ppt
│   ├── Mesh_child_template_ppt -> Image item with name "_mesh_"
├── Pathlines_template_ppt
│   ├── Pathlines_child_template_ppt -> Image item with name "_pathline"
├── Contours_template_ppt
    ├── Contours_child_template_ppt -> Image item with name "_contour"
```
