PyDynamicReporting
==================

.. toctree::
   :hidden:
   :maxdepth: 5

   gettingstarted/index
   userguide/index
   class_documentation
   examples/index
   serverless/index
   contributing

.. _Nexus: https://ansyshelp.ansys.com/public/account/secured?returnurl=/Views/Secured/prod_page.html?pn=Ansys%20Dynamic%20Reporting&pid=ansdynrep&lang=en

Introduction
------------
Ansys Dynamic Reporting, documented as `Nexus`_, provides the report
generator technologies that are used in several Ansys products. Ansys Dynamic
Reporting allows you to collect data in multiple formats from different sources.
You can then aggregate, analyze, and display this data in highly interactive reports.

Here are some key features of Ansys Dynamic Reporting:

- Handles multiple data formats natively.
- Stores data from multiple sources, including CAD packages, simulation software, and postprocessors.
- Provides tools for aggregating, filtering, and processing the data in the database.
- Supplies a web-based interface for quickly and intuitively interacting with database items.
- Includes a template editor for generating report templates.
- Displays live reports that automatically update when new data is available.
- Generates reports with a high degree of interactivity.

What is PyDynamicReporting?
---------------------------
PyDynamicReporting is part of the `PyAnsys <https://docs.pyansys.com>`_ ecosystem. It is
a Python client library that allows you to start and connect to an Ansys Dynamic Reporting
service and control the database and reports. It also provides you with quick access to web
components so that you can easily embed items or reports in other apps.

Serverless ADR
--------------
Serverless ADR is a standalone implementation of ADR integrated into pydynamicreporting
that does not require launching the ADR service.
It avoids all service overhead and can be used in Python applications directly for local or isolated use cases.

It supports:

- Single-database mode (typically SQLite)
- Multi-database setups, including PostgreSQL
- Docker-based initialization
- Media and static asset handling
- Full HTML report rendering without a server

This is useful for lightweight workflows or embedding reporting into your own apps.

See :doc:`Serverless ADR documentation <serverless/index>` for full details.

Documentation and issues
------------------------
Documentation for the latest stable release of PyDynamicReporting is hosted at
`PyDynamicReporting documentation <https://dynamicreporting.docs.pyansys.com/version/stable/>`_.

In the upper right corner of the documentation's title bar, there is an option
for switching from viewing the documentation for the latest stable release
to viewing the documentation for the development version or previously
released versions.

You can also `view <https://cheatsheets.docs.pyansys.com/pydynamicreporting_cheat_sheet.png>`_ or
`download <https://cheatsheets.docs.pyansys.com/pydynamicreporting_cheat_sheet.pdf>`_ the
PyDynamicReporting cheat sheet. This one-page reference provides syntax rules and commands
for using PyDynamicReporting.

On the `PyDynamicReporting Issues <https://github.com/ansys/pydynamicreporting/issues>`_
page, you can create issues to report bugs and request new features. On the `Discussions <https://discuss.ansys.com/>`_
page on the Ansys Developer portal, you can post questions, share ideas, and get community feedback.

To reach the project support team, email `pyansys.core@ansys.com <pyansys.core@ansys.com>`_.

License
-------
PyDynamicReporting is licensed under the MIT license.

PyDynamicReporting makes no commercial claim over Ansys whatsoever.
This library extends Ansys Dynamic Reporting by adding a Python
interface to Ansys Dynamic Reporting without changing the core behavior
or license of the original software. The use of PyDynamicReporting
requires a legally licensed copy of an Ansys product that supports
Ansys Dynamic Reporting.

Project index
-------------

* :ref:`genindex`
