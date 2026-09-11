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

Integration Tips
----------------

- With the default linked output, make sure the static and media URLs configured
  during ADR setup are served by your web application.

- Use the ``context`` parameter to pass additional context variables
  needed for rendering.

- When embedding in frameworks with isolated DOM (e.g., React, Angular),
  be mindful of script execution and CSS scope.

Serving a Self-Contained Report
-------------------------------

Set ``embed_assets=True`` when the report endpoint should not depend on ADR
static or media routes. The renderer reads product static files from the Ansys
installation and embeds directly referenced dependencies in the returned HTML
string.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR
    from flask import Flask, Response

    adr = ADR(
        ansys_installation=r"C:\Program Files\ANSYS Inc\v271",
        db_directory=r"C:\Reports\DB",
    )
    adr.setup()

    app = Flask(__name__)


    @app.get("/report")
    def report():
        html = adr.render_report(name="My Simulation Report", embed_assets=True)
        return Response(html, mimetype="text/html")

This path does not require ``static_directory``, ``collect_static=True``, or
application routes for ADR static and media files. It also embeds scene data.
Remote resources supplied by templates or applications remain external.

The embedder does not replace or wrap ``fetch``, ``XMLHttpRequest``, or DOM
APIs. If viewer JavaScript still contains an ADR URL that it constructs at
runtime, such as a Draco decoder directory, ``render_report()`` raises
``ADRException`` during its unresolved-reference check. Use linked rendering
or the existing offline export pipeline for a report that requires those
runtime viewer loads.

The response contains inline scripts and styles plus ``data:`` resources. Set
the host application's Content Security Policy to allow the required inline
content and ``data:`` sources for the report endpoint. Viewer workers may also
require the policy already used by ADR viewer content.

Asset embedding increases the response size and transient memory use. The
returned string is intended to be served as an HTML response; it is not the
offline-export deliverable produced by ``export_report_as_html()`` or the
browser-PDF methods.

Serving Linked Content
----------------------

For the default ``embed_assets=False`` path, serve static and media files via a
web server or framework route pointing to ADR's configured directories.

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
