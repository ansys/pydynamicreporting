*****************
API documentation
*****************

``pydynamicreporting``
~~~~~~~~~~~~~~~~~~~~~~
 .. _here: https://nexusdemo.ensight.com/docs/html/Nexus.html?ExternalPythonAPI.html

The Ansys Dynamic Reporting product contains a low-level API that
gives access to all the features with a high level of detail.
An extensive description of that API can be found  `here`_

The goal of the ``pydynamicreporting`` library is to allow the use to have
an easier,  more pythonic way to connect / start an Ansys Dynamic Reporting
service and manipulate its database and reports, without the need to
understand the intricacy of the Ansys Dynamic Reporting project. For this reason,
only a subset of features are available through this API, wrapped in such a way
to make the workflow easier for average user. If you are interested in extended
control of all the options and features of Ansys Dynamic Reporting, please
know that the low-level API can be used in conjunction with
``pydynamicreporting``.

To connect to or start an Ansys Dynamic Reporting service, create an instance
of the Service class. This instance can also be used to query the database,
add, or delete items, and visualize reports.

Items inside the Ansys Dynamic Reporting service are represented as instances
of the Item class. These items can be created, queried, or modified via
methods in the ``Item`` and in the ``Service`` class.

(work in progress) The Ansys Dynamic Reporting reports can easily be
accessed via Report instances.

.. autosummary::
   :toctree: _autosummary/

   ansys.dynamicreporting.core.Item
   ansys.dynamicreporting.core.Service
   ansys.dynamicreporting.core.Report
