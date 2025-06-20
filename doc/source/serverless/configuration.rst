Configuration
=============

Serverless ADR requires proper configuration to initialize its environment, connect to databases,
manage media and static files, and control runtime behavior. This guide explains the key configuration
parameters, environment variables, and recommended setup practices.

Overview
--------

Configuration for Serverless ADR can be done through:

- Constructor parameters when instantiating the ``ADR`` class.
- Environment variables (legacy or advanced usage).
- Optional overrides during the ``setup()`` call.

Key Configuration Parameters
----------------------------

The primary configuration options for the ``ADR`` class constructor are:

- ``ansys_installation`` (str, optional):
  Path to the Ansys installation directory. Special value ``"docker"`` triggers Docker-based setup.
  Defaults to automatic detection if omitted.

- ``ansys_version`` (int, optional):
  Specify the Ansys version explicitly. If not provided, automatic detection attempts to determine it.

- ``db_directory`` (str, optional):
  Directory path for the SQLite database files. If omitted, must provide ``databases`` config or environment variable.

- ``databases`` (dict, optional):
  Dictionary specifying multiple database configurations (e.g., for PostgreSQL or multi-DB setups).
  Requires a ``"default"`` database entry.

- ``media_directory`` (str, optional):
  Directory path for media file storage (uploaded images, animations, etc.). Falls back to ``db_directory`` media subfolder if not set.

- ``static_directory`` (str, optional):
  Directory path where static files (CSS, JS) will be collected.

- ``media_url`` (str, optional):
  Relative URL prefix for serving media files. Must start and end with a forward slash (e.g., ``"/media/"``).

- ``static_url`` (str, optional):
  Relative URL prefix for serving static files. Must start and end with a forward slash (e.g., ``"/static/"``).

- ``debug`` (bool, optional):
  Enable or disable debug mode. Defaults to production mode if not set.

- ``opts`` (dict, optional):
  Dictionary of environment variables to inject into the process environment.

- ``logfile`` (str, optional):
  File path to write logs. If omitted, logs to console.

- ``docker_image`` (str, optional):
  Docker image URL to use when ``ansys_installation="docker"``. Defaults to official Nexus image.

- ``in_memory`` (bool, optional):
  Enables in-memory database and media storage for ephemeral or test usage.

Environment Variables
---------------------

Some legacy or advanced configurations are controlled via environment variables:

- ``CEI_NEXUS_LOCAL_DB_DIR``: Directory for database files (alternative to ``db_directory``).

- ``CEI_NEXUS_LOCAL_MEDIA_DIR``: Directory for media files (alternative to ``media_directory``).

- ``CEI_NEXUS_LOCAL_STATIC_DIR``: Directory for static files (alternative to ``static_directory``).

- ``CEI_NEXUS_DEBUG``: Set debug mode (``"1"`` for debug, ``"0"`` for production).

- ``CEI_NEXUS_SECRET_KEY``: Secret key used internally by the ADR system.

**Note:** Prefer constructor parameters for new projects. Environment variables remain supported primarily for legacy compatibility.

Best Practices
--------------

- **Call ``ADR.setup()`` once per process early in your application lifecycle.**
  This initializes environment, Django settings, and database migrations.

- **For multi-process setups (e.g., Gunicorn, multiprocessing), ensure each process calls ``setup()`` independently.**

- **Within a process, all threads share the ADR configuration after setup; calling ``setup()`` multiple times per process is disallowed.**

- **Configure ``media_url`` and ``static_url`` to match your web server routing to serve media and static content correctly.**

- **Use absolute paths for all directory configurations to avoid ambiguity.**

- **For Docker-based Ansys installations, provide a valid Docker image and ensure Docker is installed and running.**

Examples
--------

**Basic local SQLite setup with explicit directories:**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    adr = ADR(
        ansys_installation=r"C:\Program Files\ANSYS Inc\v252",
        db_directory=r"C:\Reports\DB",
        media_directory=r"C:\Reports\Media",
        static_directory=r"C:\Reports\Static",
        media_url="/media/",
        static_url="/static/",
        debug=True,
    )
    adr.setup(collect_static=True)

**Multi-database PostgreSQL and SQLite setup:**

.. code-block:: python

    database_config = {
        "default": {
            "ENGINE": "postgresql",
            "NAME": "adr_db",
            "USER": "adr_user",
            "PASSWORD": "password",
            "HOST": "localhost",
            "PORT": "5432",
        },
        "sqlite_local": {
            "ENGINE": "sqlite3",
            "NAME": r"C:\Reports\DB\local.sqlite3",
        },
    }

    adr = ADR(
        ansys_installation=r"/opt/ansys",
        databases=database_config,
        media_directory=r"/opt/reports/media",
        static_directory=r"/opt/reports/static",
        media_url="/media/",
        static_url="/static/",
    )
    adr.setup()

**Docker-based Ansys installation:**

.. code-block:: python

    adr = ADR(
        ansys_installation="docker",
        docker_image="ghcr.io/ansys-internal/nexus_dev",
        db_directory=r"C:\Reports\DB",
        media_directory=r"C:\Reports\Media",
        static_directory=r"C:\Reports\Static",
        media_url="/media/",
        static_url="/static/",
    )
    adr.setup()

Troubleshooting
---------------

- **InvalidPath Error:** Verify all configured directories exist and are accessible.

- **ImproperlyConfiguredError:** Check database config dictionary and URL prefixes for correctness.

- **Docker Errors:** Ensure Docker daemon is running and image URLs are valid.

- **Static files not found:** Confirm ``collect_static=True`` was set during setup and that your web server serves the static directory correctly.

- **Media files missing:** Verify media upload paths and web server routing for the media URL.

Summary
-------

Proper configuration of Serverless ADR ensures seamless database connections, media management, and web serving of report assets. Follow best practices for setup and environment initialization to avoid common issues.

Next Steps
----------

See the :doc:`setup` guide for detailed startup and initialization instructions.

See the :doc:`media_and_static` guide for managing static and media files in your reports.
