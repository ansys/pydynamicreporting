Instantiation
=============

Serverless ADR supports several ways to instantiate the main ADR object depending on your use case.

Single SQLite Database (Recommended)
------------------------------------

This method creates or uses a local SQLite database directory.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    install_loc = r"C:\Program Files\ANSYS Inc\v252"
    db_dir = r"C:\ADR\DBs\ogdocex"

    adr = ADR(
        ansys_installation=install_loc,
        db_directory=db_dir,
    )
    adr.setup()

If the specified directory does not exist, it and a media subdirectory will be created automatically.

Multiple Databases
------------------

Use this method when working with multiple databases, e.g., PostgreSQL or database copies.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR
    import os

    install_loc = r"C:\Program Files\ANSYS Inc\v252"
    db_dir = r"C:\ADR\DBs\ogdocex"
    dest_dir = fr"{db_dir}_dest"

    database_config = {
        "default": {
            "ENGINE": "sqlite3",
            "NAME": os.path.join(db_dir, "db.sqlite3"),
            "USER": "nexus",
            "PASSWORD": "cei",
            "HOST": "",
            "PORT": "",
        },
        "dest": {
            "ENGINE": "sqlite3",
            "NAME": os.path.join(dest_dir, "db.sqlite3"),
            "USER": "nexus",
            "PASSWORD": "cei",
            "HOST": "",
            "PORT": "",
        },
    }

    adr = ADR(
        ansys_installation=install_loc,
        databases=database_config,
        media_directory=fr"{db_dir}\media",
    )
    adr.setup()

In-Memory Mode
--------------

Useful for testing and ephemeral workflows where persistence is not needed.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    adr = ADR(
        ansys_installation=r"C:\Program Files\ANSYS Inc\v252",
        in_memory=True,
    )
    adr.setup()

Note:

- No files are persisted to disk.
- Backup and restore operations are not supported.
- Media and static files use temporary memory locations.
- Data is lost when the process exits.

Docker-Based Instantiation
--------------------------

Use a Docker image to run ADR in containerized environments.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    adr = ADR(
        ansys_installation="docker",
        docker_image="ghcr.io/ansys-internal/nexus_dev",
        db_directory=db_dir,
        media_directory=fr"{db_dir}\media",
    )
    adr.setup()

Legacy Environment Variable Configuration
-----------------------------------------

Supported for backward compatibility but not recommended for new projects.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    opts = {
        "CEI_NEXUS_DEBUG": "0",
        "CEI_NEXUS_SECRET_KEY": "your_secret_key",
        "CEI_NEXUS_LOCAL_DB_DIR": r"C:\cygwin64\home\vrajendr\ogdocex",
    }

    install_loc = r"C:\Program Files\ANSYS Inc\v252"
    adr = ADR(ansys_installation=install_loc, opts=opts)
    adr.setup()

Important Notes
---------------

- Always call ``adr.setup()`` once per process before using other ADR APIs.
- In multi-threaded applications, a single call to ``setup()`` per process suffices.
- For multi-process scenarios, each process must call ``setup()`` independently.

For more usage examples, see the :doc:`examples` section.
