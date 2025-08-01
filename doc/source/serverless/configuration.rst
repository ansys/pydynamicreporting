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
=====================

.. warning::

   **Use of environment variables for Serverless ADR configuration is strongly discouraged.**
   Environment variables represent a legacy configuration method and can lead to hidden,
   hard-to-debug issues, security risks (such as leaking secrets), and inconsistent behavior
   especially in multi-instance or containerized deployments.

   It is highly recommended to use explicit constructor parameters and configuration files
   for all setup and runtime options instead.

Core Variables
--------------

- **CEI_NEXUS_TIMEZONE**
  Olson format timezone string for the server (e.g., ``America/New_York``).
  Used in formatting timestamps in reports.

- **CEI_NEXUS_LOCAL_DB_DIR**
  Filesystem path to the directory containing the SQLite database file(s).
  Alternative to configuring ``db_directory`` in code.

- **CEI_NEXUS_LOCAL_MEDIA_DIR**
  Path to the media directory for uploaded files such as images and animations.
  Alternative to ``media_directory`` parameter.

- **CEI_NEXUS_MEDIA_URL_PREFIX**
  URL prefix used to access media files remotely. Must start and end with a slash, e.g., ``/media/``.
  Corresponds to the ``media_url`` constructor parameter.

Database Connection Variables
-----------------------------

- **CEI_NEXUS_DB_ENGINE**
  Database engine. Defaults to SQLite.

- **CEI_NEXUS_DB_DATABASE_NAME**
  Name of the database to connect to. Defaults to ``nexus_database``.

- **CEI_NEXUS_DB_USER**
  Database username. Default is ``nexus``.

- **CEI_NEXUS_DB_PASSWORD**
  Password for the database user. Default is ``cei``.

- **CEI_NEXUS_DB_HOSTNAME**
  Database server hostname or IP address. Defaults to the path to the SQLite database file.

- **CEI_NEXUS_DB_PORT**
  Database server port number. Default is not set for SQLite.

Security Variables
------------------

- **CEI_NEXUS_SECRET_KEY**
  Django secret key used internally. If not provided, a built-in default key is used (not recommended for production).

Advanced / Optional Variables
-----------------------------

- **CEI_NEXUS_ENABLE_ACLS**
  Enables per-category Access Control Lists (ACLs). Experimental and not recommended for general use.

Usage Notes
-----------

- Constructor parameters take precedence over environment variables. If both are set, constructor values will be used.

- Always set secure secret keys in production environments to protect sensitive data. If you do not set a key, a default will be used.

Example: Setting environment variables in Linux shell:

.. code-block:: bash

   export CEI_NEXUS_LOCAL_DB_DIR="/var/data/adr_db"
   export CEI_NEXUS_LOCAL_MEDIA_DIR="/var/data/adr_media"
   export CEI_NEXUS_MEDIA_URL_PREFIX="/media/"
   export CEI_NEXUS_SECRET_KEY="a-very-secure-secret-key"

Example: Passing variables via ``opts`` parameter:

.. code-block:: python

   opts = {
       "CEI_NEXUS_LOCAL_DB_DIR": "/var/data/adr_db",
       "CEI_NEXUS_LOCAL_MEDIA_DIR": "/var/data/adr_media",
       "CEI_NEXUS_MEDIA_URL_PREFIX": "/media/",
       "CEI_NEXUS_SECRET_KEY": "a-very-secure-secret-key",
   }

   adr = ADR(ansys_installation="/opt/ansys", opts=opts)
   adr.setup()

**Note: Prefer constructor parameters for new projects. Environment variables remain supported primarily for legacy compatibility.**

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

Client-Side Interactions
--------

Serverless ADR also allows modifying the configuration setup from the client-side interactions using JavaScript. 

- Dark mode modification: Users can change the value of ``<html></html>`` element's attribute ``data-bs-theme`` to toggle between light/dark mode themes.

.. code-block:: javascript

    // toggle light mode (default)
    document.documentElement.setAttribute('data-bs-theme','light');

    // toggle dark mode
    document.documentElement.setAttribute('data-bs-theme','dark');
    

Troubleshooting
---------------

- **InvalidPath Error:** Verify all configured directories exist and are accessible.

- **ImproperlyConfiguredError:** Check database config dictionary and URL prefixes for correctness.

- **Docker Errors:** Ensure Docker daemon is running and image URLs are valid.

- **Static files not found:** Confirm ``collect_static=True`` was set during setup and that your web server serves the static directory correctly.

- **Media files missing:** Verify media upload paths and web server routing for the media URL.

Summary
-------

Proper configuration of Serverless ADR ensures seamless database connections, media management, and web serving of report assets.
Follow best practices for setup and environment initialization to avoid common issues.
