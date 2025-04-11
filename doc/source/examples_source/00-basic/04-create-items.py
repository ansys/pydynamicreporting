"""
.. _ref_create_items:

Create new items in the database
================================

To launch the service, provide an Ansys installation directory as a string.
You can provide an existing, empty, directory if you intend to create a database.

.. note::
   This example assumes that you have a local Ansys installation.

Initially, create and start a session as per other examples.

"""

import numpy as np

import ansys.dynamicreporting.core as adr
import ansys.dynamicreporting.core.examples as examples

db_dir = "C:\\tmp\\my_local_db_directory"
ansys_ins = "C:\\Program Files\\Ansys Inc\\v241"
adr_service = adr.Service(ansys_installation=ansys_ins, db_directory=db_dir)
session_guid = adr_service.start(create_db=True)


###############################################################################
# Create a text item
# ~~~~~~~~~~~~~~~~~~
# Text items are supplied as strings and can contain HTML instructions.
#

my_text = adr_service.create_item(obj_name="Text")
my_text.item_text = "<h1>Simple Title</h1>Abc..."

###############################################################################
# Create a table item
# ~~~~~~~~~~~~~~~~~~~
# Table items can only be numpy arrays, which is why you import numpy in a previous cell.
# Then:
# 1.  Create the item based on predefined names. 
# 1. Set the row labels.
# 1. Populate the database.
#


my_table = adr_service.create_item(obj_name="Table")
my_table.table_dict["rowlbls"] = ["Row 1", "Row 2"]
my_table.item_table = np.array(
    [["1", "2", "3", "4", "5"], ["1", "4", "9", "16", "25"]], dtype="|S20"
)

###############################################################################
# Create a image item
# ~~~~~~~~~~~~~~~~~~~
# To create an image item, supply the path to the image in question.
# In this example, you first download a sample PNG file and then supply its
# path.
#

img = adr_service.create_item(obj_name="Image")
image_path = examples.download_file("enthalpy_001.png", "input_data")
img.item_image = image_path

###############################################################################
# Create a 3D Item
# ~~~~~~~~~~~~~~~~
# This process is almost identical to the previous one except this time you assign
# the image path to the `item_scene` property.
#

scene = adr_service.create_item(obj_name="3D Scene")
scene.item_scene = r"C:\tmp\test_scene.avz"

###############################################################################
# Create a Tree item via a dictionary
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Creating a tree item follows the same pattern as
# previous examples have. In this example, the dictionary is quite large
# and takes up most of the code section.
#

# Create a tree item via a dictionary
leaves = []
for i in range(5):
    leaves.append({"key": "leaves", "name": f"Leaf {i}", "value": i})

children = []
children.append({"key": "child", "name": "Boolean example", "value": True})
children.append(
    {
        "key": "child_parent",
        "name": "A child parent",
        "value": "Parents can have values",
        "children": leaves,
        "state": "collapsed",
    }
)
tree = []
tree.append(
    {"key": "root", "name": "Top Level", "value": None, "children": children, "state": "expanded"}
)

# tree item creation
my_tree = adr_service.create_item(obj_name="Tree")
my_tree.item_tree = tree

# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the items that
# were created remains on disk.

# sphinx_gallery_thumbnail_path = '_static/00_create_db_0.png'
adr_service.stop()
