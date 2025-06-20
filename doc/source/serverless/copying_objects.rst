Copying Objects
==============

Serverless ADR allows you to copy collections of report objects between databases.
This is useful for migrating reports, backing up data, or synchronizing environments.

Supported Object Types
----------------------

You can copy the following object types:

- **Items**: Individual report content such as text, tables, images.
- **Templates**: Report layouts and generators defining report structure.
- **Sessions**: Contextual grouping of report data.
- **Datasets**: Collections of simulation or analysis data.

Copying ensures that related sessions and datasets are preserved and linked correctly.

Copying Workflow
----------------

To copy objects, use the ``copy_objects()`` method on the ADR instance:

.. code-block:: python

    count = adr.copy_objects(
        object_type=Item,
        target_database="remote_db",
        query="A|i_tags|cont|project=wing_sim;",
        target_media_dir="/path/to/media",
        test=False,
    )
    print(f"Copied {count} objects.")

Parameters:

- ``object_type``: The class of objects to copy (e.g., ``Item``, ``Template``).
- ``target_database``: The destination database key as configured in ADR.
- ``query``: An optional ADR query string to select which objects to copy.
- ``target_media_dir``: Directory to copy media files if objects reference files.
- ``test``: If True, only logs the number of objects to copy without performing the copy.

Copying Templates
-----------------

Only top-level templates (those with no parent) can be copied directly.
Child templates are recursively copied along with their parent to maintain hierarchy.

Handling Media Files
--------------------

When copying items with media files (e.g., images or geometry files), the
media files are copied to the specified target media directory.

You must specify ``target_media_dir`` if the target database uses SQLite or
does not provide media storage paths.

Error Handling
--------------

- Raises ``ADRException`` if unsupported object types are passed.
- Raises errors if the source or target database configurations are missing.
- Raises errors if media directory is missing when required.

Example Copying Items with Media

.. code-block:: python

    try:
        copied_count = adr.copy_objects(
            Item,
            target_database="remote_db",
            query="A|i_tags|cont|section=results;",
            target_media_dir="/data/remote/media",
        )
        print(f"Successfully copied {copied_count} items with media.")
    except ADRException as e:
        print(f"Copying failed: {e}")

Best Practices
--------------

- Ensure the target database is properly configured and accessible before copying.
- Verify that media directories have appropriate permissions for file copying.
- Use the ``test=True`` option initially to verify which objects will be copied.
- Copy related sessions and datasets automatically by copying items or templates.

Summary
-------

Copying objects in Serverless ADR is a powerful tool to migrate and synchronize
report content, preserving relationships and media assets across environments.

Next Steps
----------

Learn about :doc:`deleting_objects` to manage and clean up unwanted report data after copying.
