Embedding Reports
=================

Serverless ADR enables embedding fully rendered reports and report sections
into external web pages, dashboards, or applications. This allows you to
integrate dynamic ADR content seamlessly with other tools or UI frameworks.

Overview
--------

Embedding involves generating HTML output from templates and items, then
injecting or serving that content within another application or web page.

You can embed:

- Entire reports (top-level templates)
- Specific report sections or sub-templates
- Individual report items (e.g., tables, images, summaries)

Generating Embed-Ready HTML
---------------------------

Use the ``render_report()`` method of the ADR instance to render a complete
report.

.. code-block:: python

    html_report = adr.render_report(
        name="My Simulation Report",
        context={"plotly": 1},
        item_filter="A|i_tags|cont|project=my_project;",
    )

The resulting HTML string can then be inserted into your web page or
application container.

Embedding Individual Items
--------------------------

You can also render individual report items using their ``render()`` method:

.. code-block:: python

    item = adr.create_item(String, name="summary_text", content="Summary content here.")
    html_snippet = item.render(context={"plotly": 0})

Embedding Partial Templates or Sections
---------------------------------------

Templates can be rendered partially by applying specific item filters or by
rendering child templates individually:

.. code-block:: python

    partial_html = top_template.render(
        context={}, item_filter="A|i_tags|cont|section=results;"
    )

Displaying in Jupyter
---------------------

Items and templates can display their rendered HTML inline in a notebook:

.. code-block:: python

    string_item.visualize()
    top_template.visualize(item_filter="A|i_tags|cont|section=results;")

Use ``get_iframe()`` when you need the display object without showing it immediately.
The result is also string-like, so it can be embedded in another HTML host.

Integration Tips
----------------

- Make sure your embedded HTML includes references to static and media URLs
  configured during ADR setup so that assets like images and stylesheets
  load correctly and your web server is configured to serve them.

- Use the ``context`` parameter to pass additional context variables
  needed for rendering.

- When embedding in frameworks with isolated DOM (e.g., React, Angular),
  be mindful of script execution and CSS scope.

Serving Embedded Content
------------------------

If embedding in a web app, serve static and media files via a web server or
framework static route pointing to ADR’s configured directories.

Example with Flask:

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR
    from flask import Flask, render_template_string

    app = Flask(__name__)


    @app.route("/embedded-report")
    def embedded_report():
        adr = ADR.get_instance()
        my_app_html = "<!-- Your app's HTML here -->"
        html = adr.render_report(name="My Simulation Report")
        return f"""
            <html>
                <head>
                    <title>Embedded Report</title>
                </head>
                <body>
                    {my_app_html}
                    <div class="report-content">
                        {html}
                    </div>
                </body>
            </html>
        """

Serving Installation-Backed Static Files
----------------------------------------

The following Flask example mounts ADR static files directly from the Ansys
installation instead of collecting them into ``static_directory``:

.. code-block:: python

    from functools import partial

    from ansys.dynamicreporting.core.serverless import ADR
    from flask import Flask, send_from_directory

    # Disable Flask's default /static/ route because ADR returns that required alias.
    app = Flask(__name__, static_folder=None)
    adr = ADR(
        ansys_installation=r"E:\Program Files\ANSYS Inc\ANSYS Student\v261",
        db_directory=r"C:\ADR\db",
        static_url="/adr-static/",
    )
    static_routes = adr.get_installation_static_routes()
    adr.setup()

    for route_index, (url_prefix, directory) in enumerate(static_routes.items()):
        app.add_url_rule(
            f"{url_prefix}<path:path>",
            endpoint=f"adr_installation_static_{route_index}",
            view_func=partial(send_from_directory, directory),
        )

``send_from_directory`` keeps the requested path inside its configured
directory. For production, review the framework or web server's MIME headers,
caching policy, access controls, and file-serving performance. The example
only mounts static files; the application must mount ``adr.media_url`` to
``adr.media_directory`` separately when the report contains media.

Security Considerations
-----------------------

- Validate and sanitize any dynamic input used in filters or templates
  to avoid injection attacks.
- Limit exposure of data by controlling which templates or items
  are accessible for embedding.

Summary
-------

Embedding reports with Serverless ADR offers a flexible way to integrate rich,
dynamic simulation reports into custom applications or portals without
running a full ADR backend server.

Next Steps
----------

See the :doc:`copying_objects` guide for details on copying report content
between databases or environments, which may be useful when preparing
reports for embedding in different contexts.
