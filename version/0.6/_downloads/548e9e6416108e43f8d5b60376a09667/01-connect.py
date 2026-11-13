"""
.. _ref_connect:

Connect services
================

This example shows how to start an Ansys Dynamic Reporting
service via a Docker image, create a second instance of the ``Service``
class, and connect it to the already running service. It then shows
how to create and modify items in the original database with this
new instance.

.. note::
   This example assumes that you do not have a local Ansys installation but
   are starting an Ansys Dynamic Reporting Service via a Docker image on
   a new database.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
#
# Start an Ansys Dynamic Reporting service via a Docker image on a new
# database. The path for the database directory must be to an empty directory.

import ansys.dynamicreporting.core as adr

db_dir = r"C:\tmp\new_database"
adr_service = adr.Service(ansys_installation="docker", db_directory=db_dir)
session_guid = adr_service.start(create_db=True)

###############################################################################
# Create items
# ------------
#
# Given that the Ansys Dynamic Reporting service is running on top
# of an empty database, create a few items in the database and then visualize
# the default report that shows all these items, one after the other. Note that
# this code assumes that you have files on disk for the payload of the items.

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
# Create another connected instance
# ---------------------------------
#
# Now that you have a running Ansys Dynamic Reporting service, create a
# second instance of the ``Reporting`` class and use it to
# connect to the database. Visualize the default report.

connected_s = adr.Service()
connected_s.connect(url=adr_service.url)
connected_s.visualize_report()


###############################################################################
#
# .. image:: /_static/01_connect_1.png
#
# Create an item via the connected object
# ---------------------------------------
#
# Use the new object for the connected service to create an ``Image`` item.
# Visualize the default report again to verify that this item has been
# added to the database.

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
# Assume that you want to visualize only the items that were
# created from the connected Ansys Dynamic Reporting session and not the
# original instance. To achieve this, you add a filter to the default
# report visualization. Note that running this method on either of the
# Ansys Dynamic Reporting instances produces the same result.

adr_service.visualize_report(filter=f"A|s_guid|cont|{connected_s.session_guid}")

###############################################################################
# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the items that
# were created remains on disk.

# sphinx_gallery_thumbnail_path = '_static/01_connect_3.png'
adr_service.stop()
