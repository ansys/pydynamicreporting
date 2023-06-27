*************
API reference
*************

Ansys Dynamic Reporting contains a low-level API that gives access to all features
with a high level of detail. An extensive description of this API can be found in
`External Python API <https://nexusdemo.ensight.com/docs/html/Nexus.html?ExternalPythonAPI.html>`_
in the documentation for Ansys Dynamic Reporting.

The goal of PyDynamicReporting is to provide an easier, more Pythonic way to
connect to and start an Ansys Dynamic Reporting service and manipulate its database
and reports without needing to understand the intricacies of Ansys Dynamic Reporting.
For this reason, the PyDynamicReporting API provoides only a subset of features,
wrapping them in such a way as to make the workflow easier.

If you are interested in extended control of all options and features of
Ansys Dynamic Reporting, you can use the low-level API in conjunction
with PyDnamicReporting.

To use PyDynamicReporting to connect to or start an Ansys Dynamic Reporting service,
you create an instance of the ``Service`` class. You can then use this instance to
query the database, add or delete items, and visualize reports.

Items inside the Ansys Dynamic Reporting service are represented as instances
of the ``Item`` class. You can create, query, or modify these items using
methods in the ``Item`` and ``Service`` classes.

Lastly, you can easily access reports in Ansys Dynamic Reporting via ``Report``
instances.

.. autosummary::
   :toctree: _autosummary/

   ansys.dynamicreporting.core.Item
   ansys.dynamicreporting.core.Service
   ansys.dynamicreporting.core.Report
