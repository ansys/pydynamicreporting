Getting started
###############

``pydynamicreporting`` supports Ansys Dynamic Reporting versions 2023 R2 or newer. To run
``pydynamicreporting``, you either have to have a local copy of Ansys Dynamic
Reporting, or use a docker image that is set up by the ``pydynamicreporting``
module for you.

Visit `Ansys`_ for more information on getting a copy of Ansys Dynamic Reporting.

.. _Ansys: https://www.ansys.com/

Installation
~~~~~~~~~~~~

The ``ansys-dynamicreporting-core`` package currently supports Python 3.8 through Python 3.11 on Windows and Linux.

Install the latest from ``pydynamicreporting`` GitHub via:

.. code::

    pip install ansys-dynamicreporting-core

If you plan on doing local *development* of ``pydynamicreporting``,
install the latest package with this code:

.. code::

   git clone https://github.com/ansys/pydynamicreporting.git
   cd pydynamicreporting
   pip install virtualenv
   virtualenv venv  # create virtual environment. If on Windows, use virtualenv.exe venv
   source venv/bin/activate # If on Windows, use  .\venv\Scripts\activate
   pip install -r requirements/dev.txt  # install dependencies
   make install-dev  # install pydynamicreporting in editable mode


Now you can start developing ``pydynamicreporting``.


Creating a ``pydynamicreporting`` instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once ``pydynamicreporting`` is available to the user, the first step is to create an Ansys
Dynamic Reporting object. There are two ways to do this, based on whether
or not there is a local Ansys installation.

If there is a local installation, the user simply needs to point to the version
directory inside that installation:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")

If there is no local installation, the user needs to direct ``pydynamicreporting`` to
download (if not already available) and run a docker image:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation="docker", data_directory=r"C:\tmp\docker")

The ``data_directory`` parameter needs to pass a temporary directory (that needs to exist and be
empty) where to store temporary information from the docker image.

Launching or connecting to an Ansys Dynamic Reporting service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that the user has an Ansys Dynamic Reporting instance set up, they can
start an Ansys Dynamic Reporting service or connect to an existing one.

To connect to a running service, execute the following lines:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect()

The preceding snippet assumes that there is a running Ansys Dynamic Reporting
service on your machine on port 8000, with the default username and password.
If the Ansys Dynamic Reporting service does not use the default values
for port and log in credentials, the user needs to input them in the connect method:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
   ret = adr_service.connect(
       url="my_machine:8010", username="MyUsername", password="MyPassword"
   )


.. note::
   When you are connecting to an Ansys Dynamic Reporting service that is already
   running, the web components that you obtain from ``pydynamicreporting`` might or
   might not be embedded. This is controlled by how that Ansys Dynamic Reporting service
   was started. To make sure the web components can be embedded, make sure that
   the Ansys Dynamic Reporting service is launched with iFrames enabled via the flag:

   .. code::

      --allow_iframe_embedding


   If you are starting the service via ``pydynamicreporting``, this is the default
   so no need to do anything. For more information, see the details of the
   Ansys Dynamic Reporting `launcher`_.


.. _launcher: https://nexusdemo.ensight.com/docs/is/html/Nexus.html

Now, assume instead that you do not have a running Ansys Dynamic Reporting
service accessible to you, and need to start a new one. This can be
achieved with the simple start method:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v232",
       db_directory=r"D:\tmp\db_directory",
   )
   session_guid = adr_service.start(create_db=True)

Your ``adr_service`` object now is connected to the newly started Ansys Dynamic
Reporting service on a new database. Once again you can control the parameters
of the Ansys Dynamic Reporting service (port number, username and
password) by passing them as arguments:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v232",
       db_directory=r"D:\tmp\db_directory",
       port=8010,
   )
   session_guid = adr_service.start(create_db=True, username="MyUser", password="abcd")
