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
import numpy as np


db_dir = 'C:\\tmp\\my_local_db_directory'
ansys_ins = 'C:\\Program Files\\Ansys Inc\\v241'
adr_service = adr.Service(ansys_installation=ansys_ins, db_directory=db_dir)
session_guid = adr_service.start(create_db=True)


###############################################################################
# Create a table
# ~~~~~~~~~~~~~~
# Once a `Service` object has been created, it must be started. It can be #
# similarly stopped.
#

my_text = adr_service.create_item(obj_name='Text')
my_text.item_text = "<h1>Simple Title</h1>Abc..."

###############################################################################
# Create a table item
# ~~~~~~~~~~~~~~~~~~
# Table items can only be numpy arrays, which is why we import numpy in a previous cell. 
# Then, create our item based on predefined names. Then we can set the row labels and
# populate the database.
#


my_table = adr_service.create_item(obj_name='Table')
my_table.table_dict["rowlbls"] = ["Row 1", "Row 2"]
my_table.item_table = np.array([["1", "2", "3", "4", "5"],
                                ["1", "4", "9", "16", "25"]], dtype="|S20")

###############################################################################
# Create a image item
# ~~~~~~~~~~~~~~~~~~
# To create an image item we just need to supply the path to the image in question.
# 

img = adr_service.create_item(obj_name='Image')
img.item_image = 'C:\\tmp\\test_image.png'

###############################################################################
# Create a 3D Item
# ~~~~~~~~~~~~~~~~
# This process is almost identical to the previous one except this time we assign
# to the `item_scene` property.
# 

scene = adr_service.create_item(obj_name='3D Scene')
scene.item_scene = r'C:\tmp\test_scene.avz'

###############################################################################
# Create a Tree item via a dictionary
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Creating a tree item is similarly straightforward following the same pattern as
# previous examples have, however, in this example our dictionary is quite large 
# and takes up most of the code section.
# 

# Create a tree item via a dictionary
leaves = []
for i in range(5):
    leaves.append({"key": "leaves", "name": f"Leaf {i}", "value": i})

children = []
children.append({"key": "child", "name": "Boolean example", "value": True})
children.append({"key": "child_parent", "name": "A child parent", "value": "Parents can have values", "children": leaves, "state": "collapsed"})   
tree = []
tree.append({"key": "root", "name": "Top Level", "value": None, "children": children, "state": "expanded"})

# tree item creation
my_tree = adr_service.create_item(obj_name="Tree")
my_tree.item_tree = tree


# Finally, stop the service
adr_service.stop()