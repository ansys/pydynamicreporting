Dataset and Session Objects
===========================

.. _DatasetREST:

report_objects.DatasetREST object
---------------------------------

This object is a Python representation of an Ansys
Dynamic Reporting dataset object. When
this object is created, a GUID will automatically be generated for the
object.

Data members
^^^^^^^^^^^^

The following attributes are available on a DatasetREST object:

-  guid - string GUID. The default is str(uuid.uuid1())
-  tags - The user-defined tags string for this object. Multiple tags
   are space-separated.
-  filename - The filename portion of the dataset local path, a string
-  dirname - The directory name portion of the dataset local path, a
   string
-  format - The format of the dataset, a string
-  numparts - The number of parts in the dataset, an integer
-  numelements - The total number of elements in the dataset, an integer
   (a measure of the size of the dataset)

Methods
^^^^^^^

**dataset.set_tags(tagstring)**

Set the tags for the dataset to the passed string. Multiple tags are
space-separated.

**dataset.get_tags()**

Returns the tags string for this object. Multiple tags are
space-separated.

**dataset.add_tag(tag, value=None)**

Adds a tag to the current tag string. If no value is passed, the simple
tag string is added to the tags string. If a value is specified, a
string of the form tag=value will be added to the tag string.

**dataset.rem_tag(tag)**

Remove the tag (and any potential associated value) from the current tag
string.

.. _SessionREST:

report_objects.SessionREST object
---------------------------------

This object is a Python representation of an
Ansys Dynamic Reporting session object. When
this object is created, a GUID will automatically be generated for the
object and the date is set to the current time/date.


Data members
^^^^^^^^^^^^

The following attributes are available on a SessionREST object:

-  guid - string GUID. The default is ``str(uuid.uuid1())``
-  tags - The user defined tags string for this object. Multiple tags
   are space-separated.
-  date - The time & date of the creation of this object. The default
   is: ``datetime.datetime.now(pytz.utc)``
-  hostname - The name of the host system the session was run on, a
   string
-  version - The version of the application that was used to generate
   this session, a string
-  platform - The platform/OS on which the application generated this
   session, a string
-  application - The name of the application generating this session, a
   string


Methods
^^^^^^^

**session.set_tags(tagstring)**

Set the tags for the session to the passed string. Multiple tags are
space-separated.

**session.get_tags()**

Returns the tags string for this object. Multiple tags are
space-separated.

**session.add_tag(tag, value=None)**

Adds a tag to the current tag string. If no value is passed, the simple
tag string is added to the tags string. If a value is specified, a
string of the form tag=value will be added to the tag string.

**session.rem_tag(tag)**

Remove the tag (and any potential associated value) from the current tag
string.
