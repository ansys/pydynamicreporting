PyDynamicReporting
==================

|pyansys| |python| |pypi| |GH-CI| |bandit| |MIT| |black|

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

.. |bandit| image:: https://img.shields.io/badge/security-bandit-yellow.svg
    :target: https://github.com/PyCQA/bandit
    :alt: Security Status

.. |MIT| image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: MIT

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg?style=flat
   :target: https://github.com/psf/black
   :alt: Black

.. _Nexus: https://nexusdemo.ensight.com/docs/html/Nexus.html

Overview
--------
The ``pydynamicreporting`` repository contains the Python client library for
Ansys Dynamic Reporting, previously documented as `Nexus`_. Ansys Dynamic
Reporting is a service for pushing items of many types, including images, text,
3D scenes, and tables, into a database, where you can keep them organized and
create dynamic reports from them. When you use PyDynamicReporting to connect to
an instance of Ansys Dynamic Reporting, you have a Pythonic way of accessing all
capabilities of Ansys Dynamic Reporting.

Documentation and issues
------------------------
For comprehensive information on PyDynamicReporting, see the latest release
`documentation <https://dynamicreporting.docs.pyansys.com>`_.

On the `PyDynamicReporting Issues <https://github.com/ansys/pydynamicreporting/issues>`_
page, you can create issues to submit questions, report bugs, and request new
features. This is the best place to post questions and code.

Installation
------------
The ``pydynamicreporting`` package supports Python 3.7 through 3.11 on
Windows and Linux. It is currently available only on the Ansys private
repository at `PyAnsysPyPI <https://pkgs.dev.azure.com/pyansys/_packaging/pyansys/pypi>`_.

Installing from this private repository requires a PAT (private access
token). For information on obtaining a PAT, see `Release and publishing
<https://dev.docs.pyansys.com/dev/how-to/releasing.html#downloading-artifacts>`_
in the *PyAnsys Developer's Guide*.

To install the package from the Ansys private repository, run this code,
where ``<PAT>`` is the obtained token:

.. code::

   pip install --pre ansys-dynamicreporting-core --index-url=https://<PAT>@pkgs.dev.azure.com/pyansys/_packaging/pyansys/pypi/simple/


Once the ``pydynamicreporting`` package is publicly available on GitHub, two modes
of installation are available:

- Developer installation
- User installation


The code provided for both installation modes use a `virtual environment
<https://docs.python.org/3/library/venv.html>`_.

Developer installation
^^^^^^^^^^^^^^^^^^^^^^
To clone and install the ``pydynamicreporting`` package in development mode,
run this code:

.. code::

   git clone https://github.com/ansys/pydynamicreporting
   cd pydynamicreporting
   pip install virtualenv
   virtualenv venv  # create virtual environment
   source venv/bin/activate  # (.\venv\Scripts\activate for Windows shell)
   make install-dev  # install pydynamicreporting in editable mode


The preceding code creates an "editable" installation that lets you develop and test
PyDynamicReporting at the same time.

User installation
^^^^^^^^^^^^^^^^^
To build and create a production-like installation for use, run this code:

.. code::

   make clean  # clean
   make build   # build
   # this replaces the editable installation done previously. If you don't want to replace,
   # switch your virtual environments to test the new install separately.
   make install
   # you can skip the steps above and just do 'make all'
   make smoketest  # test import


Pre-commit setup
^^^^^^^^^^^^^^^^

`pre-commit <https://pre-commit.com/>`_ is a framework for managing and
maintaining multi-language pre-commit hooks.

To install the ``pre-commit`` package into your Git hooks, run this command:

.. code::

   pre-commit install


``pre-commit`` now runs on every commit.

Each time you clone a project, installing the ``pre-commit`` package
should always be the first thing that you do.

If you want to manually run all pre-commit hooks on a repository, run
this command:

.. code::

   pre-commit run --all-files


The preceding command runs a bunch of formatters on your source files.

To run an individual hook, obtain the hook ID from the project's
``.pre-commit-config.yaml`` file and then run this code,
where ``<hook_id>`` is the obtained ID:

.. code::

   pre-commit run <hook_id>


The first time ``pre-commit`` runs on a file, it automatically downloads,
installs, and runs the hook.


Local GitHub Actions
^^^^^^^^^^^^^^^^^^^^
To run GitHub Actions on your local desktop (recommended), install the
`act <https://github.com/nektos/act#readme>`_ package.

To run a job, such as the ``docs`` job from the ``ci_cd.yml`` file, use
this command, where ``docs`` is the job name:

.. code::

   act -j docs


Deploy and upload steps **must always** be ignored. If they are not ignored,
before running GitHub Actions locally, add ``if: ${{ !env.ACT }}`` to the
workflow step and commit this change if required.

Dependencies
------------
To use PyDynamicReporting, you must have a locally installed and licensed copy
of Ansys 2023 R2 or later.

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
adding a Python interface to Ansys Dynamic Reproting without changing
the core behavior or license of the original software. The use of
PyDynamicReporting requires a legally licensed copy of an Ansys product
that supports Ansys Dynamic Reporting.

To get a copy of Ansys, visit the `Ansys <https://www.ansys.com/>`_ website.
