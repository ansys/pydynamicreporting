"""
.. _ref_plottype:

Plot types
==========

This example shows how to start an Ansys Dynamic Reporting
service via a Docker image and create different plot items.
The example focuses on showing how to use the API to generate
different plot types.

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
import numpy as np

db_dir = r"C:\tmp\new_database"
adr_service = adr.Service(ansys_installation="docker", db_directory=db_dir)
session_guid = adr_service.start(create_db=True)

###############################################################################
# Create a simple table
# ---------------------
#
# Let us start by creating a simple table and visualizing it. Create a table
# with 5 columns and 3 rows.

simple_table = adr_service.create_item(obj_name="Simple Table", source="Documentation")
simple_table.item_table = np.array([[0, 1, 2, 3, 4], [0, 3, 6, 9, 12], [0, 1, 4, 9, 16]], dtype="|S20")
simple_table.labels_row = ["X", "line", "square"]


# You can use the labels_row attribute to set the row labels. Use the visualize
# method on the object to see its representation. By default, it will be displayed
# as a table


simple_table.visualize()


###############################################################################
#
# .. image:: /_static/simpletable.png.png
#
# Visualize as a line plot
# ------------------------
#
# Let us know create a new item that is the same as the previous simple table,
# but this time we will set the plot attribute to line to visualize the values
# as two line plots, and we will use the xaxis attribute to set which row should
# be used as the X axis. We can also control the formatting and the title of the
# axis separately with the *axis_format and *title attributes, as done below. 
# The result can be seen in the following image.

line_plot = adr_service.create_item(obj_name="Line Plot", source="Documentation")
line_plot.item_table = np.array([[0, 1, 2, 3, 4], [0, 3, 6, 9, 12], [0, 1, 4, 9, 16]], dtype="|S20")
line_plot.labels_row = ["X", "line", "square"]
line_plot.plot = 'line'
line_plot.xaxis = "X"
line_plot.yaxis_format = "floatdot0"
line_plot.xaxis_format = "floatdot1"
line_plot.xtitle = "x"
line_plot.ytitle = "f(x)"
line_plot.visualize()


###############################################################################
#
# .. image:: /_static/lineplot.png
#
# Visualize as a bar plot
# -----------------------
#
# Next, we will see how to create a bar plot. In order to do this, please
# note that it is necessary to repeat the value of the bar chart twice at
# each X location.

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
