Templates
=========

Templates in Serverless ADR define the **layout**, **organization**, and **presentation**
of your report content. They control how Items are arranged, filtered, and rendered
within a report, enabling flexible, reusable, and dynamic reporting structures.
The represent report layouts or data generators that organize and present report items.

Overview
--------

Templates are Python classes derived from the base ``Template`` model. They come in two main flavors:

- **Layouts**: Define static or semi-static page structures (e.g., panels, tabs, carousels).
- **Generators**: Automate dynamic content generation by iterating, merging, filtering, or sorting Items.

Templates can be nested hierarchically to form complex reports with multiple sections and subsections.

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

Parent-child relationships can be established by passing a ``parent``
template during creation or by appending to ``parent.children`` and saving both.

Template Types
--------------

Common layout types include:

- BasicLayout
- PanelLayout
- BoxLayout
- TabLayout
- CarouselLayout
- SliderLayout
- FooterLayout
- HeaderLayout
- IteratorLayout
- TagPropertyLayout
- TOCLayout
- ReportLinkLayout
- PPTXLayout
- PPTXSlideLayout
- DataFilterLayout
- UserDefinedLayout

Generator types include:

- TableMergeGenerator
- TableReduceGenerator
- TableMergeRCFilterGenerator
- TableMergeValueFilterGenerator
- TableSortFilterGenerator
- TreeMergeGenerator
- SQLQueryGenerator
- ItemsComparisonGenerator
- StatisticalGenerator
- IteratorGenerator

Template Attributes and Methods
-------------------------------

Templates have several important properties and methods:

- ``guid``: Unique identifier for the template.
- ``name``: The template’s unique name.
- ``date``: The date when the template was created.
- ``tags``: A string of tags for categorization and filtering.
- ``params``: JSON-encoded string storing rendering parameters and properties.
- ``item_filter``: Query string filter to select items included in this template.
- ``parent``: Reference to the parent template or None for root templates.
- ``children``: List of child templates for hierarchical organization.
- ``report_type``: String representing the template’s layout or generator type.

Common methods include:

- ``set_filter(filter_str)``: Replace the item filter string.
- ``add_filter(filter_str)``: Append to the existing item filter.
- ``get_params()``: Return parsed parameters as a dictionary.
- ``set_params(params_dict)``: Set parameters, replacing existing ones.
- ``add_params(params_dict)``: Add or update parameters without overwriting others.
- ``get_property()``: Shortcut to get the “properties” sub-dictionary from parameters.
- ``set_property(props_dict)``: Replace the “properties” dictionary.
- ``add_property(props_dict)``: Add/update keys within the “properties” dictionary.
- ``render(context=None, item_filter="", request=None)``: Render the template to HTML string.
- ``to_dict()``: Returns a JSON-serializable dictionary of the full template tree.
- ``to_json(filename)``: Store the template as a JSON file. Only allow this action if this template is a root template.
- ``reorder_child(target_child_template, new_position_index)``: Reorder the target template in the `children` list to the specified position.

Template Parameters
-------------------

Each template stores configuration and state in its ``params`` field, a JSON string representing:

- HTML header (e.g., ``"HTML"``)
- Layout-specific options (e.g., column counts, widths)
- Filter parameters and modes controlling which Items are included
- Sorting options (fields, order, selection)
- Other custom properties for configuration and behavior

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

Template Properties
-------------------

Templates support a flexible set of properties stored within the ``params`` JSON field.
These properties allow you to control fine-grained behavior of layouts and generators
and customize rendering without subclassing.

Common Properties
~~~~~~~~~~~~~~~~~

- **column_count** (layouts only)
  Number of columns in multi-column layouts.

- **column_widths** (layouts only)
  List of floats defining relative widths of columns, e.g., ``[1.0, 2.0, 1.0]``.

- **transpose** (layouts only)
  Integer flag (0 or 1) to indicate whether tabular content should be transposed.

- **skip_empty** (layouts only)
  Integer flag (0 or 1) to skip rendering empty items or not.

- **sort_fields**
  List of fields by which to sort included items.

- **sort_selection**
  Determines which items to select after sorting. Allowed values:
  ``"all"``, ``"first"``, ``"last"``.

- **filter_type**
  Controls filter application mode. Options include:
  ``"items"``, ``"root_replace"``, ``"root_append"``.

  ... and many more depending on the specific layout or generator.

Adding and Modifying Properties
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use the following methods on a template instance to interact with properties:

.. code-block:: python

    # Get all properties dictionary
    props = template.get_property()

    # Set all properties at once (replaces existing)
    template.set_property({"column_count": 3, "skip_empty": 1})

    # Add or update specific properties without overwriting others
    template.add_property({"column_count": 2})

Direct Attribute Access
~~~~~~~~~~~~~~~~~~~~~~~

Alternatively, some common properties can also be accessed or set using standard attribute
syntax on the template instance. For example:

.. code-block:: python

    # Set a property using attribute assignment
    pptx_template.use_all_slides = 0

    # Get a property value via attribute access
    output_pptx = pptx_template.output_pptx

You can also use Python’s built-in ``setattr()`` function to set properties dynamically:

.. code-block:: python

    setattr(template, "output_pptx", "report.pptx")

