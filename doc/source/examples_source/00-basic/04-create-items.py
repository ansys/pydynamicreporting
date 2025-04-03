"""
.. _ref_create_items:

Create new items in the database
================================

In order to launch the service an Ansys installation directory must be provided as a string
and an existing, empty, directory may be provided if you intend to create a database.

.. note::
   This example assumes that you have a local Ansys installation.

Initially we must create and start a session, as per other examples.

"""
import ansys.dynamicreporting.core as adr


db_dir = 'C:\\tmp\\my_local_db_directory'
ansys_ins = 'C:\\Program Files\Ansys Inc\\v241'
adr_service = adr.Service(ansys_installation=ansys_ins, db_directory=db_dir)
session_guid = adr_service.start(create_db=True)


###############################################################################
# Create a text item
# ~~~~~~~~~~~~~~~~~~
# Once a `Service` object has been created, it must be started. It can be #
# similarly stopped.
#

my_text = adr_service.create_item(obj_name='Text')
my_text.item_text = "<h1>Simple Title</h1>Abc..."

###############################################################################
# Create a table item
# ~~~~~~~~~~~~~~~~~~
# Table items can only be numpy arrays so first we need to import numpy. Then,
# create our item based on predefined names. Then we can set the row labels and
# populate the database.
#

import numpy as np

my_table = adr_service.create_item(obj_name='Table')
my_table.table_dict["rowlbls"] = ["Row 1", "Row 2"]
my_table.item_table = np.array([["1", "2", "3", "4", "5"],
                                ["1", "4", "9", "16", "25"]], dtype="|S20")

###############################################################################
# Create a plot item
# ~~~~~~~~~~~~~~~~~~
# To create an image item we just need to supply the path to the image in question.
# 

# Set visualization to be plot instead of table
my_table.plot = 'line'

# Set X axis and axis formatting
my_table.xaxis = 'Row 1'

my_table.format = 'floatdot1'

# Finally, stop the service
adr_service.stop()