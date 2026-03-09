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

You can also `view <https://cheatsheets.docs.pyansys.com/pydynamicreporting_cheat_sheet.png>`_
or `download <https://cheatsheets.docs.pyansys.com/pydynamicreporting_cheat_sheet.pdf>`_
the PyDynamicReporting cheat sheet. This one-page reference provides syntax
rules and commands for using PyDynamicReporting.

On the `PyDynamicReporting Issues <https://github.com/ansys/pydynamicreporting/issues>`_
page, you can create issues to report bugs and request new features. On the
`Discussions <https://discuss.ansys.com/>`_ page on the Ansys Developer portal,
you can post questions, share ideas, and get community feedback.

To reach the project support team, email
`pyansys.core@ansys.com <pyansys.core@ansys.com>`_.

Installation
------------
The ``pydynamicreporting`` package supports Python 3.10 through 3.12 on
Windows and Linux. It is currently available on the PyPI
`repository <https://pypi.org/project/ansys-dynamicreporting-core/>`_.

For the base client package, run:

.. code::

   pip install ansys-dynamicreporting-core

This installs the core client dependencies needed for service-mode usage.

Optional ``ext`` dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Some functionality depends on an extended dependency set, including the
Serverless stack and related data/export integrations. These dependencies are
published as the optional ``ext`` extra in ``pyproject.toml``.

Install the package with the optional extra from PyPI using:

.. code::

   pip install "ansys-dynamicreporting-core[ext]"

If you are installing from a local checkout instead of PyPI, use:

.. code::

   pip install ".[ext]"

Use the ``ext`` extra when you need functionality from
``ansys.dynamicreporting.core.serverless`` or other features that rely on this
extended stack. If you only need the base ADR client package, the standard
installation without extras is sufficient.

Serverless release constraints
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When you use Serverless ADR from an external Python virtual environment, the
venv's Django-related packages are combined with the Django settings and apps
that ship inside the installed ADR product release. If those two sides drift
apart, ``ADR.setup()`` can fail during ``django.setup()`` even though the
client environment and the product installation are each valid on their own.

To keep the checked-in ``uv.lock`` solvable, the ``ext`` extra is intentionally
a broad compatibility envelope rather than a set of mutually exclusive,
release-specific extras. Product-line-specific dependency pins live under
``constraints/`` and should be applied when creating a serverless venv for a
specific ADR release.

For example, for an ADR ``27.1`` / 2027 R1 / ``v271`` target from a source
checkout, use:

.. code:: bash

   pip install -c constraints/v271.txt ".[ext]"

If you are installing from PyPI instead of a local checkout, download the
matching constraints file from this repository and use:

.. code:: bash

   pip install -c /path/to/v271.txt "ansys-dynamicreporting-core[ext]"

Recommended practice is to keep one external serverless virtual environment
per supported ADR product release family.

Developer installation
^^^^^^^^^^^^^^^^^^^^^^
This project uses `uv <https://github.com/astral-sh/uv>`_ for fast dependency
management and virtual environment handling. To set up a development
environment:

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

This creates an "editable" installation that lets you develop and test
PyDynamicReporting simultaneously.

If you want an editable install with only the optional ADR extension
dependencies, you can also run:

.. code::

   uv sync --frozen
   uv run python -m pip install -e ".[ext]"

**Developer workflow note**

After making changes, run the pre-commit hooks (via ``uv``) before committing.
Otherwise, the code-style CI check will fail.

.. code::

   make check

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

**Updating Dependencies**

If you see an error like ``The lockfile at `uv.lock` needs to be updated``,
run the following commands to update the lock file:

.. code::

   uv sync --upgrade --all-extras
   uv lock --upgrade

Then make sure to commit the updated ``uv.lock`` file.
This ensures your local environment is synchronized with the latest dependency
constraints.

For serverless compatibility work, keep the optional ``ext`` extra broad enough
to span the supported ADR product lines and place release-specific pins in
``constraints/``. Adding mutually incompatible per-release extras breaks
``uv lock`` because the repository maintains a single checked-in ``uv.lock``.

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

**Note**: Deploy and upload steps are guarded with ``if: ${{ !env.ACT }}`` to
prevent them from running locally. Only build and validation steps will
execute with ``act``.

Creating a Release
------------------

This project now uses **tag-driven releases** and **dynamic versions** powered
by ``hatch-timestamp-version`` (based on ``hatch-vcs``). Stable releases are
cut from **Git tags** (``vX.Y.Z``). Development builds use **UTC timestamped**
versions derived from the most recent tag. **Release branches are no longer
needed**; the version is always derived from tags.

Versioning model
^^^^^^^^^^^^^^^^

- **Stable releases**: The version is the exact **Git tag** (for example,
  ``v0.10.0`` -> package version ``0.10.0``).
- **Development builds**: Version is computed from the latest tag **plus a
  timestamp**, for example ``0.10.1.devYYYYMMDDHHMMSS``.
