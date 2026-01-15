PyDynamicReporting
==================

|pyansys| |python| |pypi| |GH-CI| |cov| |MIT| |black|

.. |pyansys| image:: https://img.shields.io/badge/Py-Ansys-ffc107.svg?labelColor=black&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAABDklEQVQ4jWNgoDfg5mD8vE7q/3bpVyskbW0sMRUwofHD7Dh5OBkZGBgW7/3W2tZpa2tLQEOyOzeEsfumlK2tbVpaGj4N6jIs1lpsDAwMJ278sveMY2BgCA0NFRISwqkhyQ1q/Nyd3zg4OBgYGNjZ2ePi4rB5loGBhZnhxTLJ/9ulv26Q4uVk1NXV/f///////69du4Zdg78lx//t0v+3S88rFISInD59GqIH2esIJ8G9O2/XVwhjzpw5EAam1xkkBJn/bJX+v1365hxxuCAfH9+3b9/+////48cPuNehNsS7cDEzMTAwMMzb+Q2u4dOnT2vWrMHu9ZtzxP9vl/69RVpCkBlZ3N7enoDXBwEAAA+YYitOilMVAAAAAElFTkSuQmCC
   :target: https://docs.pyansys.com/
   :alt: PyAnsys

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-dynamicreporting-core?logo=pypi
   :target: https://pypi.org/project/ansys-dynamicreporting-core/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-dynamicreporting-core.svg?logo=python&logoColor=white
   :target: https://pypi.org/project/ansys-dynamicreporting-core
   :alt: PyPI

.. |GH-CI| image:: https://github.com/ansys/pydynamicreporting/actions/workflows/ci_cd.yml/badge.svg?branch=main
   :target: https://github.com/ansys/pydynamicreporting/actions?query=branch%3Amain
   :alt: GH-CI

.. |cov| image:: https://codecov.io/gh/ansys/pydynamicreporting/graph/badge.svg?token=WCAK7QRLR3
   :target: https://codecov.io/gh/ansys/pydynamicreporting
   :alt: codecov

.. |MIT| image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: MIT

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg?style=flat
   :target: https://github.com/psf/black
   :alt: Black

.. _Nexus: https://nexusdemo.ensight.com/docs/html/Nexus.html

Overview
--------
PyDynamicReporting is the Python client library for Ansys Dynamic Reporting,
previously documented as `Nexus`_. Ansys Dynamic Reporting is a service for
pushing items of many types, including images, text, 3D scenes, and tables,
into a database, where you can keep them organized and create dynamic reports
from them. When you use PyDynamicReporting to connect to an instance of
Ansys Dynamic Reporting, you have a Pythonic way of accessing all capabilities
of Ansys Dynamic Reporting.

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

Installation
------------
The ``pydynamicreporting`` package supports Python 3.10 through 3.12 on
Windows and Linux. It is currently available on the PyPi
`repository <https://pypi.org/project/ansys-dynamicreporting-core/>`_.

To install the package, simply run

.. code::

   pip install ansys-dynamicreporting-core

Developer installation
^^^^^^^^^^^^^^^^^^^^^^
This project uses `uv <https://github.com/astral-sh/uv>`_ for fast dependency management
and virtual environment handling. To set up a development environment:

**Prerequisites**

Install `uv` by following the `official installation guide <https://docs.astral.sh/uv/getting-started/installation/>`_.

You'll also need `make`:

.. code::

   # On Windows, install using chocolatey:
   choco install make

   # On Linux, make is usually pre-installed. If not, install via:
   sudo apt-get install build-essential  # Ubuntu/Debian
   sudo yum groupinstall "Development Tools"  # RHEL/CentOS/Fedora

**Clone and Install**

.. code::

   git clone https://github.com/ansys/pydynamicreporting
   cd pydynamicreporting
   make install

The ``make install`` command does the following:
- Synchronizes dependencies from ``uv.lock`` (includes all optional extras)
- Creates a ``.venv`` virtual environment automatically
- Installs the package in editable mode

This creates an "editable" installation that lets you develop and test PyDynamicReporting simultaneously.

**Available Make Commands**

The Makefile provides several useful commands:

.. code::

   make check        # Run code quality checks (pre-commit hooks)
   make version      # Display the current project version
   make build        # Build source distribution and wheel
   make check-dist   # Validate built artifacts
   make test         # Run the full test suite with coverage
   make smoketest    # Quick import test
   make docs         # Build documentation
   make clean        # Remove build artifacts and caches

**Running Tests**

To run tests with coverage reporting:

.. code::

   make test

For a quick sanity check:

.. code::

   make smoketest

Local GitHub Actions
^^^^^^^^^^^^^^^^^^^^
To run GitHub Actions on your local desktop, install the
`act <https://github.com/nektos/act#readme>`_ package:

.. code::

   choco install act-cli  # Windows
   # or: brew install act  # macOS/Linux with Homebrew

To run a specific job from the CI/CD workflow, use:

.. code::

   act -W '.github/workflows/ci_cd.yml' -j style --bind      # Run code style checks
   act -W '.github/workflows/ci_cd.yml' -j smoketest --bind  # Run smoke tests

**Note**: Deploy and upload steps are guarded with ``if: ${{ !env.ACT }}`` to prevent
them from running locally. Only build and validation steps will execute with ``act``.

Creating a Release
------------------

