"""
.. _ref_tag_items:

What are "tags" for?
====================

When working with a items you can set, add, and remove tags on them.

The system of tagging is how the Ansys Dynamic Reporting service knows
where to put items into your reports. Filters can be applied later to
select the relevant tags for a specific section of the report. Items are
fetched from the database based on the tags they have associated with them.

.. note::
   This example assumes that you have a local Ansys installation.

Initially we must create and start a session, as per other examples.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
#
# Start an Ansys Dynamic Reporting service on a new
# database. The path for the database directory must be to an empty directory.
#

import ansys.dynamicreporting.core as adr

db_dir = "C:\\tmp\\my_local_db_directory"
ansys_ins = "C:\\Program Files\\Ansys Inc\\v241"
adr_service = adr.Service(ansys_installation=ansys_ins, db_directory=db_dir)
session_guid = adr_service.start(create_db=True)


###############################################################################
# Create a text item
# ~~~~~~~~~~~~~~~~~~
# Text items are supplied as strings and can contain HTML instructions.
#

my_text = adr_service.create_item(obj_name="Text")
my_text.item_text = "<h1>Simple Title</h1>Abc..."

###############################################################################
# Adding tags
# ~~~~~~~~~~~
# Once you have an item tags can be set, added, or removed.
#

my_text.set_tags("tag1=one tag2=two tag3=three")

# Add or remove tags on an item
my_text.add_tag(tag="tag4", value="four")
my_text.rem_tag("tag1")

adr_service.stop()
