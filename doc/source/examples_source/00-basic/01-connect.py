"""
.. _ref_connect:

Connect Services
================

In this example we will use the API to start an Ansys Dynamic Reporting
service, and then create a second instance of the class and connect it
to the already running service. We will show that we can create and modify
items on the original database with this new instance
"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
# Assuming you do not have a local Ansys installation, use
# ``pydynamicreporting`` to start an Ansys Dynamic Reporting service via a docker
# image on a new database. Make sure the database directory is an empty
# directory.

import ansys.dynamicreporting.core as adr

db_dir = r"C:\tmp\new_database"
adr_service = adr.Service(ansys_installation="docker", db_directory=db_dir)
session_guid = adr_service.start(create_db=True)

###############################################################################
# Create items
# ------------
#
# Given that the Ansys Dynamic Reporting service is currently running on top
# of an empty database, create a few items for the database and then visualize
# the default report that shows all the items one after the other. This
# assumes you have files on disk for the payload of the items.

my_text = adr_service.create_item(obj_name="Text", source="Documentation")
my_text.item_text = "This is a simple string with no HTML formatting."
my_animation = adr_service.create_item(obj_name="Animation File", source="Documentation")
my_animation.item_animation = r"D:\tmp\myanim.mp4"
my_file = adr_service.create_item(obj_name="General File", source="Documentation")
my_file.item_file = r"D:\tmp\anytfile.txt"
adr_service.visualize_report()

###############################################################################
#
# .. image:: /_static/01_connect_0.png
#
# Create a new connected instance
# -------------------------------
#
# Now that we have a running Ansys Dynamic Reporting service, create a
# second instance of the Ansys Dynamic Reporting class and use it to connect
# to the database. Visualize the default report

connected_s = adr.Service()
connected_s.connect(url=adr_service.url)
connected_s.visualize_report()


###############################################################################
#
# .. image:: /_static/01_connect_1.png
#
# Create a new item via the connected object
# ------------------------------------------
#
# Use the new object for the connected service to create a new image item.
# Visualize the default report again to verify that the item has correctly
# been added to the database.
#

my_image = connected_s.create_item(obj_name="Image", source="Documentation")
my_image.item_image = r"D:\tmp\local_img.png"
connected_s.visualize_report()


###############################################################################
#
# .. image:: /_static/01_connect_3.png
#
# Visualize only items from a session
# -----------------------------------
#
# Let us now assume that the user wants to visualize only the items that were
# created from the connected Ansys Dynamic Reporting session and not the
# original instance. This can be achieved by adding a filter to the default
# report visualization. Note that running this method on either of the
# Ansys Dynamic Reporting instances will have the same result

adr_service.visualize_report(filter=f"A|s_guid|cont|{connected_s.session_guid}")

###############################################################################
# Close the service
# -----------------
# Close the Ansys Dynamic Reporting service. The database with the items that were created will
# remain on disk.

adr_service.stop()
