"""
.. _ref_tagging:

Tagging
=======

Tagging is an important feature of Ansys Dynamic Reporting. Adding tags to items
allows the database to organize them and the templates to create reports in
a precise and effective manner. This example shows how to add, modify, query,
and delete tags on items.

.. note::

   This example assumes that you have a local Ansys installation.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
#
# Start an Ansys Dynamic Reporting service with a new database. The path for the
# database directory must be to an empty directory.

import ansys.dynamicreporting.core as adr

ansys_loc = r"C:\Program Files\ANSYS Inc\v232"
db_dir = r"C:\tmp\new_database"
adr_service = adr.Service(ansys_installation=ansys_loc, db_directory=db_dir)
session_guid = adr_service.start(create_db=True)

###############################################################################
# Create an item and tag it
# -------------------------
#
# Now that an Ansys Dynamic Reporting service is running on top of a new
# database, create an item and set some tags on it. Use the
# :func:`get_tags<ansys.dynamicreporting.core.Item.get_tags>` method to
# see the values of the tags.

my_text = adr_service.create_item()
my_text.item_text = "<h1>Analysis Title</h1>This is the first of many items"
my_text.set_tags("var=pressure time=0.34")
my_text.get_tags()

###############################################################################
# Modify the tags
# ---------------
#
# Once the tags have been set, you can add or delete to them. Use the
# :func:`get_tags<ansys.dynamicreporting.core.Item.get_tags>` method
# to verify that the new value of the tags is the expected ``var=pressure dp=3``.

my_text.add_tag(tag="dp", value="3")
my_text.rem_tag("time")
my_text.get_tags()


###############################################################################
# Query items based on tag values
# -------------------------------
#
# Add a couple of other items and tag them. Then, query the database
# for items that have a specific tag set on them. Given the preceding
# code, this results in only two items. See the contents of the ``dp3_items``
# list.

my_second_text = adr_service.create_item()
my_second_text.item_text = "<h1>Second Text</h1>Second text item"
my_second_text.set_tags("var=temperature dp=3")
my_thid_text = adr_service.create_item()
my_thid_text.item_text = "<h1>Third Text</h1>An other item"
my_thid_text.set_tags("var=temperature dp=2")
dp3_items = adr_service.query(filter="A|i_tags|cont|dp=3")

###############################################################################
# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the items that
# were created remains on disk.

# sphinx_gallery_thumbnail_path = '_static/default_thumb.png'
adr_service.stop()
