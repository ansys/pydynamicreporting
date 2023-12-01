Data Item Object
================

.. _ItemREST:

report_objects.ItemREST object
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This object is a Python representation of an Ansys Dynamic
Reporting data item object. When
this object is created, a GUID will automatically be generated for the
object and the date is set to the current time/date.

Data members
^^^^^^^^^^^^

The following attributes are available on an ItemREST object:

-  guid - string GUID. The default is ``str(uuid.uuid1())``
-  tags - The user-defined tags string for this object. Multiple tags
   are space-separated.
-  sequence - An integer sequence number that can be used for
   sorting/indexing in a report
-  date - The time & date of the creation of this object. The default
   is: ``datetime.datetime.now(pytz.utc)``
-  name - The name of the data object, a string
-  source - The source of the data object, a string
-  session - string GUID of a SessionREST object that already exists in
   the database
-  dataset - string GUID of a DatasetREST object that already exists in
   the database


Methods
^^^^^^^

**item.set_tags(tagstring)**

Set the tags for the item to the passed string. Multiple tags are
space-separated.

**item.get_tags()**

Returns the tags string for this object. Multiple tags are
space-separated.

**item.add_tag(tag, value=None)**

Adds a tag to the current tag string. If no value is passed, the simple
tag string is added to the tags string. If a value is specified, a
string of the form tag=value will be added to the tag string.

**item.rem_tag(tag)**

Remove the tag (and any potential associated value) from the current tag
string.

**has_file = item.is_file_protocol()**

This method returns True if the data item refers to an actual file on
the server. Currently the ItemRest.type values of ItemREST.type_img,
ItemREST.type_scn, ItemREST.type_anim and ItemREST.type_file all refer
to files.

Once all of the metadata attributes listed above are set, an actual data
payload needs to be set for the data item. There are convenience methods
to set the item type and fill in the payload data.

**content = item.get_payload_content()**

For Items that have been fetched using the Server object, this method
allows you to get the payload without having to manually decode the
payload data.

An example of the use of this method is shown below:

.. code-block:: python

   from ansys.dynamicreporting.core.utils import report_remote_server, report_objects

   serverobj = report_remote_server.Server("http://localhost:8000/", "nexus", "cei")
   obj_list = serverobj.get_objects(
       objtype=report_objects.ItemREST, query="A|i_type|cont|string;"
   )

   # Previously you had to do this to get the data of an item and then decode it to view human readable content

   # import pickle**
   # data = pickle.loads(obj_list[0].payloaddata)

   # This method gives you the human readable content directly (handles decoding internally.)
   data = obj_list[0].get_payload_content()


Animation Item
''''''''''''''

**item.set_payload_animation(mp4_filename)**

This method sets the item payload to an animation. The "mp4_filename"
argument should be the name of a .mp4 encoded video file. Note: the file
must exist on disk before this call is made and must stay on disk until
the item is pushed to the ADR Nexus server.

File Item
'''''''''

**item.set_payload_file(filename)**

This method sets the item payload to the content of an arbitrary file on
disk. The argument should be the name of a file to be uploaded. Note:
the file must exist on disk before this call is made and must stay on
disk until the item is pushed to the ADR Nexus server.

HTML Item
'''''''''

**item.set_payload_html(html_text)**

This will set the item payload to HTML formatted text.

Image Item
''''''''''

**item.set_payload_image(image)**

This method sets the item payload to an image. The argument can be one
of three things: the binary representation of a .png file on disk as a
string, a QImage object or an enve.image object. Examples are shown
below:

-  A string which is the binary data representation of the image. Note:
   this is the only format supported in a Python interpreter that lacks
   the PyQt and enve modules.

   .. code-block:: python

      with open("example.png", "rb") as fp:
          img = fp.read()
      item.set_payload_image(img)


-  A Qt QImage object instance

   .. code-block:: python

      from PyQt4 import QtGui

      img = QtGui.QImage("example.png")
      item.set_payload_image(img)


-  An enve image object instance

   .. code-block:: python

      import enve

      img = enve.image()
      if img.load("example.png") == 0:
          item.set_payload_image(img)


None Item
'''''''''

**item.set_payload_none()**

By default an item has no payload. This method will reset the item to
that state. It is legal to push an item without a data payload into the
server.

Scene Item
''''''''''

**item.set_payload_scene(filename)**

This method sets the item payload to the 3D geometry found in the passed
filename.  Supported geometry formats include: EnSight CSF, STL, PLY,
SCDOC and AVZ format files.

String Item
'''''''''''

**item.set_payload_string(string)**

This will set the item payload to an ASCII string.

