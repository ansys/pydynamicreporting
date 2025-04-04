"""
.. _ref_set_plot_properties:

How to set plot properties
==========================

When working with a table it is possible to turn it into a plot by specifying
the plot type through the `plot` property.

.. note::
   This example assumes that you have a local Ansys installation.

Initially we must create and start a session, as per other examples.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
#
# Start an Ansys Dynamic Reporting service via a Docker image on a new
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

simple_table = adr_service.create_item(obj_name="Simple Table", source="Documentation")
simple_table.item_table = np.array(
    [[0, 1, 2, 3, 4], [0, 3, 6, 9, 12], [0, 1, 4, 9, 16]], dtype="|S20"
)
simple_table.labels_row = ["X", "line", "square"]

###############################################################################
# Once we have created a table we can actually set it to be a plot by changing
# its properties
#

# Set visualization to be plot instead of table
simple_table.plot = "line"

# Set X axis and axis formatting
simple_table.xaxis = "Row 1"
simple_table.format = "floatdot1"

adr_service.stop()
