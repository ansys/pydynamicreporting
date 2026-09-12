"""
.. _ref_queries_example:

Item queries
============

The Ansys Dynamic Reporting database can contain any number of items, from a few
to tens of thousands. To handle all this data, the :func:`queryansys.dynamicreporting.core.Service.query>`
method allows you to quickly slice the database to select a subset of items.

.. note::
   This example assumes that you have a local Ansys installation.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
# Start an Ansys Dynamic Reporting service with a new database. The path for the
# database directory must be to an empty directory.

import ansys.dynamicreporting.core as adr
import ansys.dynamicreporting.core.examples as examples

ansys_loc = r"C:\Program Files\ANSYS Inc\v232"
db_dir = r"C:\tmp\new_database"
adr_service = adr.Service(ansys_installation=ansys_loc, db_directory=db_dir)
session_guid = adr_service.start(create_db=True)

###############################################################################
# Create items
# ------------
#
# Now that an Ansys Dynamic Reporting service is running on top of a
# new database, you can populate it. We will download and push to the database
# 14 images.We will then set some different names, sources, and
# tags based on the image names

variables = ["enthalpy", "statictemperature"]
for v in variables:
    for i in range(7):
        if i % 3 == 0:
            new_image = adr_service.create_item(
                obj_name=f"Image {str(i + 1)}", source="Application X"
            )
        elif i % 3 == 1:
            new_image = adr_service.create_item(
                obj_name=f"Image {str(i + 1)}", source="Application Y"
            )
        elif i % 3 == 2:
            new_image = adr_service.create_item(
                obj_name=f"Image {str(i + 1)}", source="Application Z"
            )
        filename = f"{v}_{str(i + 1).zfill(3)}.png"
        new_image.item_image = examples.download_file(filename, "input_data")
        new_image.set_tags(f"var={v} clip=-{float(i) * 0.01}")

###############################################################################
# Query the database
# ------------------
#
# Now that the database is populated with a few items with different
# names, sources, and tags, query the database, beginning with an empty
# query that returns the entire set (all 14 items). Next, query on the
# source name, which results in three different lists, with 6, 4, and 4 items
# respectively. Query on the ``var`` and ``clip`` taga. See that the lists
# have the expected length. You can try different queries using other attributes.
# #

all_items = adr_service.query()
test_one = len(all_items) == 14
app_x = adr_service.query(item_filter="A|i_src|cont|Application X")
app_y = adr_service.query(item_filter="A|i_src|cont|Application Y")
app_z = adr_service.query(item_filter="A|i_src|cont|Application Z")
test_two = len(app_x) == 6
test_three = len(app_y) == len(app_z) == 4
enthalpy_items = adr_service.query(item_filter="A|i_tags|cont|var=enthalpy")
statictemperature_items = adr_service.query(item_filter="A|i_tags|cont|var=statictemperature")
test_four = len(enthalpy_items) == len(statictemperature_items) == 7
clip3_items = adr_service.query(item_filter="A|i_tags|cont|clip=-0.03")
clip5_items = adr_service.query(item_filter="A|i_tags|cont|clip=-0.05")
test_five = len(clip3_items) == len(clip5_items) == 2

###############################################################################
# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the items that
# were created remains on disk.

# sphinx_gallery_thumbnail_path = '_static/default_thumb.png'
adr_service.stop()
