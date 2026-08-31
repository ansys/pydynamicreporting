Previewing Reports in a Web Server
==================================

Use :meth:`ADR.serve_report() <ansys.dynamicreporting.core.serverless.adr.ADR.serve_report>`
to open one serverless ADR report in a browser. The method starts a local web
server that provides three routes:

- ``/`` renders the selected report.
- The configured ``static_url`` serves files from ``static_directory``.
- The configured ``media_url`` serves files from ``media_directory``.

The report is rendered again on each page request, so refreshing the browser
shows changes saved to the ADR database while the server is running.

Collecting the Static Files
---------------------------

Configure a static directory and collect the ADR frontend files during setup:

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    adr = ADR(
        ansys_installation=r"C:\Program Files\ANSYS Inc\v261",
        db_directory=r"C:\ADR\DBs\preview",
        static_directory=r"C:\ADR\Static",
        static_url="/static/",
        media_url="/media/",
    )
    adr.setup(collect_static=True)

``serve_report()`` reads directly from the collected static directory. It
raises an error if ``static_directory`` was not configured.

Starting the Server
-------------------

After creating and saving the report, select it with the same lookup fields
accepted by ``render_report()``:

.. code-block:: python

    adr.serve_report(name="My Simulation Report")

The default URL is ``http://127.0.0.1:8000/``. The method opens that URL in the
default browser and blocks until you press ``Ctrl+C``.

Pass rendering options when the preview needs a filter or custom context:

.. code-block:: python

    adr.serve_report(
        name="My Simulation Report",
        context={"plotly": 1},
        item_filter="A|i_tags|cont|project=demo;",
        embed_scene_data=True,
    )

For a headless session, disable the browser launch and choose a different
local port if needed:

.. code-block:: python

    adr.serve_report(
        guid=report.guid,
        host="127.0.0.1",
        port=8123,
        open_browser=False,
    )

Development Use Only
--------------------

This server handles one request at a time and is intended for local previews,
examples, and debugging. It does not provide authentication, TLS, or the
hardening expected from a production web server. The default host binds only
to the local machine.

For a long-running application, call ``render_report()`` from the application's
request handler and configure that application or its front-end server to map
``static_url`` and ``media_url`` to the corresponding ADR directories. See
:doc:`embedding_reports` for the embedding pattern.
