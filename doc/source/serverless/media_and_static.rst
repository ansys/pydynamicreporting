Media and Static Files
=====================

Serverless ADR manages two key asset categories essential for rich report presentation:

- **Media files**: User-uploaded or generated files such as images, animations, 3D models, and other payloads associated with Items.
- **Static files**: Framework assets including CSS, JavaScript, fonts, and icons required to render reports and web interfaces correctly.

This guide covers the storage, access, lifecycle, and best practices for managing these files in Serverless ADR.

Overview
--------

Media Files
~~~~~~~~~~~

Media files complement your report Items and can include:

- Images (PNG, JPG, TIFF)
- Animation videos (MP4)
- 3D models and scenes (STL, OBJ, AVZ)
- Generic user files

They are stored separately on disk in a **media directory** configured during ADR setup. Items reference media files by unique GUID-based filenames to avoid collisions and enable retrieval.

Static Files
~~~~~~~~~~~

Static files provide the frontend styling and interactivity needed for report visualization. They include:

- CSS files for layout and themes
- JavaScript libraries (e.g., Plotly support)
- Fonts and icons

Static files reside in a **static directory** and are served alongside media files, typically by a web server or via the framework’s static file handling.

Configuration
-------------

You configure media and static paths and URLs when instantiating and setting up the ADR object:

- ``media_directory``: Path on disk for media files storage.
- ``static_directory``: Path on disk for static assets.
- ``media_url``: URL prefix to access media files (default: ``/media/``).
- ``static_url``: URL prefix to access static files (default: ``/static/``).

Example configuration:

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
    adr.setup(collect_static=True)

File Storage and Access
-----------------------

- Media files are saved with unique names based on the Item GUID and type, e.g., ``<guid>_image.png``.
- Items with associated files use the ``FilePayloadMixin`` to manage file storage and retrieval.
- The media directory should be accessible by any server or process serving reports or web content.
- Static files are collected during setup if ``collect_static=True`` is passed to ``ADR.setup()``.
- Static files can be served by any compatible web server or via built-in mechanisms in web frameworks.
- Items without files do not consume media storage.

Managing Media Files in Items
-----------------------------

Several Item subclasses support file payloads using the ``FilePayloadMixin``:

- ``Image``
- ``Animation``
- ``Scene``
- ``File``

These classes provide convenient properties and methods:

- ``file_path``: Returns the absolute file path on disk for the Item’s media.
- ``has_file``: Boolean indicating if the media file exists.
- ``file_ext``: File extension of the media file.
- ``save()``: Saves both the database record and copies the media file to the media directory.
- ``delete()``: Deletes the database record and removes the associated media file.

Example: Creating and saving an Image Item with a file

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Image

    img_item = adr.create_item(
        Image,
        name="wing_profile",
        content="C:\\images\\wing_profile.png",
        tags="section=geometry",
    )
    img_item.save()

Working with Media Files Directly
--------------------------------

You can access media file paths from Items:

.. code-block:: python

    print(img_item.file_path)  # C:\ADR\db\media\<guid>_image.png

Check if the item has a file associated with it:

.. code-block:: python

    if img_item.has_file:
        print("Media file is available.")

Deleting Items cleans up media files automatically:

.. code-block:: python

    img_item.delete()  # Removes DB record and deletes the image file

Static Files Collection and Serving
-----------------------------------

- Static files are typically collected from ADR’s installed packages during setup by calling:

  ``adr.setup(collect_static=True)``
- This process copies necessary CSS, JS, fonts, and icons into the configured static directory.
- Static files must be served by your web server or framework to enable proper report rendering.
- The static URL prefix (e.g., ``/static/``) must correspond to your web server configuration.

In-Memory Mode and Temporary Files
----------------------------------

- When using ADR in in-memory mode (``in_memory=True``), media and static files are stored in temporary directories.
- These directories are automatically cleaned up when ADR closes, so media files do not persist beyond the session.
- This mode is useful for testing or transient report generation but not for production.

Best Practices
--------------

- Always explicitly configure media and static directories during ADR instantiation to avoid ambiguity.
- Ensure the media directory has sufficient disk space and correct read/write permissions.
- When serving reports on a web server, map the ``media_url`` and ``static_url`` to the correct directories.
- Use meaningful and consistent tags on Items to organize media assets logically.
- Avoid manually deleting or moving media files outside ADR to prevent broken links.

Troubleshooting
---------------

- **Media files missing:** Confirm media directory path is correct and files exist on disk.
- **Permission denied errors:** Verify file system permissions allow read/write by the ADR process and web server.
- **Static assets not loading:** Ensure static files were collected during setup and your web server serves the static directory correctly.
- **File corruption:** Re-upload or regenerate files; validate file types before saving.

Summary
-------

Effective media and static file management is critical for generating rich, interactive reports with Serverless ADR.
Proper setup, naming conventions, and lifecycle handling ensure seamless integration of visual and data assets in your reports.

Next Steps
----------

Explore the :doc:`embedding_reports` guide to learn how to embed Serverless ADR reports
within your own web applications or documentation portals.
