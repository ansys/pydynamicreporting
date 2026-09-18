*************
API reference
*************

Ansys Dynamic Reporting contains a low-level API that allows the user to access
a;; the available features and properties in full detail. While this low-level
API is very powerful, it can also be quite complex to use and it requires a
steep learning curve. For a comprehensive description of this API, see
`External Python API <https://nexusdemo.ensight.com/docs/html/Nexus.html?ExternalPythonAPI.html>`_
in the documentation for Ansys Dynamic Reporting.

The goal of PyDynamicReporting is to provide an easier, more Pythonic way to
start or connect to an Ansys Dynamic Reporting service so that you do not need
to understand the intricacies of Ansys Dynamic Reporting to manipulate its
database and reports. For this reason, the PyDynamicReporting API provides only a subset
of features, which are wrapped in such a way as to make the workflow easier.

If you are interested in extended control of all options and features of
Ansys Dynamic Reporting, you can use its low-level API in conjunction
with the PyDnamicReporting API.

To use PyDynamicReporting to start or connect to an Ansys Dynamic Reporting service,
you create an instance of the ``Service`` class. You then use this instance to
query the database, to add and delete items, and to visualize reports.

Items inside the Ansys Dynamic Reporting service are represented as instances
of the ``Item`` class. You use methods in both the ``Item`` class and ``Service``
class to create, query, and modify items.

Lastly, you create and use ``Report`` instances to access reports in Ansys
Dynamic Reporting.

.. autosummary::
   :toctree: _autosummary/

   ansys.dynamicreporting.core.Item
   ansys.dynamicreporting.core.Service
   ansys.dynamicreporting.core.Report
