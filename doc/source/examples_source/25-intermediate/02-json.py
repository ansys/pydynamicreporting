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
# Assume there is already running Ansys Dynamic Reporting Service that you might have set
# up in the guide earlier. Connect to that service. Should you require any information
# about the service connection, please refer to :ref:`ref_connect_to_a_running_service`.

import ansys.dynamicreporting.core as adr

adr_service = adr.Service(ansys_installation=r'C:\Program Files\ANSYS Inc\v232')
adr_service.connect(url='http://localhost:8020', username = "admin", password = "mypassword")
