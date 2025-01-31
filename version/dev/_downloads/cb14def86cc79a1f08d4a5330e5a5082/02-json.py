"""
.. _ref_json:

Import or export report template using JSON
===========================================

Ansys Dynamic Reporting provides a seamless solution for serializing and
deserializing report templates. It allows you to export templates as local
JSON files and rebuild them through JSON imports. This section describes
the process of converting a report template and loading it back in.

.. note::

   This example assumes that you have a local Ansys installation.

"""

##########################################################################################
# Start a new Ansys Dynamic Reporting service
# -------------------------------------------
#
# Start a new ADR service. Make sure the database directory is empty. Use the get_list_report
# method to check that there are no reports in the datanase.

import ansys.dynamicreporting.core as adr
import ansys.dynamicreporting.core.examples as examples

adr_service = adr.Service(
    ansys_installation=r"C:\Program Files\ANSYS Inc\v251", db_directory=r"C:\tmp\new_template"
)
adr_service.start(create_db=True)
adr_service.get_list_reports()

##########################################################################################
#
# Create a new report template from the JSON file
# ------------------------------------------------
#
# Download a JSON sample file for the report templates. Load it into the ADR service.
# Check that the ADR service now contains a report. Visualize it.

template_path = examples.download_file("report_template.json", "multi_physics")
adr_service.load_templates(template_path)
adr_service.get_list_reports()
new_report = adr_service.get_report("Solution Analysis from Multiphysics simulation")
new_report.visualize()

##########################################################################################
#
# .. image:: /_static/report_json_vis.png
#    :scale: 50%
#
# Modify and export the report template
# -------------------------------------
#
# Add a new chapter to the report template using the low level API. Export the new JSON
# file corresponding to the changed report, and visualize it. Note the extra chapter in
# the Table Of Contents, corresponding to the change you just made.

server = adr_service.serverobj
new_chapter = server.create_template(
    name="Appendix", parent=new_report.report, report_type="Layout:basic"
)
new_chapter.params = '{"TOCitems": 1, "HTML": "<h3>Appendix</h3>", "properties": {"TOCItem": "1", "TOCLevel": "0", "justification": "left"}}'
new_chapter.set_filter("A|i_tags|cont|section=appendix;")
server.put_objects(new_chapter)
server.put_objects(new_report.report)
new_report.visualize()

new_report.export_json("modified_report.json")

##########################################################################################
#
# .. image:: /_static/export_json_vis.png
#    :scale: 50%
#
# .. note::
#
#    If the name of the loaded report conflicts with an existing name in the service
#    (for example, when reloading the same report as in the previous step), Ansys Dynamic
#    Reporting automatically renames the loaded report. In this case, the report will be
#    renamed to "my_report_name (1)".

###############################################################################
# Close the service
# -----------------
#
# Close the Ansys Dynamic Reporting service. The database with the report
# template that was created remains on disk.

# sphinx_gallery_thumbnail_path = '_static/default_thumb.png'
adr_service.stop()
