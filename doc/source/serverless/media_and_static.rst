Media and Static Files
=====================

Serverless ADR manages two important categories of assets that accompany your reports and items:

- **Media files**: User-uploaded or generated files such as images, animations, 3D models, and other payloads associated with Items.
- **Static files**: Framework assets like CSS, JavaScript, fonts, and icons needed to properly render reports and web interfaces.

This guide explains how media and static files are organized, accessed, and managed within Serverless ADR.

Overview
--------

### Media Files

Media files are stored separately from the database and linked to Items via file paths or URLs. Examples include:

- Images (PNG, JPG, TIFF)
- Animation videos (MP4)
- 3D scene files (STL, OBJ, AVZ)
- Arbitrary user files

These files reside in a configurable media directory, typically inside or alongside the database directory.

### Static Files

Static files contain the frontend resources required to render reports correctly. They include:

- CSS stylesheets for layout and theming
- JavaScript libraries for interactivity (e.g., Plotly support)
- Fonts and icons

Static files are collected and served from a configurable static directory.

Configuration
-------------

Both media and static directories can be set during ADR instantiation or setup via the following parameters:

- ``media_directory``: Path where media files are stored.
- ``static_directory``: Path where static files are stored.
- ``media_url``: URL prefix for accessing media files (usually ``/media/``).
- ``static_url``: URL prefix for static files (usually ``/static/``).

Example:

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    adr = ADR(
        ansys_installation="C:\\Program Files\\ANSYS Inc\\v252",
        db_directory="C:\\ADR\\db",
        media_directory="C:\\ADR\\db\\media",
        static_directory="C:\\ADR\\static",
        media_url="/media/",
        static_url="/static/",
    )
    adr.setup()

File Storage and Access
-----------------------

- Media files are saved with unique names based on the Item GUID and type, e.g., ``<guid>_image.png``.
- Items with associated files use the ``FilePayloadMixin`` to manage file storage and retrieval.
- The media directory should be accessible by any server or process serving reports or web content.
- Static files are collected during setup if ``collect_static=True`` is passed to ``ADR.setup()``.
- Static files can be served by any compatible web server or via built-in mechanisms in web frameworks.

Working with Media Files in Items
---------------------------------

Many Item subclasses support files, such as:

- ``Image``
- ``Animation``
- ``Scene``
- ``File``

They use the ``FilePayloadMixin``, which provides properties and methods like:

- ``file_path``: Absolute path to the stored file.
- ``has_file``: Boolean indicating if the file exists.
- ``file_ext``: File extension of the payload file.

Saving Items with Files:

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Image

    img_item = adr.create_item(
        Image,
        name="wing_profile",
        content="C:\\images\\wing_profile.png",
        tags="section=geometry",
    )
    img_item.save()

File Deletion and Cleanup
-------------------------

- When an Item with file payload is deleted, the corresponding media file is also removed from the media directory.
- Manual cleanup may be necessary if files are moved or corrupted outside ADR.

Best Practices
--------------

- Always configure media and static directories explicitly to avoid ambiguity.
- Ensure web servers serving reports have read access to media and static directories.
- Use unique tagging in Items to organize media assets logically.
- Use in-memory mode only for transient or test environments, as media files won’t persist.

Troubleshooting
---------------

- **Missing files**: Verify the media directory path is correct and files exist.
- **Permission errors**: Check filesystem permissions for read/write access.
- **Static files not loading**: Confirm static files were collected during setup and served correctly.
- **Corrupted media**: Re-upload or regenerate media files; ensure valid file types.

Summary
-------

Media and static file management is crucial for full-fidelity report rendering in Serverless ADR.
Proper configuration and handling ensure smooth integration of rich content into your reports.

Next Steps
----------

Proceed to the :doc:`embedding_reports` guide to learn how to embed Serverless ADR reports
within your own web applications or documentation portals.
