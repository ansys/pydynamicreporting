Server Object
=============

report_remote_server.Server object
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This object serves to wrap the Ansys Dynamic Reporting REST API.
It sets up a connection
to an ADR Nexus server and allows objects to be pulled from and pushed to the
server.

A new server object can be created with the following:

**serverobj = report_remote_server.Server(url=None, username=None, password=None)**

Methods
^^^^^^^

**serverobj.set_URL("http://localhost:8000")**
**serverobj.set_username("nexus")**
**serverobj.set_password("cei")**

Specify the ADR Nexus server (url and authentication information) to which
to connect the Server object to.

**url = serverobj.get_URL()**
**username = serverobj.get_username()**
**password = serverobj.get_password()**

Retrieve information about the current Server configuration.

**server_name = serverobj.get_server_name()**

Attempts to connect to the database returns the name of the server. For
remote servers, the name is a configuration parameter. For local
servers, it is the name of the directory that contains the SQLite file.
Note: if a connection to the server cannot be made or the server does
not support names, this method returns the URL for the server.

**server_version_float = serverobj.validate()**

Attempts to connect to the database and verifies that the server
connection specifications are valid. It returns the version of the
ADR Nexus
server API that the server is using. Note: this method will throw an
exception on encountering an error.

**has_database_url = serverobj.valid_database()**

This method checks to see if a database url has been set. It returns
True if a url has been set. It does not verify that the connection and
username, password is valid.

**serverobj.stop_local_server()**

This method will stop any local ADR Nexus server accessible via the current
Server object URL, username and password.

**guid_list = serverobj.get_object_guids(objtype=type_class, query=None)**

This method will query the server and returns a list of the object GUIDs
that meet the specific query. If the query is
None, all of the GUIDs of the type specified by objtype will be
returned. The objtype keyword specifies the type of database object to
get the list of guids for. Valid values for the objtype keyword include:

-  report_objects.DatasetREST
-  report_objects.SessionREST
-  report_objects.ItemREST

**obj_list = serverobj.get_objects(objtype=type_class, query=None)**

This method is similar to **get_object_guids()** except that it
returns a list of actual instances of the class specified by the
objtype keyword instead of just returning the GUIDs.

Note that if you want the list of templates, you can either set
**objtype** to **report_objects.TempalteREST** or to
**report.objects.TemplateREST.factory**. In the first case, all the
templates will be returned as objects of the TemplateREST class. In
the second case, all templates will be returned as objects of the
sub-classes of TemplateREST, corresponding to the exact report_type.

**obj = serverobj.get_object_from_guid(guid, objtype=type_class)**

This method queries the ADR Nexus server for a single object of the class
specified by objtype with the GUID specified by the guid argument. It
returns an instance of the class specified by objtype or None if the
GUID is not present.

**status_code = serverobj.put_objects(objects)**

This method takes a collection of objects of the classes
report_objects.DatasetREST, report_objects.SessionREST and
report_objects.ItemREST and pushes the local contents of the objects to
the server. If objects with the same GUID(s) already exist in the server
database, they will be overwritten. The return value is a status code
from the **requests** Python module (e.g. **requests.codes.ok**). Note:
if an error occurs the method will return the last error, but it will
try to push every object in the input collection.

**status_code = serverobj.del_objects(objects)**

This method takes a collection of objects of the classes
report_objects.DatasetREST, report_objects.SessionREST and
report_objects.ItemREST and asks the server to delete them. If objects
with matching GUIDs exist in the server database, they will be removed
from the database. This method only looks at the guid attribute of the
input object collection. The return value is a status code from the
**requests** Python module (e.g. **requests.codes.ok**). Note: if an
error occurs the method will return the last error, but it will try to
delete every object in the input collection.

**status_code = serverobj.get_file(object, fileobj)**

In some cases, a report_objects.ItemREST instance will have an
associated file in the Ansys Dynamic Reporting datastore.
Examples include images,
animations and 3D geometry (see report_objects.ItemRest above). The
ItemREST.is_file_protocol() can be used to check for this. This method
will download the file (if any) associated with the (ItemREST instance)
object and write the output into the file object specified by the
fileobj argument. Fileobj should be an open Python file type object that
supports minimally write I/O semantics. Note that the operation is
streaming, so it is possible for a partial file to exist if errors are
encountered. The return value is a status code from the **requests**
Python module (e.g. **requests.codes.ok**).

**session = serverobj.get_default_session()**
**dataset = serverobj.get_default_dataset()**
**serverobj.set_default_session(session)**
**serverobj.set_default_dataset(dataset)**

The server object maintains default SessionREST and DatasetREST objects
that are used with the create_item() method to simplify data item
creation. The get_default_session() and get_default_dataset() methods
return the current default session and dataset objects. The
corresponding set_default_session() and set_default_dataset() methods
set these objects to externally generated objects or more commonly,
modified objects returned by the get methods.