Note that attribute access is a convenient shortcut for common properties.
Under the hood, these are proxied to the underlying JSON ``params`` data.

Examples
~~~~~~~~

.. code-block:: python

    # Set multiple properties at creation
    layout = adr.create_template(
        BasicLayout,
        name="Summary Section",
        tags="section=summary",
    )
    layout.set_property(
        {
            "column_count": 2,
            "column_widths": [1.0, 1.5],
            "skip_empty": 1,
        }
    )
    layout.save()

    # Update an existing property
    layout.add_property({"comments": "Updated to include additional charts"})
    layout.save()

Notes
~~~~~

- Properties are stored as JSON under ``params`` → ``properties``.
- They provide a flexible way to extend template capabilities without subclassing.
- Some specialized layouts and generators may define their own additional properties accessible through their own APIs.

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

Working with Template Hierarchies
---------------------------------

Templates can be organized in parent-child relationships to structure complex reports.

- Use the ``parent`` argument to specify a template’s parent during creation.
- The ``children`` list contains all direct child templates.
- The ``children_order`` property stores the ordered GUIDs of children for rendering order.
- The ``reorder_children()`` method will reorder the ``children`` list based on the stored order.

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

Rendering Templates
-------------------

Templates can render themselves into complete HTML content using the ``render()`` method.

.. code-block:: python

    html_report = top_template.render(
        context={}, item_filter="A|i_tags|cont|project=wing_sim;"
    )
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html_report)

This method generates the full HTML output, including all nested templates and items,
and applies any specified filters. The ``context`` parameter can be used to pass additional
data for rendering, such as user-defined variables or configuration settings.

Rendering context supports options like:

- Page dimensions and DPI for layout calculations
- Date and time formatting

- If rendering fails, the output HTML will contain an error message for easier debugging.

- If you would like more information on the error, set the ``debug`` flag to ``True`` when instantiating
  the ``ADR`` class.

Rendering via the ADR Entry Point
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ADR singleton class provides convenient methods to render templates by name or other filters,
abstracting the fetching and rendering process:

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    adr = ADR.get_instance()

    # Render an HTML report by name with optional context and item filtering
    html_content = adr.render_report(
        name="Serverless Simulation Report",
        context={"key": "value"},
        item_filter="A|i_tags|cont|project=wing_sim;",
    )
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html_content)

The ``render_report()`` method:

- Requires at least one keyword argument to identify the template (e.g., ``name``, ``guid``).
- Passes the ``context`` and ``item_filter`` to the template's ``render()`` method.
- Raises ``ADRException`` on failure with descriptive error messages.

Rendering to PPTX
-----------------

You can render a PowerPoint (.pptx) file from templates of type ``PPTXLayout`` using either the template’s
``render_pptx()`` method or through the ADR singleton’s ``render_report_as_pptx()`` helper.

Example using the template method:

.. code-block:: python

    pptx_bytes = pptx_template.render_pptx(
        context={"key": "value"}, item_filter="A|i_tags|cont|project=wing_sim;"
    )
    with open("report.pptx", "wb") as f:
        f.write(pptx_bytes)

Example using the ADR entrypoint:

.. code-block:: python

    pptx_bytes = adr.render_report_as_pptx(
        name="Serverless Simulation Report",
        context={"key": "value"},
        item_filter="A|i_tags|cont|project=wing_sim;",
    )
    with open("report.pptx", "wb") as f:
        f.write(pptx_bytes)

Notes on ``render_report_as_pptx()`` method:

- The template identified by the filter (e.g., ``name``) must be of type ``PPTXLayout``.
- Raises an ``ADRException`` if the template is not found or not of the required type.
- Returns raw bytes of the generated PPTX presentation.
- Passes ``context`` and ``item_filter`` to the template’s ``render_pptx()`` method.
- Exceptions during rendering are wrapped and raised as ``ADRException``.

Lifecycle Notes
---------------

- Templates must be saved to persist changes.
- Parent templates must be saved before saving children.
- Deleting a template typically requires handling or deleting its children to avoid orphaned templates.

Exceptions and Validation
-------------------------

- Creating or fetching templates with missing or invalid fields raises validation errors.
- Attempting to instantiate the base ``Template`` class directly raises an error.
- Filters using keys mentioning the type (like ``t_types|``) are disallowed on subclasses.
- Invalid parent references or child types will raise type or integrity errors during saving.
- Only top-level templates (parent=None) can be copied between databases.
- Templates must have their parents and children saved before saving themselves to ensure integrity.
- Invalid property types or malformed filters raise errors.
- Fetching non-existent templates raises ``DoesNotExist`` errors.
- Using invalid filter keys in subclasses raises ``ADRException``.

Summary
-------

Templates are the backbone of report structure in Serverless ADR. They let you create
rich, dynamic, and highly customizable reports by defining layouts and generators,
setting filters and parameters, and nesting templates to build complex hierarchical reports.

Rendering can be done directly via template instances or conveniently through the ADR singleton instance.

- Use ``template.render()`` for HTML output.
- Use ``template.render_pptx()`` or ``adr.render_report_as_pptx()`` for PPTX output.
- Both rendering paths support passing context and filtering items if applicable.
- Handle exceptions raised as ``ADRException`` to debug issues.
