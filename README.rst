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
The ``pydynamicreporting`` package supports Python 3.10 through 3.13 on
Windows and Linux. It is currently available on the PyPi
`repository <https://pypi.org/project/ansys-dynamicreporting-core/>`_.

To install the package, simply run

.. code::

   pip install ansys-dynamicreporting-core

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

To build and create a production-like installation on Windows (not required on other OSes),
first install `chocolatey <https://chocolatey.org/install>`_. Then:

.. code::

   choco install make  # install make on Windows
   make clean  # clean
   make build   # build
   # this replaces the editable installation done previously. If you don't want to replace,
   # switch your virtual environments to test the new install separately.
   make install
   # you can skip the steps above and just do 'make all'
   make smoketest  # test import

Local GitHub Actions
^^^^^^^^^^^^^^^^^^^^
To run GitHub Actions on your local desktop (recommended), install the
`act <https://github.com/nektos/act#readme>`_ package.

.. code::

   choco install act-cli

To run a job, such as the ``style`` job from the ``ci_cd.yml`` file, use
this command, where ``style`` is the job name:

.. code::

   act -W '.github/workflows/ci_cd.yml' -j style --bind


Deploy and upload steps **must always** be ignored. If they are not ignored,
before running GitHub Actions locally, add ``if: ${{ !env.ACT }}`` to the
workflow step and commit this change if required.

Local tests
^^^^^^^^^^^
To run tests on your local desktop (recommended), use the `make` target
`test-dev`. This target runs the tests in the same way as GitHub Actions but using
a local Ansys installation instead of Docker. You must specify the path to your Ansys
installation and the test file you are trying to run.

.. code::

   make test-dev TEST_FILE="tests/test_service.py" INSTALL_PATH="C:\Program Files\ANSYS Inc\v252"

Note that any tests that require Docker will obviously fail.

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