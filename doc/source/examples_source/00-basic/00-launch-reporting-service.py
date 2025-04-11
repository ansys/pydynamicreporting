"""
.. _ref_launch_reporting_service:

Launching the Ansys Dynamic Reporting Service
=============================================

To launch the service, provide an Ansys installation directory as a string.
You can provide an existing, empty, directory if you intend to create a database.

.. note::
   This example assumes that you have a local Ansys installation.

"""

import ansys.dynamicreporting.core as adr

db_dir = "C:\\tmp\\my_local_db_directory"
ansys_ins = "C:\\Program Files\\Ansys Inc\\v241"

adr_service = adr.Service(ansys_installation=ansys_ins, db_directory=db_dir)


###############################################################################
# Starting the Service
# ~~~~~~~~~~~~~~~~~~~~
# Once a `Service` object has been created, it must be started. It can be #
# similarly stopped.
#

session_guid = adr_service.start(create_db=True)

# To stop the service
adr_service.stop()

###############################################################################
# Connecting to a remote Service
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# You may need to connect to a service that is already running. To do so create
# a Service object, as before, but leave off the database argument and this time,
# call the `connect` method and provide connection details, including any
# credentials required.
#

ansys_ins = r"C:\Program Files\Ansys Inc\v241"
adr_service = adr.Service(ansys_installation=ansys_ins)
adr_service.connect(url="http://localhost:8000", username="user", password="p455w0rd")

# To stop the service
# sphinx_gallery_thumbnail_path = '_static/00_create_db_0.png'
adr_service.stop()
