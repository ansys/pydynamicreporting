# Copyright (C) 2016 - 2025 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''
"""
.. _ref_set_plot_properties:

How to set plot properties
==========================

When working with a table it is possible to turn it into a plot by specifying
the plot type through the `plot` property.

.. note::
   This example assumes that you have a local Ansys installation.

Initially we must create and start a session, as per other examples.

'''

import ansys.dynamicreporting.core as adr


db_dir = 'C:\\tmp\\my_local_db_directory'
ansys_ins = 'C:\\Program Files\Ansys Inc\\v241'
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