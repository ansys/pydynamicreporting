*************
API reference
*************

Ansys Dynamic Reporting contains a low-level API that allows you to access
all the available features and properties in full detail. While this low-level
API is very powerful, it can also be quite complex to use and it requires a
steep learning curve. For a comprehensive description of this API, see
the section :ref:`Low Level Python API <lowlevel>`.

The goal of PyDynamicReporting is to provide an easier, more Pythonic way to
start or connect to an Ansys Dynamic Reporting service so that you do not need
to understand the intricacies of Ansys Dynamic Reporting to manipulate its
database and reports. For this reason, the PyDynamicReporting API provides only a subset
of features, which are wrapped in such a way as to make the workflow easier.

If you are interested in extended control of all options and features of
Ansys Dynamic Reporting, you can use its low-level API in conjunction
with the PyDynamicReporting API.

To use PyDynamicReporting to start or connect to an Ansys Dynamic Reporting service,
you create an instance of the ``Service`` class. You then use this instance to
query the database, to add and delete items, and to visualize reports.

Items inside the Ansys Dynamic Reporting service are represented as instances
of the ``Item`` class. You use methods in both the ``Item`` class and ``Service``
class to create, query, and modify items.

Lastly, you create and use ``Report`` instances to access reports in Ansys
Dynamic Reporting.

Compatibility information
=========================

The package exposes its client-to-product compatibility contract so
applications can inspect the bundled ADR release and supported annual product
lines:

.. code-block:: python

   import ansys.dynamicreporting.core as adr

   compatibility = adr.get_compatibility_info()
   print(compatibility.client_version)
   print(compatibility.bundled_product_release)
   print(compatibility.supported_product_lines)
   print(compatibility.support_policy)

The same values are available as ``BUNDLED_PRODUCT_RELEASE``,
``SUPPORTED_PRODUCT_LINES``, and ``SUPPORTED_PRODUCT_RELEASE_POLICY``.
``DEFAULT_ANSYS_INSTALL_RELEASE`` and ``DEFAULT_ANSYS_INSTALL_VERSION``
describe the default local-install lookup target; they are separate from the
supported product window.

.. autosummary::
   :toctree: _autosummary/

   ansys.dynamicreporting.core.ProductCompatibility
   ansys.dynamicreporting.core.get_compatibility_info
   ansys.dynamicreporting.core.product_release_to_display_string
   ansys.dynamicreporting.core.product_release_to_short_label

Logging utility
===============

.. autosummary::
   :toctree: _autosummary/

   ansys.dynamicreporting.core.adr_utils.get_logger


.. autosummary::
   :toctree: _autosummary/

   ansys.dynamicreporting.core.Item
   ansys.dynamicreporting.core.Service
   ansys.dynamicreporting.core.Report

.. toctree::
   lowlevelapi/index.rst

