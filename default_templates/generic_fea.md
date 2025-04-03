# Generic FEA report

Report template for a coupled Structural and Thermal analysis.

## Structure of the report

The generated report will have the following structure:

```text
Report
├── Image
├── Header
├── Report Title
├── Executive Summary
├── Table of Content
├── Introduction
│   ├── Background
│   ├── Problem Statement
│   ├── Objectives
│   ├── Scope
├── Methodology
│   ├── Geometry and Mesh Generation
│   ├── Material Properties
│   ├── Structural Analysis
│   ├── Thermal Analysis
│   ├── Coupled Structural-Thermal Results
├── Results
│   ├── Structural Analysis Results
│   ├── Thermal Analysis Results
│   ├── Coupled Structural-Thermal Results
├── Discussion
│   ├── Structural Analysis Discussion
│   ├── Thermal Analysis Discussion
│   ├── Coupled Structural-Thermal Discussion
├── References
├── Conclusions
│   ├── Summary
│   ├── Recommendations
├── Appendices
│   ├── Appendix-A
│   ├── Appendix-B
```

You can add or modify the structure of the report by adding / removing / modifying the corresponding report templates.

## Filters

Each report section is populated with items from the database that pass the aggregated filters. You can modify these filters to fit your database.

At the top level, there is a filter for item tags containing the string 'projectA'. Only items that pass this filter will be added into the report.

The following tree displays the filter for each report leaf. The idea is to use item names and tags to place them in the correct section.

```text
Report -> item tag contains "projectA"
├── Image -> item tag contains "logo"
├── Header -> NO ITEMS HERE. The text comes from the template HTML
├── Report Title -> NO ITEMS HERE. The title comes from the template HTML
├── Executive Summary -> item name contains "overview"
├── Table of Content -> NO ITEMS HERE. Automatically generated
├── Introduction
│   ├── Background -> item tags contain "section=background"
│   ├── Problem Statement -> item tags contain "section=problem"
│   ├── Objectives -> item tags contain "section=objectives"
│   ├── Scope -> item tags contain "section=scope"
├── Methodology -> item tags contain "chapter=methodology"
│   ├── Geometry and Mesh Generation -> item tags contain "section=mesh"
│   ├── Material Properties -> item tags contain "section=materials"
│   ├── Structural Analysis -> item tags contain "section=structural"
│   ├── Thermal Analysis -> item tags contain "section=thermal"
│   ├── Coupled Structural-Thermal Results -> item tags contain "section=coupled"
├── Results -> item tags contain "chapter=results"
│   ├── Structural Analysis Results -> item tags contain "section=structural"
│   ├── Thermal Analysis Results -> item tags contain "section=thermal"
│   ├── Coupled Structural-Thermal Results -> item tags contain "section=coupled"
├── Discussion -> item tags contain "chapter=discussion"
│   ├── Structural Analysis Discussion -> item tags contain "section=structural"
│   ├── Thermal Analysis Discussion -> item tags contain "section=thermal"
│   ├── Coupled Structural-Thermal Discussion -> item tags contain "section=coupled"
├── References -> item name contain "chapter=references"
├── Conclusions-> item tags contain "chapter=conclusions"
│   ├── Summary -> item tags contain "session=summary"
│   ├── Recommendations -> item tags contain "session=recommendations"
├── Appendices -> item name contain "chapter=appendices"
│   ├── Appendix-A -> item tags contain "session=appendixA"
│   ├── Appendix-B -> item tags contain "session=appendixB"
```


Please remember that for each leaf, you need to take into account all the filters of its parent. So for example for an item to be displayed in the "Geometry and Mesh Generation" section of the "Methodology" chapter, it will need to have tags that contain "projectA" AND tags that contain "chapter=methodology" AND tags that contain "section=mesh".