- No manual editing of ``pyproject.toml`` for versions;
  ``[tool.hatch.version]`` drives everything.
- **Product compatibility** is declared separately from SemVer. The package
  version stays plain SemVer, while the package metadata declares the bundled
  ADR product release and the supported annual product lines.

Product compatibility policy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Each client major line represents one ADR compatibility epoch.
- A client line supports the current ADR annual product line and the previous
  annual product line.
- Minor and patch releases do not widen the compatibility window.
- A new client major advances the window by one annual product line and drops
  the oldest supported line.

The current released client line is bundled with ADR ``26.1`` and supports the
``25.*`` and ``26.*`` annual product lines. If ADR later ships ``26.2``,
that release is still covered by the same client compatibility epoch.

The legacy package constants ``DEFAULT_ANSYS_VERSION``, ``ansys_version``,
``__ansys_version__``, and ``__ansys_version_str__`` remain install-facing
compatibility shims for existing imports and runtime path resolution. They are
not the public compatibility contract.
Implicit install discovery probes the current internal baseline first
(``271``), then falls back through released installs such as ``261`` and
``251`` so current users are not blocked on a single unreleased default.

For example, under this policy:

- ``1.0.0`` could bundle ADR ``27.1`` and support ``26.*`` and ``27.*``.
- ``1.2.0`` and ``1.2.2`` would still support ``26.*`` and ``27.*``.
- ``2.0.0`` could bundle ADR ``28.1`` and support ``27.*`` and ``28.*``,
  dropping support for ``26.*``.

What the automation does
^^^^^^^^^^^^^^^^^^^^^^^^

- **Create Draft Release** (on tag push): builds wheels/sdist and opens a
  **draft GitHub Release** attaching artifacts.
- **Publish Release** (when the GitHub Release is **published**): uploads
  artifacts to **PyPI** via Trusted Publisher, then builds and deploys
  **stable docs**.
- **Failure notifications**: posts to Microsoft Teams on workflow failure.

Prerequisites
^^^^^^^^^^^^^

- Ensure ``CHANGELOG.md`` has a section for the release **dated today**. The
  helper script validates this.
- Working tree must be **clean** (no uncommitted changes).
- CI secrets for publishing and docs deployment are configured in GitHub.

Cutting a Stable Release
^^^^^^^^^^^^^^^^^^^^^^^^

1. Make sure your ``CHANGELOG.md`` entry for the version is dated **today**.
   This check runs automatically from ``make tag``.
2. Create and push the release tag:

   .. code-block:: bash

      make tag

   This runs all safety checks, validates the changelog date, and pushes the
   Git tag (for example, ``v0.10.0``).
3. Once the tag is pushed:

   - The **Create Draft Release** workflow builds the package and opens a
     **draft GitHub Release** with artifacts.
   - After reviewing and finalizing notes, publish the GitHub Release.

4. Publishing the release automatically triggers the **Release** workflow,
   which:

   - Uploads artifacts to **PyPI** using Trusted Publisher.
   - Builds and deploys the **stable documentation**.

Patch releases
^^^^^^^^^^^^^^

- For a patch, update the changelog, ensure the working tree is clean, then
  run ``make tag`` again. This tags the next patch version determined by
  ``hatch version`` from your last tag.
- No separate "release branch" is required; the version is derived from tags.

