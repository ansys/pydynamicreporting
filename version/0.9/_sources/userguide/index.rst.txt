User guide
##########

This section describes concepts that you need to know to use PyDynamicReporting.

API overview
------------

The PyDynamicReporting API has three main classes:

- ``Service``: Provides for starting and connecting to an Ansys Dynamic
  Reporting service. This class also provides for creating, querying, and
  deleting the database and for stopping an Ansys Dynamic ``Report`` service.
- ``Item``: Provides access to the items in the database and allows
  them to be modified.
- ``Report``: Provides access to and rendering of ``Report`` objects.

PyDynamicReporting supports creating and pushing these items into an Ansys
Dynamic Reporting service:

- Images
- Animations
- 3D Scenes (AVZ file format supported)
- Tables
- Trees
- Text (HTML and LaTeX file formats supported)
- Files (generic file formats supported)

This code connects to a running Ansys Dynamic Reporting service and
pushes an image item on a new session:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(
       url="my_machine:8010", username="MyUsername", password="MyPassword"
   )
   first_image = adr_service.create_item()
   first_image.item_image = "location\image\file.png"
   first_image.visualize()


A rendering of the image object is embedded in the current interpreter. You
can follow the same steps to create and visualize other types of items.

To get the URL corresponding to an item, use this attribute:

.. code:: python

   first_image.url()


Similarly, to get the iframe corresponding to an item, use this attribute:

.. code:: python

   first_image.get_iframe()


With the corresponding URL or iframe, you can embed the item visualization
into any other app.

.. note:: If you want to update an image, all you need to do is redefine
   the ``item_image`` attribute. The Ansys Dynamic Reporting database is
   automatically updated.

Visualize an Ansys Dynamic reporting item
-----------------------------------------

PyDynamicReporting provides two main ways to visualize an item. The first is
to visualize it standalone, as shown in the preceding code examples. The second
is to visualize it together with all the other items that are present in the
current Ansys Dynamic Reporting session.

Each time that you use the PyDnamicReporting
:func:`start<ansys.dynamicreporting.core.Service.start>` method to
start an Ansys Dynamic Reporting service or the
:func:`connect<ansys.dynamicreporting.core.Service.connect>` method
to connect to one, you are connected to a specific session. Each
session has its own GUID (globally unique identifier).

On the Ansys Dynamic Reporting object, you can execute the
:func:`visualize_report<ansys.dynamicreporting.core.Service.visualize_report>`
method to visualize all items that are present in the session.

The following code embeds a widget in the app that you are running
from. It shows that both items (image and text) have been created.

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(
       url="my_machine:8010", username="MyUsername", password="MyPassword"
   )
   first_image = adr_service.create_item()
   first_image.item_image = "location\image\file.png"
   first_text = adr_service.create_item()
   first_text.item_text = "<h1>My Title</h1>This is the first example"
   adr_service.visualize_report()


Connect to and query an existing Ansys Dynamic Reporting session
----------------------------------------------------------------

You can start an Ansys Dynamic Reporting session in one Python interpreter
and connect to it in a different interpreter or on a different machine by passing the
session GUID as the parameter in the :func:`connect<ansys.dynamicreporting.core.Service.connect>`
method.

This code starts an Ansys Dynamic Reporting session in the first interpreter:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v232",
       db_directory=r"D:\tmp\test_pydynamicreporting",
       port=8010,
   )
   _ = adr_service.start()
   session_guid = adr_service.session_guid


The session contains the GUID needed to connect to this session in a different
interpreter or on a different machine.

This GUID is then copied and pasted into another interpreter as shown in this code:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(url="http://localhost:8010", session=session_guid)


Once you are connected to the session, you can query its items:

.. code:: python

   all_items = adr_service.query()
   only_images = adr_service.query(filter="A|i_type|cont|image|")


The :func:`query<ansys.dynamicreporting.core.Service.query>` method takes
a filter input that allows you to select the items to return. The query
string follows the same structure as the queries described in
`Query Expressions <https://nexusdemo.ensight.com/docs/html/Nexus.html?QueryExpressions.html>`_
in the documentation for Ansys Dynamic Reporting.

To get a list of the existing report templates in the database, use the
:func:`get_list_reports<ansys.dynamicreporting.core.Service.get_list_reports>`
method:

.. code:: python

   all_reports = adr_service.get_list_reports()


To query the database for a specific report, use the
:func:`get_report<ansys.dynamicreporting.core.Service.get_report>`
method:

.. code:: python

   my_report = adr_service.get_report(report_name="My Top Report")
   my_report.visualize()


Backward compatibility with template generator scripts
------------------------------------------------------

The template editor in Ansys Dynamic Reporting contains a feature for exporting
a Python script to create report templates on the connected server with all their
settings and properties and push these report templates to a new server.
This script uses the low-level API for Ansys Dynamic Reporting, which preceded
PyDynamicReporting.

A legacy script starts with these lines of code:

.. code:: python

   import cei
   from template_editor import report_remote_server, report_objects

   server = report_remote_server.Server("http://127.0.0.1:9528", "nexus", "cei")


Following these lines are a series of commands that describe the template names and properties.

To convert a legacy script to a report template for PyDynamicReporting, replace the preceding
lines in the legacy script with these lines:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(url="http://localhost:8010")
   server = adr_
   service.serverobj


Everything else in the script remains the same.
