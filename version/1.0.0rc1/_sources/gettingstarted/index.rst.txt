Getting started
###############

To run PyDynamicReporting, you must have a local copy of a
supported Ansys installation that includes Ansys Dynamic Reporting.
PyDynamicReporting uses a rolling ADR product compatibility policy. Each
client major version supports the ADR annual product line it is bundled with
and the immediately previous annual product line. For example, the ``1.x``
client line supports ADR ``26.*`` and ``27.*``. Older ADR releases might still
work in some cases, but they are outside the supported compatibility window and
can produce compatibility warnings. For details, see the
:ref:`Compatibility Policy <compatibility_policy>`.

To get a copy of Ansys, visit the `Ansys <https://www.ansys.com/>`_ website.

.. note::

   Up to the Ansys 2023 R2 release, Ansys Dynamic Reporting is installed as
   part of the Ansys EnSight package, under the Fluids section of the
   installer. Starting from the Ansys 2024 R1 release, Ansys Dynamic Reporting
   is installed separately, and can be found in the Fluids section of the
   Ansys installer. Please also note that in all versions, Ansys Dynamic Reporting
   is automatically installed if one of the following Ansys products is
   installed: EnSight, Forte, Fluent, Polyflow, or Icepack.



Installation
~~~~~~~~~~~~

The ``ansys-dynamicreporting-core`` package currently supports Python 3.10
through Python 3.13 on Windows and Linux.

To install the latest package from PyPI, run this command:

.. code::

   pip install ansys-dynamicreporting-core


If you plan on doing local development of PyDynamicReporting, clone the
repository and use the checked-in ``uv.lock`` file:

.. code::

   git clone https://github.com/ansys/pydynamicreporting.git
   cd pydynamicreporting
   make install

The ``make install`` target runs ``uv sync --frozen --all-extras`` and installs
the package in editable mode. Use ``uv sync --frozen --all-extras`` directly
if ``make`` is unavailable.

Create an Ansys Dynamic Reporting instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once PyDynamicReporting is installed, your first step is to create an Ansys
Dynamic Reporting object. There are two ways to do this, based on whether
or not there is a local Ansys installation.

If there is a local installation, simply point to the version
directory inside the Ansys installation:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v261")


If there is no local installation, you must direct PyDynamicReporting to
download (if not already available) and run a Docker image:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(
       ansys_installation="docker",
       docker_image="your-adr-image:latest",
       data_directory=r"C:\tmp\adr_work",
       db_directory=r"C:\tmp\adr_database",
   )


There is no public ADR image. Set ``docker_image`` to an image that you are
authorized to use. The ``data_directory`` must exist and be empty; it stores
temporary files copied from the container. The ``db_directory`` stores the ADR
database and must also be empty when you create a database.

Start and connect to an Ansys Dynamic Reporting service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once an Ansys Dynamic Reporting instance is created, you can start
an Ansys Dynamic Reporting service or connect to a running
one.

To connect to a running service, run this code:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v261")
   ret = adr_service.connect()


The preceding code assumes that there is a running Ansys Dynamic Reporting
service on your machine on port 8000 with the default username and password.
If the Ansys Dynamic Reporting service does not use the default values for
the URL, port, and login credentials, you must provide the appropriate values
in the :func:`connect<ansys.dynamicreporting.core.Service.connect>` method:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v261")
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


   If you are using PyDynamicReporting to start the Ansys Dynamic Reporting
   service, you do not need to take any action because iframes are enabled
   by default. For more information on the launcher in Ansys Dynamic Reporting,
   see the Ansys Dynamic Reporting `documentation`_.


.. _documentation: https://ansyshelp.ansys.com/public/account/secured?returnurl=/Views/Secured/prod_page.html?pn=Ansys%20Dynamic%20Reporting&pid=ansdynrep&lang=en


Now, assume that you do not have a running Ansys Dynamic Reporting service
accessible to you and that you must start one. You can use this simple
start method:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v261",
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
       ansys_installation=r"C:\Program Files\ANSYS Inc\v261",
       db_directory=r"D:\tmp\db_directory",
       port=8010,
   )
   session_guid = adr_service.start(create_db=True, username="MyUser", password="abcd")