Local dry-runs (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^
You can use ``act`` to exercise non-publishing parts locally. Steps that
publish or deploy are already guarded in workflows (for example, with
``if: ${{ !env.ACT }}``). Build and validation steps still run:

.. code-block:: bash

   act -W '.github/workflows/release.yml' -j release --bind

CI workflows (reference)
^^^^^^^^^^^^^^^^^^^^^^^^

- **.github/workflows/create_draft_release.yml**

  - Triggers on tag push ``v*`` or manual dispatch.
  - Builds artifacts and opens a **draft** GitHub Release attaching
    ``dist/*``.

- **.github/workflows/release.yml**

  - Triggers on a **published** GitHub Release or manual dispatch.
  - Rebuilds and validates, downloads artifacts, **publishes to PyPI**,
    builds docs, and **deploys stable docs**.

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
Releases are blocked if today's dated entry is missing:

.. code-block:: text

   ERROR: CHANGELOG.md is not ready for release.
      Expected line: ## [0.10.0] - YYYY-MM-DD
      Tip: Check if it's still marked as '[Unreleased]' and update it to today's date.

Troubleshooting
^^^^^^^^^^^^^^^

- **"No Git tag found" during checks**: Create a tag via ``make tag`` (or
  ``git tag vX.Y.Z && git push origin vX.Y.Z``).
- **Draft already exists**: The draft release is unique per tag. Delete or
  publish the existing one, or bump the tag properly.
- **Version mismatch**: ``hatch version`` determines the version from the last
  tag. Ensure you pushed the intended tag and your clone has all tags
  (``git fetch --tags``).

Dependencies
------------
To use PyDynamicReporting, you must have a locally installed and licensed copy
of Ansys 2023 R2 or later.

To use PyDynamicReporting Serverless
(``ansys.dynamicreporting.core.serverless``), you must have a locally
installed and licensed copy of Ansys 2025 R1 or later.

Dependency compatibility when using Serverless from external Python
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PyDynamicReporting's **Serverless** mode
(``ansys.dynamicreporting.core.serverless``) is frequently used from a
**standalone Python virtual environment** (a "client" environment) while
targeting an **installed ADR product release** (the "server" installation).

This creates a two-sided compatibility surface:

- **Client environment**: dependencies installed via ``pip`` or ``uv`` into a
  virtual environment, for example ``Django`` and ``django-guardian``.
- **Server installation**: the ADR product's Python/Django code and settings
  shipped with a specific annual release.

Because ADR product releases ship on a slower cadence (typically **yearly**)
while the client library and its dependencies may update more often, it is
possible for the **client dependency versions** to drift ahead of what an
**older product release** expects.

Compatibility matrix (client deps vs server deps)
"""""""""""""""""""""""""""""""""""""""""""""""""

In practice, the system behaves like this, where "deps" includes packages like
``Django`` and ``django-guardian``:

1. **Old client deps <-> New server deps**
   Often works today as long as newer server-side
   dependencies/configuration only *add* capabilities and do not remove old
   behavior. This can break in the future if the server removes APIs or
   behavior that the old client relies on.
2. **New client deps <-> Old server deps** (**current failure mode**)
   This is the most common and disruptive breakage: the client installs newer
   dependencies that have removed or hardened behavior, while the older
   product release still uses legacy configuration or APIs. Example: newer
   ``django-guardian`` raises at import time when it sees the legacy setting
   ``GUARDIAN_MONKEY_PATCH``, requiring ``GUARDIAN_MONKEY_PATCH_USER``
   instead. If an older product release still sets the old key,
   ``django.setup()`` fails during ``apps.populate()``.
3. **Old client deps <-> Old server deps**
   Works (matched expectations).
4. **New client deps <-> New server deps**
   Works (matched expectations).

Why this matters
""""""""""""""""

The failing class (#2) can happen even when the client and server are both
"correct" in isolation:

- The **client** is correct to install current dependencies.
- The **older product release** is correct for the dependencies and
  configurations it shipped with at the time.

But the combined system fails because **import-time settings validation** (or
removed APIs) turns a mismatch into a hard crash before ADR can apply any
runtime logic.

Recommended long-term strategy (avoid "dependency drift" failures)
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

To prevent recurring breakages of class (#2), treat "Serverless in external
Python" as a **compatibility boundary** that must be managed explicitly.
Options include:

- **Prefer running with the product-controlled Python environment** when
  targeting an installed ADR product release. The product controls the
  dependency set, eliminating client-side drift.
- **Provide and document per-product dependency constraints** (lockfiles or
  constraints files) for supported product release lines, and test them in CI.
  This ensures that external virtual environment installs resolve to a
  dependency set known to be compatible with that product line.
- **Maintain an explicit compatibility policy** (for example, "support last N
  annual ADR product releases") and enforce it with runtime
  detection/fingerprinting of the targeted product release, clear error
  messages, and CI matrix coverage for each supported product line.

Current repository mitigation
"""""""""""""""""""""""""""

This repository currently contains two concrete mitigations for the most common
"new client deps <-> old server deps" failure mode:

- ``ADR.setup()`` sanitizes imported product settings before calling
  ``django.setup()`` so known setting transitions do not fail at import time.
  The current shim translates ``GUARDIAN_MONKEY_PATCH`` to
  ``GUARDIAN_MONKEY_PATCH_USER`` when newer ``django-guardian`` is installed,
  and migrates ``DEFAULT_FILE_STORAGE`` to ``STORAGES["default"]`` for newer
  Django releases.
- Release-specific dependency profiles live in ``constraints/``. The current
  example, ``constraints/v271.txt``, targets ADR ``27.1`` / 2027 R1 / ``v271``.

These mitigations reduce breakage, but the primary recommendation is still to
install the ``ext`` extra together with the constraints file that matches the
target ADR release.

.. note::

   The key goal is to ensure that an external virtual environment does **not**
   silently pick newer dependencies that are incompatible with an older
   installed product release.

   This dependency-constraints guidance is complementary to the client
   compatibility contract: the current released client line is bundled with ADR
   ``26.1`` and supports the ``25.*`` and ``26.*`` annual product lines,
   while still using plain SemVer for package releases.

Basic usage
-----------
This code shows how to start the simplest PyDynamicReporting session:

.. code:: pycon

   >>> import ansys.dynamicreporting.core as adr
   >>> adr_service = adr.Service(ansys_installation=r"C:\\Program Files\\ANSYS Inc\\v232\\")
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
