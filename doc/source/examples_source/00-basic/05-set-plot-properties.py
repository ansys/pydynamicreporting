"""
.. _ref_set_plot_properties:

How to set plot properties
==========================

When working with a table, you can turn it into a plot by specifying
the plot type through the `plot` property. Once a table is converted
you can alter all sorts of plot properties by accessing properties on
the item object.

.. note::
   This example assumes that you have a local Ansys installation.

Initially, you must create and start a session as per other examples.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
#
# Start an Ansys Dynamic Reporting service on a new
# database. The path for the database directory must be to an empty directory.
#

import numpy as np

import ansys.dynamicreporting.core as adr

db_dir = "C:\\tmp\\new_database"
adr_service = adr.Service(db_directory=db_dir)
session_guid = adr_service.start(create_db=True)

###############################################################################
# Create a simple table
# ---------------------
#
# Let us start by creating a simple table and visualizing it. Create a table
# with 5 columns and 3 rows.
#

my_table = adr_service.create_item(obj_name="Table")
my_table.table_dict["rowlbls"] = ["Row 1", "Row 2"]
my_table.item_table = np.array(
    [["1", "2", "3", "4", "5"], ["1", "4", "9", "16", "25"]], dtype="|S20"
)

###############################################################################
# Once you have created a table, set it to be a plot by changing
# its properties, and then you can set other properties.
#

# Set visualization to be plot instead of table
my_table.plot = "line"

# Set X axis and axis formatting
my_table.xaxis = "Row 1"
my_table.format = "floatdot1"

###############################################################################
# Properties can also be inspected this way.
#

print(my_table.type)

# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the items that
# were created remains on disk.

# sphinx_gallery_thumbnail_path = '_static/00_create_db_0.png'
adr_service.stop()
