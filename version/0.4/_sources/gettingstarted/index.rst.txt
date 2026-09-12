Getting started
###############

PyDynamicReporting supports Ansys Dynamic Reporting 2023 R2 and later. To run
PyDynamicReporting, you must have either a local copy of an Ansys installation
with a product that uses Ansys Dynamic Reporting or use a Docker image that
PyDynamicReporting sets up for you.

To get a copy of Ansys, visit the `Ansys <https://www.ansys.com/>`_ website.

Installation
~~~~~~~~~~~~

The ``ansys-dynamicreporting-core`` package currently supports Python 3.8
through Python 3.11 on Windows and Linux.

To install the latest package from GitHub, run this command:

.. code::

    pip install ansys-dynamicreporting-core


If you plan on doing local *development* of PyDynamicReporting, install the
latest ``pydynamicreporting`` package with this code:

.. code::

   git clone https://github.com/ansys/pydynamicreporting.git
   cd pydynamicreporting
   pip install virtualenv
   virtualenv venv  # create virtual environment. If on Windows, use virtualenv.exe venv
   source venv/bin/activate # If on Windows, use  .\venv\Scripts\activate
   pip install -r requirements/dev.txt  # install dependencies
   make install-dev  # install pydynamicreporting in editable mode


Now you can start developing the ``pydynamicreporting`` package.


Create an Ansys Dynamic Reporting instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once PyDynamicReporting is installed, your first step is to create an Ansys
Dynamic Reporting object. There are two ways to do this, based on whether
or not there is a local Ansys installation.

If there is a local installation, simply point to the version
directory inside the Ansys installation:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")


If there is no local installation, you must direct PyDynamicReporting to
download (if not already available) and run a Docker image:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation="docker", data_directory=r"C:\tmp\docker")


The ``data_directory`` parameter must pass a temporary directory that has to exist and be
empty. This directory stores temporary information from the Docker image.

Start and connect to an Ansys Dynamic Reporting service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once an Ansys Dynamic Reporting instance is created, you can start
an Ansys Dynamic Reporting service or connect to a running
one.

To connect to a running service, run this code:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect()


The preceding code assumes that there is a running Ansys Dynamic Reporting
service on your machine on port 8000 with the default username and password.
If the Ansys Dynamic Reporting service does not use the default values for
the URL, port, and login credentials, you must provide the appropriate values
in the :func:`connect<ansys.dynamicreporting.core.Service.connect>` method:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(
       url="my_machine:8010", username="MyUsername", password="MyPassword"
   )


.. note::
   When you are connecting to a running Ansys Dynamic Reporting service, the
   web components that you obtain from PyDynamicReporting might or might not
   be embedded. This is controlled by how the Ansys Dynamic Reporting service
   was started. To ensure that web components can be embedded, you must
   start the Ansys Dynamic Reporting service with iframes enabled via this flag:

   .. code::

      --allow_iframe_embedding


   If you are using PyDnamicReporting to start the Ansys Dynamic Reporting
   service, you do not need to take any action because iframes are enabled
   by default. For more information on the launcher in Ansys Dynamic Reporting,
   see the Ansys Dynamic Reporting `documentation`_.


.. _documentation: https://nexusdemo.ensight.com/docs/is/html/Nexus.html

Now, assume that you do not have a running Ansys Dynamic Reporting service
accessible to you and that you must start one. You can use this simple
start method:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v232",
       db_directory=r"D:\tmp\db_directory",
   )
   session_guid = adr_service.start(create_db=True)


The ``adr_service`` object is now connected to a newly started Ansys Dynamic
Reporting service on a new database. Once again, you can control the parameters
of the Ansys Dynamic Reporting service (port number, username, and
password) by passing them as arguments:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v232",
       db_directory=r"D:\tmp\db_directory",
       port=8010,
   )
   session_guid = adr_service.start(create_db=True, username="MyUser", password="abcd")
