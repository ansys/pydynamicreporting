User guide
##########

This guide provides information regarding using ``pydynamicreporting``
and its constituent modules and components.

``pydynamicreporting`` basic overview
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
There are three main classes in the ``pydynamicreporting`` module: a Service,
an Item and a Report class. The Service class allows the user to start or
connect to an Ansys Dynamic Reporting service, create new
databases, query or delete them, and stop the Ansys Dynamic Reporting
service. The Item class gives access to
the items in the database and allows the user to modify them. Similarly, the Report
class gives the user access to Ansys Dynamic Reporting Report objects.

The types of items that can currently be created and pushed into an Ansys
Dynamic Reporting service via ``pydynamicreporting`` are:

- Image
- Animation
- 3D Scene (AVZ format supported)
- Table
- Tree
- Text (HTML and Latex formatting supported)
- File (generic file format)

For example, connect to a running Ansys Dynamic Reporting service and
push on a new session an image item. This can be achieved with
the following lines:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(
       url="my_machine:8010", username="MyUsername", password="MyPassword"
   )
   first_image = adr_service.create_item()
   first_image.item_image = "location\image\file.png"
   first_image.visualize()

A rendering of the image object is embedded in the current interpreter. The same
steps can be followed to create and visualize other item types.

The user can get access to the URL corresponding to the item via the attribute:

.. code:: python

   first_image.url()

and similarly, they can get the IFrame corresponding to the item with:

.. code:: python

   first_image.get_iframe()

which allows users to embed the item visualization into any other app.

Note that if the user wants to update the image, all they need to do is redefine the ``item_image``
attribute. The Ansys Dynamic Reporting database is automatically updated.

Visualizing an Ansys Dynamic Reporting item
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are two main routes to visualize an Item via the ``pydynamicreporting``
module. The first is to visualize it stand alone, as described in the preceding
section. The second is to visualize it together with all the other items that are currently
present in the current Ansys Dynamic Reporting session.

Each time the user connects to an Ansys Dynamic Reporting service via the
``pydynamicreporting`` methods (either the connect or the
start module), they are connected to a specific session. Each session can be identified by
a unique GUID. On the Ansys Dynamic Reporting object you can execute
the ``visualize_report`` call to visualize all
the items that are currently present in the session. So executing the following code:

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

results in an widget embedded in the app you are running from that shows both items
(image and text) that have been created.

Connect to an existing Ansys Dynamic Reporting session and query it
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The user can start an Ansys Dynamic Reporting session in one python interpreter,
and connect to it in a different interpreter or machine simply by passing the
session ``guid`` as the parameter in the connect method.

In the first python interpreter, type:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v232",
       db_directory=r"D:\tmp\test_pydynamicreporting",
       port=8010,
   )
   _ = adr_service.start()
   session_guid = adr_service.session_guid

The session contains the ``guid`` for the current session. Copy and paste it in the following
python interpreter

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(url="http://localhost:8010", session=session_guid)

Now that the user is connected to the session, they can query its Items

.. code:: python

   all_items = adr_service.query()
   only_images = adr_service.query(filter="A|i_type|cont|image|")

The query method takes a filter input that allows the user to select the Items to be
returned. The query string follows the same structure as the Ansys Dynamic
Reporting queries, as described in
`this page <https://nexusdemo.ensight.com/docs/html/Nexus.html?QueryExpressions.html>`_

The user can also query the database for existing report templates. Use the following method

.. code:: python

   all_reports = adr_service.get_list_reports()

to obtain a list of the names of the top-level reports contained in the database.
he user can also query the database for existing report templates. Use the following method

.. code:: python

   my_report = adr_service.get_report(report_name="My Top Report")
   my_report.visualize()

Backward compatibility with template generator scripts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Ansys Dynamic Reporting template editor contains a feature to export a python script to
create the report templates on the connected server with all their settings and properties,
and push them to a new server. This script uses the Ansys Dynamic Reporting low level API \
that was available before the ``pydynamicreporting`` module. To convert legacy scripts
that use this technique to the current ``pydynamicreporting`` module, follow these steps.

Legacy scripts start with the following:

.. code:: python

   import cei
   from template_editor import report_remote_server, report_objects

   server = report_remote_server.Server("http://127.0.0.1:9528", "nexus", "cei")

and then a series of commands that describe the template names and properties. Delete these first few lines and
replace them with:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(url="http://localhost:8010")
   server = adr_service.serverobj

Everything else in the script remains the same.
