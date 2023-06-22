"""
.. _ref_queries_example:

Item Queries
============

The Ansys Dynamic Reporting database can contain any number of items - from a few to tens of thousands.
To handle all this data, a query method is provided, that allows to quickly slice
the database and select subset of items.
"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
# Start an Ansys Dynamic Reporting service with a new database, assuming you
# have a local Ansys installation. Make sure to pass as the database
# directory the path to an empty directory.

import ansys.dynamicreporting.core as adr

ansys_loc = r"C:\Program Files\ANSYS Inc\v232"
db_dir = r"C:\tmp\new_database"
adr_service = adr.Service(ansys_installation=ansys_loc, db_directory=db_dir)
session_guid = adr_service.start(create_db=True)

###############################################################################
# Create items
# ------------
#
# Now that we have an Ansys Dynamic Reporting service running on top of a
# new database, let's populate it. We will create multiple text items for
# simplicity. Set some different names, sources, tags to the items.

for i in range(100):
    if i % 3 == 0:
        my_text = adr_service.create_item(obj_name=f"Name {str(i%20)}", source="Application X")
    elif i % 3 == 1:
        my_text = adr_service.create_item(obj_name=f"Name {str(i%20)}", source="Application Y")
    elif i % 3 == 2:
        my_text = adr_service.create_item(obj_name=f"Name {str(i%20)}", source="Application Z")
    my_text.item_text = "Any text. Does not matter the actual payload"
    if i % 4 == 0:
        my_text.set_tags("var=pressure")
    elif i % 4 == 1:
        my_text.set_tags("var=energy")
    elif i % 4 == 2:
        my_text.set_tags("var=temperature")
    elif i % 4 == 3:
        my_text.set_tags("var=vorticity")
    my_text.add_tag(tag="dp", value=str(i % 50))

###############################################################################
# Query the database
# ------------------
#
# Now that we have populated the database with a hundred items with different
# names, sources, and tags, let us query the database. Let's start with an empty
# query. This will return the entire set of items, so 100. Then, query based on the
# source name. This will result in three different lists of 34, 33 and 33 items each.
# Finally, query based on the name and on the dp tag. See that the lists have the
# expected length. You can try different queries using the other attributes that
# have been set on the items.
#

all_items = adr_service.query()
test_one = len(all_items) == 100
app_x = adr_service.query(filter="A|i_src|cont|Application X")
app_y = adr_service.query(filter="A|i_src|cont|Application Y")
app_z = adr_service.query(filter="A|i_src|cont|Application Z")
test_two = len(app_x) == 34
test_three = len(app_y) == len(app_z) == 33
name_0 = adr_service.query(filter="A|i_name|cont|Name 0")
name_11 = adr_service.query(filter="A|i_name|cont|Name 11")
name_7 = adr_service.query(filter="A|i_name|cont|Name 7")
test_four = len(name_7) == len(name_0) == len(name_11) == 5
dp0_items = adr_service.query(filter="A|i_tags|cont|dp=0")
dp10_items = adr_service.query(filter="A|i_tags|cont|dp=10")
dp33_items = adr_service.query(filter="A|i_tags|cont|dp=33")
test_five = len(dp0_items) == len(dp10_items) == len(dp33_items) == 2

###############################################################################
# Close the service
# -----------------
# Close the Ansys Dynamic Reporting service. The database with the
# items that were created will remain on disk.

adr_service.stop()
