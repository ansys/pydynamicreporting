"""
.. _ref_json:

JSON export/import
====================

Ansys Dynamic Reporting provides a seamless solution for serialization and deserialization
of reports. It enables users to export reports as local JSON files and rebuild reports through
JSON imports. This guide will walk you through the process of converting a report template
and loading it back, ensuring you gain confidence and proficiency in using these features.

.. note::

   This example assumes that you have a local Ansys installation.

"""

##########################################################################################
# Connect to a running Ansys Dynamic Reporting service
# ----------------------------------------------------
#
# Assume that an Ansys Dynamic Reporting service is already running, as set up in the
# earlier steps of this guide. Connect to the service to proceed. For additional details
# about establishing a service connection, refer to :ref:`ref_connect_to_a_running_service`.

import ansys.dynamicreporting.core as adr

adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
adr_service.connect(url="http://localhost:8020", username="admin", password="mypassword")

##########################################################################################
# Select a report and export it to a JSON file
# --------------------------------------------
#
# From the running service, select the desired report and export it as a JSON file to
# your local disk.

report = adr_service.get_report(report_name="my_report_name")
report.export_json(r"C:\tmp\my_json_file.json")

##########################################################################################
# Load the JSON file back
# -----------------------
#
# Load the same file you just exported back the Ansys Dynamic Reporting service.

adr_service.load_templates(r"C:\tmp\my_json_file.json")

##########################################################################################
#
# .. note::
#
#    If the name of the loaded report conflicts with an existing name in the service
#    (e.g., when reloading the same report as in the previous step), Ansys Dynamic
#    Reporting automatically renames the loaded report. In this case, the report will be
#    renamed to "my_report_name (1)".
