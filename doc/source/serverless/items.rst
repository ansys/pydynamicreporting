Items
=====

In Serverless ADR, **Items** are the fundamental content units that form the building blocks of your reports.
They encapsulate individual pieces of data or visual content, such as text, tables, images, animations, and files,
which you can organize, query, and render within report templates.

Core Concepts
-------------

- Items are fully fledged Python classes with type-specific validation and behavior.
- Each item must be associated with a **Session** and a **Dataset** to maintain provenance.
- Items support rich metadata through tags, ordering via sequence numbers, and source attribution.
- Valid content types and file formats are enforced to ensure data integrity.
- Common item types include:

  - `String`: Plain text content.
  - `HTML`: Valid HTML content, validated for proper structure.
  - `Table`: Two-dimensional numpy arrays representing tabular data, with additional metadata like labels and plot settings.
  - `Tree`: Hierarchical data represented as nested dictionaries with keys `key`, `name`, `value`, and optional `children`.
  - `Image`: Images in PNG, JPG, and enhanced TIFF formats, supporting embedded metadata.
  - `Animation`: Video files, typically MP4 format.
  - `Scene`: 3D scene files such as STL, PLY, AVZ, CSF, and related formats.
  - `File`: Generic files linked to your reports.

Creating Items
--------------

Create new items via the ADR instance’s `create_item()` method.
Items automatically link to the current default session and dataset unless specified explicitly.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import String, Table
    import numpy as np

    # Create a string item
    string_item = adr.create_item(
        String,
        name="summary",
        content="This simulation demonstrates fluid flow around a wing.",
        tags="section=summary project=wing_sim",
    )
    string_item.save()

    # Create a table item with data
    data = np.array([
        [0.0, 10.0, 101325.0],
        [0.5, 12.5, 101300.0],
        [1.0, 15.0, 101280.0],
    ], dtype="float")

    table_item = adr.create_item(
        Table,
        name="pressure_data",
        content=data,
        tags="section=data project=wing_sim",
    )
    # Set additional table metadata
    table_item.labels_row = ["Time (s)", "Velocity (m/s)", "Pressure (Pa)"]
    table_item.plot = "line"
    table_item.xaxis = "Time (s)"
    table_item.yaxis = ["Velocity (m/s)", "Pressure (Pa)"]
    table_item.save()

Item Properties and Metadata
----------------------------

Items support several useful properties and metadata fields:

- **name**: Unique identifier for the item within the dataset.
- **content**: The primary payload of the item, type-dependent.
- **tags**: A space-separated string of key or key=value tags for querying and filtering.
- **source**: String to track the data origin or generating process.
- **sequence**: Integer to order items in reports or presentations.
- **session** and **dataset**: Associations to link items to specific data contexts.

Working With File-Based Items
-----------------------------

Items like `Image`, `Animation`, `Scene`, and `File` accept file paths as content.
The files are validated for existence and allowed formats before being saved into the configured media directory.

Example: Creating and saving an image item

.. code-block:: python

    image_item = adr.create_item(
        Image,
        name="wing_profile",
        content="path/to/wing_profile.png",
        tags="section=images project=wing_sim",
    )
    image_item.save()

Rendering Items
---------------

Items can be rendered individually into HTML fragments using the `render()` method.
This HTML can then be embedded in reports or served directly.

.. code-block:: python

    html_fragment = string_item.render(context={})
    print(html_fragment)

Querying Items
--------------

You can query items using the ADR `query()` method with filters based on tags, names, types, and other metadata.

.. code-block:: python

    items = adr.query(
        query_type=String,
        query="A|i_tags|cont|project=wing_sim;A|i_name|cont|summary;"
    )

Lifecycle Notes
---------------

- Items must be associated with saved Sessions and Datasets before calling `save()`.
- Modifying an item’s content or metadata requires calling `save()` again to persist changes.
- Deleting an item removes it from the database and deletes associated media files, if any.
- Proper session and dataset management is critical to maintain report integrity and provenance.
- Validation errors are raised if content does not meet item-specific requirements.

Exceptions and Validation
-------------------------

- Attempting to create or save items without required fields or with invalid content raises validation errors.
- File-based items validate file existence and format before saving.
- Fetching or querying non-existent items raises a `DoesNotExist` exception.
- Multiple items matching a single fetch criteria raise a `MultipleObjectsReturned` exception.

Summary
-------

Items encapsulate the actual data and content in your reports. Understanding item types, content validation, and lifecycle management is essential for effective Serverless ADR usage.

Next, explore the :doc:`templates` guide to learn how to arrange items into complex, reusable report layouts.
