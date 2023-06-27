Ansys Dynamic Reporting
=======================

.. toctree::
   :hidden:
   :maxdepth: 5

   gettingstarted/index
   userguide/index
   class_documentation
   examples/index
   contributing

Introduction
------------
Ansys Dynamic Reporting is the report generator technologies used by Ansys tools. It allows
users to collect data in multiple formats from different sources, aggregate it,
analyze it, and display it in highly interactive reports.

Key features include:

- Handling multiple data formats natively
- Storage of data from multiple sources (CAD packages, simulation software, post processors, and so on)
- Tools to aggregate, filter, process data in the database
- Web based interface that allows users to quickly and intuitively interact with the database items
- Template editor to generate report templates
- Live reports that automatically update when new data is available
- Reports with high degree of interactively


What is ``pydynamicreporting``?
-------------------------------
``pydynamicreporting`` is part of the `PyAnsys <https://docs.pyansys.com>`_ ecosystem. It is
a Python module that allows the user to launch / connect to an Ansys Dynamic Reporting service
and control database and reports. It also provides the user with quick access to web
components, so that items or reports can easily be embedded in other applications.


Documentation and issues
------------------------
Please see the latest release `documentation <https://dynamicreporting.docs.pyansys.com/>`_
page for more details.

Please feel free to post issues and other questions at `GitHub Issues
<https://github.com/ansys/pydynamicreporting/issues>`_. This is the best place
to post questions and code.

License
-------
``pydynamicreporting`` is licensed under the MIT license.

This module, ``ansys-dynamicreporting-core`` makes no commercial claim over
Ansys whatsoever. This tool extends the functionality of ``Ansys Dynamic Reporting``
by adding a remote Python interface to Ansys Dynamic Reporting without changing the
core behavior or license of the original software. The use of Ansys Dynamic
Reporting through the ``pydynamicreporting`` interface requires any license that
allows the use of stand alone Ansys Dynamic Reporting.

Project index
-------------

* :ref:`genindex`