This project now uses **tag-driven releases** and **dynamic versions** powered by ``hatch-timestamp-version`` (based on ``hatch-vcs``). Stable releases are cut from **Git tags** (``vX.Y.Z``). Development builds use **UTC timestamped** versions derived from the most recent tag.
**Release branches are no longer needed**; the version is always derived from tags.

Versioning model
^^^^^^^^^^^^^^^^
- **Stable releases**: The version is the exact **Git tag** (for example, ``v0.10.0`` → package version ``0.10.0``).
- **Development builds**: Version is computed from the latest tag **plus a timestamp**, e.g. ``0.10.1.devYYYYMMDDHHMMSS``.
- No manual editing of ``pyproject.toml`` for versions — ``[tool.hatch.version]`` drives everything.

What the automation does
^^^^^^^^^^^^^^^^^^^^^^^^
- **Create Draft Release** (on tag push): builds wheels/sdist and opens a **draft GitHub Release** attaching artifacts.
- **Publish Release** (when the GitHub Release is **published**): uploads artifacts to **PyPI** via Trusted Publisher, then builds & deploys **stable docs**.
- **Failure notifications**: posts to Microsoft Teams on workflow failure.

Prerequisites
^^^^^^^^^^^^^
- Ensure ``CHANGELOG.md`` has a section for the release **dated today** (the helper script validates this).
- Working tree must be **clean** (no uncommitted changes).
- CI secrets for publishing and docs deploy are configured in GitHub.

Cutting a Stable Release
^^^^^^^^^^^^^^^^^^^^^^^^
1) Make sure your ``CHANGELOG.md`` entry for the version is dated **today**
   (this check runs automatically from ``make tag``).

2) Create and push the release tag:

   .. code-block:: bash

      make tag

   This runs all safety checks, validates the changelog date, and pushes the Git tag (for example, ``v0.10.0``).

3) Once the tag is pushed:
   - The **Create Draft Release** workflow builds the package and opens a **draft GitHub Release** with artifacts.
   - After reviewing and finalizing notes, **publish** the GitHub Release.

4) Publishing the release automatically triggers the **Release** workflow, which:
   - Uploads artifacts to **PyPI** using Trusted Publisher.
   - Builds and deploys the **stable documentation**.

Patch releases
^^^^^^^^^^^^^^
- For a patch, update the changelog, ensure the working tree is clean, then run ``make tag`` again (which tags the next patch version determined by ``hatch version`` from your last tag).
- No separate “release branch” is required; the version is derived from tags.

Local dry-runs (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^
You can use ``act`` to exercise non-publishing parts locally. Steps that publish or deploy are already guarded in workflows (e.g., with ``if: ${{ !env.ACT }}``). Build and validation steps still run:

.. code-block:: bash

   act -W '.github/workflows/release.yml' -j release --bind

CI workflows (reference)
^^^^^^^^^^^^^^^^^^^^^^^^
- **.github/workflows/create_draft_release.yml**
  - Triggers on: tag push ``v*``, or manual dispatch.
  - Builds artifacts and opens a **draft** GitHub Release attaching ``dist/*``.

- **.github/workflows/release.yml**
  - Triggers on: **published** GitHub Release, or manual dispatch.
  - Rebuilds/validates, downloads artifacts, **publishes to PyPI**, builds docs, and **deploys stable docs**.

CLI helpers
^^^^^^^^^^^
- Print the resolved version (dev or stable):

  .. code-block:: bash

     make version

- Build locally (sdist + wheel):

  .. code-block:: bash

     make build
     make check-dist

- Clean:

  .. code-block:: bash

     make clean

Changelog guards
^^^^^^^^^^^^^^^^
Releases are blocked if today’s dated entry is missing:

.. code-block:: text

   ❌ ERROR: CHANGELOG.md is not ready for release.
      Expected line: ## [0.10.0] - YYYY-MM-DD
      Tip: Check if it's still marked as '[Unreleased]' and update it to today's date.

Troubleshooting
^^^^^^^^^^^^^^^
- **“No Git tag found” during checks**: Create a tag via ``make tag`` (or ``git tag vX.Y.Z && git push origin vX.Y.Z``).
- **Draft already exists**: The draft release is unique per tag. Delete or publish the existing one, or bump the tag properly.
- **Version mismatch**: ``hatch version`` determines the version from the last tag; ensure you pushed the intended tag and your clone has all tags (``git fetch --tags``).


Dependencies
------------
To use PyDynamicReporting, you must have a locally installed and licensed copy
of Ansys 2023 R2 or later.

To use PyDynamicReporting Serverless (ansys.dynamicreporting.core.serverless),
you must have a locally installed and licensed copy of Ansys 2025 R1 or later.

Basic usage
-----------
This code shows how to start the simplest PyDynamicReporting session:

.. code:: pycon

    >>> import ansys.dynamicreporting.core as adr
    >>> adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v232")
    >>> ret = adr_service.connect()
    >>> my_img = adr_service.create_item()
    >>> my_img.item_image = "image.png"
    >>> adr_service.visualize_report()


License and acknowledgements
----------------------------
PyDynamicReporting is licensed under the MIT license.

PyDynamicReporting makes no commercial claim over Ansys whatsoever.
This library extends the functionality of Ansys Dynamic Reporting by
adding a Python interface to Ansys Dynamic Reporting without changing
the core behavior or license of the original software. The use of
PyDynamicReporting requires a legally licensed copy of an Ansys product
that supports Ansys Dynamic Reporting.

To get a copy of Ansys, visit the `Ansys <https://www.ansys.com/>`_ website.