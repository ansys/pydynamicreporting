Ansys Dynamic Reporting
=======================

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

.. _Ansys Dynamic Reporting: https://nexusdemo.ensight.com/docs/html/Nexus.html

Overview
--------
This repository contains the source for ``pydynamicreporting`` - the Python API to
`Ansys Dynamic Reporting`_. ``pydynamicreporting`` provides an API to connect to an Ansys
Dynamic Reporting service and manipulate its items and reports. Ansys Dynamic Reporting
is a service that allows the user to push items of many types (image, text, 3D scenes,
table, ...) into a database, keep them organized and create dynamic reports from them.
The ``pydynamicreporting`` module gives the user full access to all these capabilities in
a natural and pythonic way. To get more information about Ansys Dynamic Reporting,
please see `the Ansys Dynamic Reporting documentation page`_.


.. _the Ansys Dynamic Reporting documentation page: https://nexusdemo.ensight.com/docs/html/Nexus.html



Installation
------------
Currently, ``pydynamicreporting`` is only available on the ANSYS Azure PyPI.

Install with:

.. code::

   pip install --pre ansys-dynamicreporting-core --index-url=https://<PAT>@pkgs.dev.azure.com/pyansys/_packaging/pyansys/pypi/simple/

where `PAT` is private access token. Read how to obtain it `here <https://dev.docs.pyansys.com/dev/how-to/releasing.html#downloading-artifacts>`_.


Development
-----------

To clone and install in development mode:

.. code::

   git clone https://github.com/ansys/pydynamicreporting
   cd pydynamicreporting
   pip install virtualenv
   virtualenv venv  # create virtual environment
   source venv/bin/activate  # (.\venv\Scripts\activate for Windows shell)
   make install-dev  # install pydynamicreporting in editable mode

This creates an 'editable' installation that lets you
develop and test pydynamicreporting at the same time.

To build and create a production-like install of pydynamicreporting:

.. code::

   make clean  # clean
   make build   # build
   # this will replace the editable install done previously. If you don't want to replace,
   # switch your virtual environments to test the new install separately.
   make install
   # you can skip the steps above and just do 'make all'
   make smoketest  # test import

Pre-commit setup
^^^^^^^^^^^^^^^^

``pre-commit`` is a multi-language package manager for pre-commit hooks.

To install pre-commit into your git hooks, run:

.. code::

   pre-commit install

pre-commit will now run on every commit. Every time you clone a project using pre-commit, this should always be the first thing you do.

If you want to manually run all pre-commit hooks on a repository, run:

.. code::

   pre-commit run --all-files

This will run a bunch of formatters on your source files.

To run individual hooks, use:

.. code::

   pre-commit run <hook_id>

``<hook_id>`` can be obtained from ``.pre-commit-config.yaml``.
The first time pre-commit runs on a file, it will automatically download, install, and run the hook.


Local GitHub actions
^^^^^^^^^^^^^^^^^^^^

To simulate GitHub Actions on your local desktop (recommended), install `act <https://github.com/nektos/act#readme>`_.
To run a job, for example - ``docs`` from ``ci_cd.yml``, use:

.. code::

   act -j docs

Deploy and upload steps **must always** be ignored. If not, please add ``if: ${{ !env.ACT }}`` to the workflow step (and commit if required) before running.


Usage
-----
The simplest ``pydynamicreporting`` session may be started like this:

.. code:: pycon

    >>> import ansys.dynamicreporting.core as adr
    >>> adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v231")
    >>> ret = adr_service.connect()
    >>> my_img = adr_service.create_item()
    >>> my_img.item_image = "image.png"
    >>> adr_service.visualize_report()

Dependencies
------------
You will need a locally installed and licensed copy of Ansys to run Ansys Dynamic Reporting with the
first supported version being Ansys 2023 R2.

Documentation and Issues
------------------------
Please see the latest release `documentation <https://dynamicreporting.docs.pyansys.com>`_
page for more details.

Please feel free to post issues and other questions at `pydynamicreporting Issues
<https://github.com/ansys/pydynamicreporting/issues>`_.  This is the best place
to post questions and code.

License
-------
``pydynamicreporting`` is licensed under the MIT license.

This module, ``ansys-dynamicreporting-core`` makes no commercial claim over Ansys whatsoever.
This tool extends the functionality of ``Ansys Dynamic Reporting`` by adding a remote Python
interface to Ansys Dynamic Reporting without changing the core behavior or license of the original
software. The use of Ansys Dynamic Reporting through the ``pydynamicreporting``
interface requires any license that allows the use of stand alone Ansys Dynamic Reporting.

To get a copy of Ansys, please visit `Ansys <https://www.ansys.com/>`_.