Table Item
''''''''''

**item.set_payload_table(dictionary)**

This will set the item payload to be a table, the table being specified
in a dictionary. Minimally, the dictionary must contain a single numpy
array with the 'array' key. There are a few restrictions on this array.
First, it must be 2D. Second, the dtype of the array should be
numpy.float32, numpy.double or a string (dtype="\|S20").

Other table properties (e.g. row/column labels, text formatting, etc)
can also be set in this dictionary. A simple example:

.. code-block:: python

   import numpy

   d = dict(
       array=numpy.zeros((3, 2), numpy.double),
       rowlbls=["Row 1", "Row 2", "Row 3"],
       collbls=["Column A", "Column B"],
       title="Simple table",
   )
   item.set_payload_table(d)


If the external Python API is being used from within EnSight, it is also
possible to pass an ENS_PLOTTER object to the set_payload_table()
method. It will capture not only the data in the plots, but many of the
plotter attributes. One example might be:

.. code-block:: python

   plot = ensight.objs.core.PLOTS[0]  # get the first ENS_PLOTTER object
   item.set_payload_table(plot)


Many more table properties exist and can be set as the default values
for a table by setting same-named keys in the dictionary. The properties
are documented in the item properties section at `this`_ page.

.. _this: https://nexusdemo.ensight.com/docs/en/html/Nexus.html?TableItem.html

A short-cut APIs exists for a common case:

.. code-block:: python

   item.set_payload_table_values(array, rowlbls=None, collbls=None, title=None)


This is a shortcut for the following two lines of python:

.. code-block:: python

   d = dict(
       array=numpy.array(array, numpy.double),
       rowlbls=rowlbls,
       collbls=collbls,
       title=title,
   )
   item.set_payload_table(d)


Note this can be handy for cases like:

.. code-block:: python

   item.set_payload_table_values([[1, 2, 3], [4, 5, 6]])


where one does not want to work with numpy and prefers to pass lists of
lists. The core API will convert the list of lists into a 2D numpy array
for the caller.

It is possible to use a table of strings. To create a 2 row, 3 column
array of strings (up to 20 characters), one might use code like this:

.. code-block:: python

   import numpy

   array = numpy.array([["A", "B", "C"], [1, 2, 3]], dtype="\|S20")
   d = dict(
       array=array,
       rowlbls=["Row 1", "Row 2"],
       collbls=["Column A", "Column B", "Column C"],
       title="Simple ASCII table",
   )
   item.set_payload_table(d)


A numpy array of strings contains strings of all the same length. The
maximum length must be specified using the 'dtype=' named argument when
the array is created.

.. _TreeItemDetails:


Tree Item
'''''''''

**item.set_payload_tree(tree)**

A tree payload consists of a list of "entities". Each entity is a
dictionary with several required keys and potentially some optional
ones. The required dictionary keys are:

-  'name' - the text string that will be displayed in the tree view.
-  'key' - a simple text string that can be used to specify the type of
   the entity. This value can be used to enforce a schema on the
   entities. This value is not displayed.
-  'value' - the data item value for the entity. This can be the None
   object or an object of any of the following types: bool, int, float,
   str, datetime.datetime, uuid.UUID.

optional keys include:

-  'children' - this key can be set to another list of entities. These
   entities are 'children' of the entity with this key and their
   visibility is controlled by the visible state of this entity.
-  'state' - if present, this key hints the generation engine that this
   entity node (or the nodes below it) should be initially displayed
   expanded or collapsed. Valid values include the strings: "expanded",
   "collapsed", "collapseRecursive" and "expandRecursive".
-  'header' - this key may be set to a boolean and defaults to False. If
   it is present and set to True, the rendered row associated with this
   item will be displayed as bold text and with an enhanced bottom
   border line.

The following example includes examples of all of the various options:

.. code-block:: python

   import datetime
   import enve
   import uuid

   image_item = server.create_item(name="An Image", source="externalAPI", sequence=0)
   img = enve.image()
   if img.load("example.png") == 0:
       image_item.set_payload_image(img)

   leaves = list()
   for i in range(10):
       leaves.append(dict(key="leaves", name="Leaf {}".format(i), value=i))

   children = list()
   children.append(dict(key="child", name="Boolean example", value=True))
   children.append(dict(key="child", name="Integer example", value=10))
   children.append(dict(key="child", name="Float example", value=99.99))
   children.append(dict(key="child", name="Simple string", value="Hello world!!!"))
   children.append(
       dict(key="child", name="The current date", value=datetime.datetime.now())
   )

   # this entity will display the image item (or a link to it) created above
   children.append(
       dict(key="child", name="A data item guid", value=uuid.UUID(image_item.guid))
   )
   children.append(
       dict(
           key="child_parent",
           name="A child parent",
           value="Parents can have values",
           children=leaves,
           state="expanded",
       )
   )

   tree = list()
   tree.append(
       dict(key="root", name="Top Level", value=None, children=children, state="collapsed")
   )
   item = server.create_item(name="Tree List Example", source="externalAPI", sequence=0)
   item.set_payload_tree(tree)

