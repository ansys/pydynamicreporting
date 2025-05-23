"""
.. _ref_create_report_templates:

Creating report templates
=========================

Templates are used to specify how the final report will be organised. They
can be nested to describe the layout of subsections in greater detail.

.. note::
   This example assumes that you have a local Ansys installation.

Initially, create and start a session as per other examples.

"""

###############################################################################
# Start an Ansys Dynamic Reporting service
# ----------------------------------------
#
# Start an Ansys Dynamic Reporting service on a new
# database. The path for the database directory must be to an empty directory.
# Get the serverobj property from the service. This property will be used to create the
# template.
#

import ansys.dynamicreporting.core as adr

db_dir = "C:\\tmp\\my_local_db_directory"
ansys_ins = "C:\\Program Files\\Ansys Inc\\v241"
adr_service = adr.Service(ansys_installation=ansys_ins, db_directory=db_dir)
session_guid = adr_service.start(create_db=True)
server = adr_service.serverobj


###############################################################################
# Create a template
# ~~~~~~~~~~~~~~~~~~
# The template is a plan of how ADR items will be presented in the final report.
# The contents of sections is specified by filters that query the tags of items
# in the database.
#


template_0 = server.create_template(name="My Report", parent=None, report_type="Layout:basic")

server.put_objects(template_0)

###############################################################################
# Nesting templates
# ~~~~~~~~~~~~~~~~~
# Templates can be nested to describe layouts within a section, with the topmost template
# being the report itself.
#
# Filters are composed of strings in a common format. The format is explained in more detail
# on this page [Query Expressions](https://ansyshelp.ansys.com/public/account/secured?returnurl=/Views/Secured/corp/v251/en/adr_ug/adr_ug_query_expressions.html?q=query%20expression).
#

template_1 = server.create_template(name="Intro", parent=template_0, report_type="Layout:panel")
template_1.set_filter("A|i_type|cont|html,string;")

server.put_objects(template_1)
server.put_objects(template_0)
template_2 = server.create_template(name="Plot", parent=template_0, report_type="Layout:panel")
template_2.set_filter("A|i_type|cont|table;")

server.put_objects(template_2)
server.put_objects(template_0)

# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the items that
# were created remains on disk.

# sphinx_gallery_thumbnail_path = '_static/00_create_db_0.png'
adr_service.stop()
