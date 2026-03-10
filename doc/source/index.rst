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
   api_docs_serverless
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

Compatibility Policy
--------------------
PyDynamicReporting uses plain SemVer for package versions, but product
compatibility is a separate explicit contract.

- ``0.x`` is the legacy transition line. ``0.10.x`` is the last legacy line
  tied to ADR ``26.1`` behavior.
- ``1.0.0`` is the first fully policy-driven line. Starting there, each client
  major version maps to one ADR annual product line.
- A policy-driven client major supports the bundled ADR annual line and the
  immediately previous annual line.
- Minor and patch releases stay inside the same support window.
- Every future client major advances the support window by one ADR annual line.

Under this policy:

- ``0.x`` is bundled with ADR ``26.1`` and supports ``25.*`` and ``26.*``.
- ``1.x`` is bundled with ADR ``27.1`` and supports ``26.*`` and ``27.*``.
- ``2.x`` is bundled with ADR ``28.1`` and supports ``27.*`` and ``28.*``.

ADR ``25.2`` was the last half-year release. Starting with ADR ``26.1``, each
annual line currently has only one concrete release, so ``26.*`` currently
means ``26.1``, ``27.*`` means ``27.1``, and so on.

What "Supported" Means
----------------------
In PyDynamicReporting, "supported" is an explicit compatibility contract, not a
best-effort guess.

- A supported ADR product line is inside the documented compatibility window
  for that client major release.
- Supported lines are the scope for compatibility regressions and bug fixes.
- Supported lines are covered by this repository's targeted compatibility
  checks and release validation for the declared policy.
- Unsupported lines may still work in some cases, but compatibility is not
  guaranteed.
- When service-mode or serverless install detection finds an ADR product line
  outside the supported window, PyDynamicReporting warns instead of silently
  treating it as fully supported.

Install Detection Defaults
--------------------------
If you do not pass ``ansys_version`` explicitly, PyDynamicReporting uses an
install-facing default search order that is separate from the public support
contract.

- The current default released install target is ``261``.
- Implicit install discovery probes ``261`` first, then ``251``, then ``271``.
- ``271`` remains available when you request it explicitly, but it is not the
  default install search target.

The legacy package constants ``DEFAULT_ANSYS_VERSION``, ``ansys_version``,
``__ansys_version__``, and ``__ansys_version_str__`` remain install-facing
compatibility shims for existing imports and runtime path resolution. They do
not define the public support contract.

Serverless External Python Environments
---------------------------------------
When Serverless ADR runs from an external Python virtual environment, the
client-side Django dependency set is combined with the Django settings and apps
shipped inside the installed ADR product release.

This means that external virtual environments should be treated as a versioned
compatibility boundary.

- Install the package together with the constraints file that matches the ADR
  product release you are targeting.
- Keep one external serverless virtual environment per supported ADR product
  release family.
- Prefer the product-controlled Python environment when you do not need a
  standalone venv.

The repository also includes a settings compatibility shim for known serverless
setting transitions, but that shim is only a safety net. It is not a
replacement for using dependency constraints that match the target ADR
installation.

For the detailed serverless caveats and dependency-drift explanation, see
:doc:`serverless/caveats`.

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
