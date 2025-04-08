"""
.. _ref_all_plot_properties:

Explore plot properties
=======================

When working with a table it is possible to turn it into a
plot by specifying the plot type through the `plot` property.
In this example we demonstrate a variety of the possible plot
properties available.

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

my_table = adr_service.create_item(obj_name='Table')
my_table.table_dict["rowlbls"] = ["Row 1", "Row 2"]
my_table.item_table = np.array([["1", "2", "3", "4", "5"],["1", "4", "9", "16", "25"]], dtype="|S20")

###############################################################################
# Once we have created a table we can actually set it to be a plot by changing
# its properties, and then we are free to set other properties.
#

# Set visualization to be plot instead of table
my_table.plot = "line"

# Set X axis and axis formatting
my_table.xaxis = "Row 1"
my_table.format = "floatdot1"

###############################################################################
# Some rules on properties
# ------------------------
# - If a property is not relevant to a plot and it is changed, nothing will happen
# - Plots are not dynamically updated. Subsequent `visualize` calls are needed
# - Plots can have `visualize()` called repeatedly without exhausting the object
#

my_table.line_color = 'black'
# This won't appear on our 2D plot or affect its output
my_table.zaxis = 'z-axis'
my_table.visualize()

# Sets the x-axis limits and similar patterns work for yrange and zrange.
my_table.xrange = [0, 3]
my_table.visualize()

###############################################################################
# Key properties
# --------------
# A few key properties are listed below as well as what they do, to get you started.
#
# - `xtitle`, `ytitle`, `ztitle`, `palette_title` - set the axis, and colorbar, labels
# - `xrange`, `yrange, `zrange`, `palette_range` - set the axes amd colorbar limits
# - `plot_title` - set the plot title
# - `line_marker` - set the marker of scatter data, defaults to `circle`.
# - `line_error_bars` - set y-axis error bars. Other axes are not available.
# - `width`, `height` - dimensions of chart in pixels
#

adr_service.stop()
