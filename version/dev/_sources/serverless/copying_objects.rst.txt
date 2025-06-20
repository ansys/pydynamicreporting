Copying Objects
==============

Serverless ADR supports copying collections of report objects—including **Items**, **Templates**, **Sessions**, and **Datasets**—from one database to another. This functionality facilitates data migration, backup, synchronization, or environment replication.

Copying ensures that GUIDs (unique identifiers) are preserved and that related Sessions and Datasets referenced by Items are copied as well to maintain data integrity.

Prerequisites
-------------

- Multiple database configurations must be set up in the ADR instance.
- The source and target databases must be properly configured and accessible.
- For objects referencing media files (e.g., images, animations), a valid media directory must be specified for the target database.
- Only top-level Templates (those without parents) can be copied; their children are copied recursively.

API Usage
---------

Use the ``copy_objects()`` method on an ADR instance:

.. code-block:: python

    count = adr.copy_objects(
        object_type=Item,  # Class of objects to copy (Item, Template, Session, Dataset)
        target_database="dest",  # Target database key
        query="A|i_tags|cont|project=wing_sim;",  # ADR query string to filter objects
        target_media_dir="/path/to/media",  # Required if copying Items with media in SQLite
        test=False,  # If True, only logs number of objects to be copied, no actual copy
    )
    print(f"Copied {count} objects.")

Parameters
----------

- ``object_type`` (`type`): The class of objects to copy. Must be a subclass of ``Item``, ``Template``, ``Session``, or ``Dataset``.
- ``target_database`` (`str`): The configured target database key.
- ``query`` (`str`, optional): ADR query string to select which objects to copy. Defaults to copying all.
- ``target_media_dir`` (`str` or `Path`, optional): Directory to copy media files to when copying Items.
- ``test`` (`bool`, optional): If True, no copying occurs; only the count of matching objects is returned.

Copying Logic Details
---------------------

1. **Validation**

   - Checks that ``object_type`` is valid.
   - Validates that both source ("default") and target databases exist in ADR's configuration.

2. **Querying Objects**

   - Uses the ADR query interface to fetch objects matching the query string.

3. **Handling Items**

   - Checks if any Items reference media files.
   - Determines the target media directory:
     - Uses provided ``target_media_dir`` if specified.
     - If using SQLite for the target DB, attempts to resolve the media directory adjacent to the DB.
     - Throws an exception if no suitable media directory can be determined.
   - For each Item, attempts to fetch or create the corresponding Session and Dataset in the target DB.
   - Updates Items to reference the copied Sessions and Datasets.

4. **Handling Templates**

   - Only copies top-level Templates.
   - Recursively copies child Templates preserving hierarchy and order.

5. **Handling Sessions and Datasets**

   - Copies queried Sessions or Datasets as-is.

6. **Test Mode**

   - If ``test=True``, logs and returns the number of objects that *would* be copied, without performing any write operations.

7. **Performing Copy**

   - Saves all copied objects to the target database.
   - Copies media files referenced by Items to the target media directory.
   - Rebuilds 3D geometry files if applicable.

Example: Copy Sessions

.. code-block:: python

    session_count = adr.copy_objects(
        object_type=Session,
        target_database="dest",
        query="A|s_tags|cont|dp=;",
    )
    print(f"Copied {session_count} sessions.")

Example: Copy Items with Media

.. code-block:: python

    item_count = adr.copy_objects(
        Item,
        target_database="dest",
        query="A|i_tags|cont|dp=dp227;",
        target_media_dir=r"C:\ansys\dest_db\media",
    )
    print(f"Copied {item_count} items with media.")

Example: Copy Top-Level Template and Its Children

.. code-block:: python

    template_count = adr.copy_objects(
        Template,
        target_database="dest",
        query="A|t_name|eq|Serverless Simulation Report;",
    )
    print(f"Copied {template_count} templates.")

Error Handling
--------------

- Raises ``TypeError`` if ``object_type`` is not a valid ADR model subclass.
- Raises ``ADRException`` if databases are misconfigured.
- Raises ``ADRException`` if attempting to copy non top-level Templates.
- Raises ``ADRException`` if ``target_media_dir`` is missing when required.
- Exceptions from saving or media copying are caught and re-raised as ``ADRException``.

Implementation Notes
--------------------

- The copying uses a deep copy of Template objects to preserve the hierarchy.
- For Items, Session and Dataset references are fetched or created in the target database to maintain links.
- Media files are copied using standard filesystem operations; ensure appropriate permissions.
- The method supports extensions for future support of source database selection (currently hardcoded to "default").

Best Practices
--------------

- Ensure the target database is properly configured and accessible before copying.
- Copy related sessions and datasets automatically by copying items or templates.
- Always use ``test=True`` initially to preview the number of objects to be copied.
- Ensure media directories have sufficient space and permissions.
- Use descriptive ADR query strings to limit copy scope.
- Avoid copying Templates with parents; copy only top-level templates to prevent hierarchy issues.
- Call ``adr.setup()`` before copying to ensure proper configuration.

Summary
-------

The ``copy_objects()`` method provides robust, automated transfer of ADR report content and metadata between databases, preserving references and media assets to support backup, migration, and distributed workflows.

Next Steps
----------

Learn how to manage unwanted data after copying with :doc:`deleting_objects`.
