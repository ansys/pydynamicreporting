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

Serverless ADR supports several environment variables to configure its runtime behavior,
database connections, security settings, and media/static file handling. These variables
can be used for legacy configurations or advanced deployments.

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

- **CEI_NEXUS_LOCAL_ALLOW_REMOTE_ACCESS**
  If set to any value, allows remote access to a local database server (use cautiously).

- **CEI_NEXUS_SERVE_STATIC_FILES**
  If ``True``, enables Django’s built-in static and media file serving (not recommended for production).

Database Connection Variables
-----------------------------

- **CEI_NEXUS_DB_ENGINE**
  Database engine string (e.g., ``django.db.backends.postgresql_psycopg2``). Defaults to PostgreSQL.

- **CEI_NEXUS_DB_DATABASE_NAME**
  Name of the database to connect to. Defaults to ``nexus_database``.

- **CEI_NEXUS_DB_USER**
  Database username. Default is ``nexus``.

- **CEI_NEXUS_DB_PASSWORD**
  Password for the database user. Default is ``cei``.

- **CEI_NEXUS_DB_HOSTNAME**
  Database server hostname or IP address. Defaults to ``127.0.0.1``.

- **CEI_NEXUS_DB_PORT**
  Database server port number. Default is ``5432``.

Security and Server Variables
-----------------------------

- **CEI_NEXUS_SERVER_NAME**
  Human-readable name of the server. Defaults to ``mixed``.

- **CEI_NEXUS_SECRET_KEY**
  Django secret key used internally. If not provided, a built-in default key is used (not recommended for production).

- **CEI_NEXUS_ALLOWED_HOSTS**
  Comma-separated list of allowed hostnames for accessing the server (e.g., ``localhost,127.0.0.1``).

- **CEI_NEXUS_TRUSTED_ORIGINS**
  List of trusted origins for unsafe requests like POST, supporting wildcards (e.g., ``https://*.example.com``).

- **CEI_NEXUS_HTTPS_SECURED**
  Boolean flag to indicate if the server runs behind HTTPS only. Enables security headers.

- **CEI_NEXUS_HSTS_SECURED**
  Enables HTTP Strict Transport Security (HSTS) headers.

- **CEI_NEXUS_HSTS_SECONDS**
  Duration in seconds for HSTS policy enforcement. Use with caution to avoid locking out clients.

- **CEI_NEXUS_X_FRAME_OPTIONS**
  Sets the HTTP X-Frame-Options header globally for protection against clickjacking.

Advanced / Optional Variables
-----------------------------

- **CEI_NEXUS_ENABLE_ACLS**
  Enables per-category Access Control Lists (ACLs). Experimental and not recommended for general use.

- **CEI_NEXUS_ACLS_NGINX_LOCATION**
  NGINX internal location directive for permission-protected media files. Default is ``/media_secured``.

Remote Session Configuration
----------------------------

- **CEI_NEXUS_REMOTE_WEBSOCKETURL**
  URL to the NGINX server proxying to the websocket server.

- **CEI_NEXUS_REMOTE_WS_PORT**
  Port used by the websocket server for WS protocol communication.

- **CEI_NEXUS_REMOTE_HTML_PORT**
  Port used by the websocket server for HTTP REST communication.

- **CEI_NEXUS_REMOTE_VNCPASSWORD**
  Password for VNC server sessions.

Usage Notes
-----------

- When running a non-debug local server, use the following command to enable static file serving:

  .. code-block:: bash

     python manage.py runserver --insecure 0.0.0.0:8000

- Environment variables override constructor parameters if both are set.

- Always set secure secret keys in production environments to protect sensitive data.

- Configure ``CEI_NEXUS_ALLOWED_HOSTS`` and ``CEI_NEXUS_TRUSTED_ORIGINS`` to restrict server access.

- When enabling HTTPS and HSTS, be cautious with duration settings to avoid client lockout.

Example: Setting environment variables in Linux shell:

.. code-block:: bash

   export CEI_NEXUS_LOCAL_DB_DIR="/var/data/adr_db"
   export CEI_NEXUS_LOCAL_MEDIA_DIR="/var/data/adr_media"
   export CEI_NEXUS_MEDIA_URL_PREFIX="/media/"
   export CEI_NEXUS_SECRET_KEY="a-very-secure-secret-key"
   export CEI_NEXUS_ALLOWED_HOSTS="localhost,127.0.0.1"
   export CEI_NEXUS_HTTPS_SECURED="True"

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

Summary
-------

Proper use of environment variables allows flexible deployment and integration of Serverless ADR
into diverse environments, including containerized, cloud, or on-premises infrastructures.

See also the :doc:`configuration` and :doc:`setup` guides for comprehensive initialization instructions.

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
