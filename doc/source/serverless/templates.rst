Templates
=========

Templates in Serverless ADR define the **layout**, **organization**, and **presentation**
of your report content. They control how Items are arranged, filtered, and rendered
within a report, enabling flexible, reusable, and dynamic reporting structures.

Overview
--------

Templates are Python classes derived from the base ``Template`` model. They come in two main flavors:

- **Layouts**: Define static or semi-static page structures (e.g., panels, tabs, carousels).
- **Generators**: Automate dynamic content generation by iterating, merging, filtering, or sorting Items.

Templates can be nested hierarchically to form complex reports with multiple sections and subsections.

Key Template Types
------------------

Some common built-in layout types:

- ``BasicLayout``: Simple container for report content with minimal structure.
- ``PanelLayout``: Defines a panel section, often used for grouping related content.
- ``BoxLayout``, ``TabLayout``, ``CarouselLayout``, ``SliderLayout``: Provide different UI paradigms for organizing items.
- ``TOCLayout``: Automatically generates a table of contents.
- ``HeaderLayout`` and ``FooterLayout``: Static header and footer regions.
- ``PPTXLayout`` and ``PPTXSlideLayout``: For PowerPoint integration and slide control.

Some important generator types:

- ``IteratorGenerator``: Iterates over a set of items and applies a sub-template.
- ``TableMergeGenerator`` and related filter generators: Merge, reduce, or filter tabular data.
- ``StatisticalGenerator``: Produces statistics or aggregated views of data.
- ``SQLQueryGenerator``: Executes SQL queries to produce data-driven content.

Creating Templates
------------------

Use the ADR instance’s ``create_template()`` method to create a new template object.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import BasicLayout

    top_template = adr.create_template(
        BasicLayout,
        name="Wing Simulation Report",
        parent=None,
        tags="project=wing_sim",
    )
    top_template.params = '{"HTML": "<h1>Wing Simulation Report</h1>"}'
    top_template.set_filter("A|i_tags|cont|project=wing_sim;")
    top_template.save()

Parent-child relationships can be established by passing a ``parent`` template during creation or by appending to ``parent.children`` and saving both.

Template Parameters and Properties
----------------------------------

Each template stores configuration and state in its ``params`` field, a JSON string representing:

- HTML content or raw strings (e.g., ``"HTML"``)
- Layout-specific options (e.g., column counts, widths)
- Filter parameters and modes controlling which Items are included
- Sorting options (fields, order, selection)
- Custom properties for user-defined metadata

You can manipulate these through provided methods:

- ``get_params()`` / ``set_params(dict)``
- ``add_params(dict)`` to merge parameters
- ``get_property()`` / ``set_property(dict)`` / ``add_property(dict)`` for the ``properties`` subset
- Sorting and filtering helpers (e.g., ``get_sort_fields()``, ``set_sort_fields()``, ``get_filter_mode()``, ``set_filter_mode()``)

Example modifying parameters:

.. code-block:: python

    params = top_template.get_params()
    params["HTML"] = "<h1>Updated Report Title</h1>"
    top_template.set_params(params)
    top_template.save()

Filters
-------

Filters control which Items are included in a template’s rendered output.

- Set via ``set_filter(filter_str)``, where ``filter_str`` is a query string, e.g.,
  ``"A|i_tags|cont|section=intro;"`` selects items tagged "section=intro".

- Filters can be extended via ``add_filter()``.

Sorting
-------

Templates can specify sorting of items by fields using:

- ``set_sort_fields([...])`` for sorting keys (e.g., ``["date", "name"]``)
- ``set_sort_selection("all" | "first" | "last")`` to choose which items from sorted groups to show.

Child Templates and Ordering
----------------------------

Templates maintain ordered children to compose hierarchical reports.

- The ``children`` attribute holds nested templates.
- ``children_order`` is a string of comma-separated GUIDs determining rendering order.
- Call ``reorder_children()`` to sync children list order with ``children_order`` field.

Rendering Templates
------------------

Templates can render themselves into complete HTML content using the ``render()`` method.

.. code-block:: python

    html_report = top_template.render(context={}, item_filter="A|i_tags|cont|project=wing_sim;")
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html_report)

Rendering context supports options like:

- ``plotly`` flag to enable interactive plots
- Page dimensions and DPI for layout calculations
- Date and time formatting

Error Handling
--------------

If rendering fails, the output HTML will contain an error message for easier debugging.

Lifecycle Notes
---------------

- Templates must be saved to persist changes.
- Parent templates must be saved before saving children.
- Children templates must be saved before their parent saves can complete successfully.
- Deleting a template typically requires handling or deleting its children to avoid orphaned templates.

Exceptions and Validation
-------------------------

- Creating or fetching templates with missing or invalid fields raises validation errors.
- Attempting to instantiate the base ``Template`` class directly raises an error.
- Filters using restricted keys (like ``t_types|``) are disallowed on subclasses.
- Invalid parent references or child types will raise type or integrity errors during saving.

Example: Creating a Nested Template Structure
---------------------------------------------

.. code-block:: python

    toc = adr.create_template(
        TOCLayout,
        name="Table of Contents",
        parent=top_template,
        tags="project=wing_sim",
    )
    toc.params = '{"HTML": "<h2>Contents</h2>"}'
    toc.set_filter("A|i_name|eq|__NonexistentName__;")
    toc.save()

    results_panel = adr.create_template(
        PanelLayout,
        name="Results",
        parent=top_template,
        tags="project=wing_sim",
    )
    results_panel.params = '{"HTML": "<h2>Results</h2><p>Simulation data and figures.</p>"}'
    results_panel.set_filter("A|i_tags|cont|section=results;")
    results_panel.save()

    top_template.children.append(results_panel)
    top_template.save()

Summary
-------

Templates are the backbone of report structure in Serverless ADR. They let you create
rich, dynamic, and highly customizable reports by defining layouts and generators,
setting filters and parameters, and nesting templates to build complex hierarchical reports.

Next, move on to the :doc:`rendering` guide to learn how to convert templates and items
into final HTML reports for presentation or web serving.