**item = serverobj.create_item(name="Unnamed Item", source="ADR Python
API", sequence=0)**

This method simplifies the generation of data items. One can create a
new data item by simply instantiating an instance of ItemREST(), but
many of the item attributes would need to be configured properly before
the object can be saved into the database. Most notably, the
item.session and item.dataset attributes need to be set to the GUIDs for
an instance of SessionREST and DatasetREST respectively. The Server
object always maintains a default instance of SessionREST and
DatasetREST objects. The object references can be modified by the user
to customize their metadata. The create_item() method will create a new
instance of the ItemREST class and will automatically fill in the
session and dataset attributes to the objects returned by
get_default_session() and get_default_dataset(). Additionally, if
put_objects() is called on an item whose session or dataset attributes
match the default GUIDs, the put_objects() method will push the session
and/or dataset objects as needed. If the session/dataset objects change
(without changing the GUIDs) the system will detect this any
automatically push them when the next item is pushed that references one
of them. The create_item() method allows the user to specify the name,
source and sequence number for the item during creation.

**serverobj.export_report_as_html(report_guid, directory_name,
query=None)**

This method exports the Ansys Dynamic Reporting report with the
GUID specified by the
argument "report_guid". The result will be written into the directory
specified by the argument "directory_name". The method will create the
directory if it does not exist previously. There will be a file named
"index.html" in the directory and a "media" subdirectory containing the
resources needed to display the report. note: if there is an error, this
method will throw an exception.

Input arguments:

-  report guid (string) - the guid of the report to be downloaded as
   HTML.
-  directory_name (string) - the name of the directory to save the
   downloaded contents.
-  query (dictionary) - a dictionary of query parameters to add to the
   report URL.

**serverobj.export_report_as_pdf(report_guid, file_name, delay=5000)**

Save a PDF rendering of the Ansys Dynamic Reporting report with the GUID specified by the
argument "report_guid". The name of the PDF file is specified by the
argument "file_name". Note: if there is an error, this method will throw
an exception. This is the equivalent of displaying the report with the
query 'print=pdf' included in the report URL.

Input arguments:

-  report guid (string) - the guid of the report to be saved as PDF.
-  file_name (string) - the name of the target PDF file.
-  delay (int) - number of milliseconds to wait for the report to load
   before downloading it. Default is 5000ms. Optional.

Various data items and report templates will behave differently when
printing:

#. Tree data items will be fully expanded and the interactive buttons
   for expanding/collapsing will be removed.
#. Animation data items will be rendered as if the 'image_display'
   property is set to 1.
#. Table data items will have all of their interactive controls
   suppressed (e.g. sorting, searching, scrolling, pagination, etc)
#. Tab layouts will behave as if the 'inline_tabs' property is set to 1.
#. Panel layouts will behave as if the 'panel_template_toggle' property
   is set to 0.

Magic tokens
^^^^^^^^^^^^

Magic tokens is a new way for users in the ADR Nexus server
to login without using
their password. Ansys Dynamic Reporting
provides a Python API to generate a per-user
secret token. This token can then be attached to any Ansys Dynamic Reporting web page URL
to bypass login during future access. This is currently restricted to
only the user who starts the server. This can be useful if a URL needs
to be reused within a HTML iframe.

**serverobj.generate_magic_token(max_age=None)**

This method generates a magic token with the desired expiry.

Input arguments:

-  max_age (int) - Expiry of the token in seconds. If this is None, the
   server will use its default expiry of 1 day.

**serverobj.get_url_with_magic_token()**

This will return a URL to access the ADR Nexus server with a magic token
attached.

Usage:

.. code-block:: python

   from ansys.dynamicreporting.core.utils import report_remote_server, report_objects

   server = report_remote_server.Server()
   opts = {
       "port": 8000,
       "directory": "C:\\Users\\Nexus\\db",
       "raise_exception": True,
       "connect": server,
   }
   launched = report_remote_server.launch_local_database_server(None, opts)
   if launched:
       print(server.magic_token)  # auto generation.. default expiry of 1day
       print(server.get_url_with_magic_token())
       server.magic_token = server.generate_magic_token(
           max_age=60
       )  # manual generation, with an expiry of 60 seconds
       print(server.get_url_with_magic_token())
       # Prints URL with token.
       # Example: http://127.0.0.1:8000?magic_token=eyJ1c2VyX2lkIjozLCJtYXhfYWdlIjo4NjQwMCwidGltZXN0YW1wIjoiMW5QY1B5In0:1nPcPy:c3OZhMCVQQq_fXXzevQ47WHxYfbAZE5TI-GL0yBzIaw
       template = serverobj.create_template(
           name="New Template", parent=None, report_type="Layout:basic"
       )


Method on a report_remote_server.Server() object to create a new
report_object.TemplateREST object. You can pass as input:

-  name (string) - the name of the template
-  parent (template objects)- the parent template. If None, the new
   template will be a top level one
-  report_type (string) - sets the type of template. Each value of
   report_type corresponds to a different template type, and will
   generate an object from the corresponding template sub-class. See the
   table for the accepted values of report_type, the corresponding
   template type and Python API sub-class.

**error_string = serverobj.get_last_error()**

Several of the server methods return REST error codes: put_objects(),
del_objects(), get_file(), etc. When these methods error, they return
the specific REST error code. If the error in question was generated by
the ADR Nexus server, in addition to the error_code not being equal to
**requests.codes.ok**, the server may return a more detailed error
string. This string can be retrieved using the get_last_error() method.
An example of a data item with an item name exceeding:

.. code-block:: python

   from ansys.dynamicreporting.core.utils import report_remote_server, report_objects

   serverobj = report_remote_server.Server(
       url="http://localhost:8000", username="nexus", password="cei"
   )
   invalid_data_item_name = 100
   item = serverobj.create_item(invalid_data_item_name, "command line")
   item.set_payload_string("A simple text string")
   print(serverobj.put_objects(item))
   print(serverobj.get_last_error())


will output the following (note: **requests.codes.bad_request** == 400)
output noting that the "name" field exceeds the maximum field length:

**400**
**{"name":["Ensure this field has no more than 80 characters."]}**
