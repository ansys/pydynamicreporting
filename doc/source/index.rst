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

.. _compatibility_policy:

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
- ``1.0.x`` is bundled with ADR ``27.1`` (27R1).
- ``1.1.0`` development targets ADR ``27.2`` (27R2). Its bundled-release
  metadata identifies ``27.2`` while retaining support for ``26.*`` and
  ``27.*``, including 27R1.
- ``2.x`` would be bundled with ADR ``28.1`` and support ``27.*`` and ``28.*``.

... and so on.

An annual product line can contain multiple releases: ``27.*`` includes
``27.1`` and ``27.2``. The supported annual lines stay the same when a minor
client release advances the bundled ADR release within that window.

Development and Maintenance Branches
------------------------------------
``main`` currently targets PyDynamicReporting ``1.1.0`` for ADR ``27.2``.
``stable/27.1`` holds the frozen 27R1 line and its ``1.0.x`` release fixes.
Create ``stable/27.2`` for ``1.1.x`` when 27R2 freezes, then use ``main`` for
the next development release. The legacy ``stable/26.x`` name is retained.

Development builds on ``main`` use the next minor version after the nearest reachable
tag with a UTC timestamp, such as ``1.1.0.devYYYYMMDDHHMMSS``. Exact release
tags remain authoritative for published versions. See the README's
maintenance branch policy for the version-scheme setting used when freezing
a new maintenance line.

What "Supported" Means
----------------------
In PyDynamicReporting, "supported" is an explicit compatibility contract, not a
best-effort guess.

- A supported ADR product line is inside the documented compatibility window
  for that client major release.
- Supported lines are the scope for compatibility regressions and bug fixes.
- Supported lines are covered by this repository's targeted compatibility
  checks and release validation for the declared policy.
- Some features can have a narrower product requirement within the supported
  window. For example, browser PDF export requires ADR ``27.1`` or newer
  because the required browser binary is shipped with ADR product line ``27``
  and later.
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

Implicit install discovery tries the default install line first, then the
previous annual line when the default is unavailable. Request an older layout
explicitly if you need one.

During 27R2 development, the bundled-release target is ``27.2``, but implicit
install discovery still tries ``27.1`` followed by ``26.1``. This preserves
the existing default installation behavior while 27R2 is unreleased. Select
``ansys_version=272`` explicitly when using a 27R2 development installation.

Serverless External Python Environments
---------------------------------------
When Serverless ADR runs from an external Python virtual environment, the
client-side dependency set is combined with the set shipped
inside the installed ADR product release.

This means that external virtual environments should be treated as a versioned
compatibility boundary.

- For the current ADR line bundled with a client major release, install the
  package normally unless your workflow needs stricter pins.
- For the previous supported ADR line, use the matching constraints file when
  one is provided. For example, both ``1.0.x`` and ``1.1.x`` support ADR
  ``26.1`` and can use ``constraints/v261.txt`` when targeting that release.
- Python 3.14 is supported with ADR ``27.1``. Use Python 3.12 with the ADR
  ``26.1`` constraint profile.
- Keep one external serverless virtual environment per supported ADR product
  release family.

The repository also includes a settings compatibility shim for known
setting transitions. That shim can patch known mismatches, but external-venv
compatibility remains bounded by the target ADR release and the dependencies
installed in that environment.

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
