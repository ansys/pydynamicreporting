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
.. _ref_launch_reporting_service:

Launching the Ansys Dynamic Reporting Service
=============================================

In order to launch the service an Ansys installation directory must be provided as a string
and an existing, empty, directory may be provided if you intend to create a database.

.. note::
   This example assumes that you have a local Ansys installation.

'''

import ansys.dynamicreporting.core as adr


db_dir = 'C:\\tmp\\my_local_db_directory'
ansys_ins = 'C:\\Program Files\Ansys Inc\\v241'

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

import ansys.dynamicreporting.core as adr


ansys_ins = r'C:\Program Files\Ansys Inc\v241'
adr_service = adr.Service(ansys_installation=ansys_ins)
adr_service.connect(url='http://localhost:8000', username='user', password='p455w0rd')

# To stop the service
adr_service.stop()
