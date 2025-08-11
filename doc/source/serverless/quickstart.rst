Quickstart
==========

Get started quickly with Serverless ADR using the most common setup: a local SQLite database.

Instantiation and Setup
-----------------------

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    install_loc = r"C:\Program Files\ANSYS Inc\v252"
    db_dir = r"C:\ADR\DBs\ogdocex"

    adr = ADR(
        ansys_installation=install_loc,
        db_directory=db_dir,
    )
    adr.setup()

Creating Items
--------------

Create report items such as text or tables tied to the default session and dataset.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import String

    item = adr.create_item(
        String,
        name="intro_text",
        content="This is a quickstart demo for Serverless ADR.",
        tags="section=intro",
        source="quickstart-example",
    )

Building Templates
------------------

Create a basic template to structure the report.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import BasicLayout

    template = adr.create_template(
        BasicLayout,
        name="Quickstart Report",
        parent=None,
        tags="section=quickstart",
    )
    template.set_filter("A|i_tags|cont|section=intro;")
    template.save()

Loading Templates from a JSON file
----------------------------------

You can load a report with multiple templates from an existing JSON file.

.. code-block:: python

    adr.load_templates_from_file("my_report.json")

Rendering the Report
--------------------

Render the report template to HTML, filtering items as needed.

.. code-block:: python

    html_content = adr.render_report(
        name="Quickstart Report",
        context={},
        item_filter="A|i_tags|cont|section=intro;",
    )

    # Save to file or use the HTML content in your application
    with open("quickstart_report.html", "w", encoding="utf-8") as f:
        f.write(html_content)

Accessing the ADR Instance
--------------------------

Retrieve the active ADR instance anywhere in your code:

.. code-block:: python

    adr = ADR.get_instance()

For more detailed setup options and concepts, see the :doc:`overview` and :doc:`instantiation` guides.
