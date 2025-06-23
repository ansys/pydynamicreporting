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
report or a subset of it as HTML.

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
    item.save()

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

- Make sure your embedded HTML includes references to static and media URLs
  configured during ADR setup so that assets like images and stylesheets
  load correctly.

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

    from flask import Flask, render_template_string

    app = Flask(__name__)


    @app.route("/embedded-report")
    def embedded_report():
        from ansys.dynamicreporting.core.serverless import ADR

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
- Limit exposure of internal data by controlling which templates or items
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
