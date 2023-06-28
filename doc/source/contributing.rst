.. _ref_contributing:

==========
Contribute
==========
Overall guidance on contributing to a PyAnsys library appears in the
`Contributing <https://dev.docs.pyansys.com/how-to/contributing.html>`_ topic
in the *PyAnsys Developer's Guide*. Ensure that you are thoroughly familiar with
this guide before attempting to contribute to PyDnamicReporting.


Post issues
-----------
Use the `PyDnamicReporting Issues <https://github.com/ansys/pydynamicreporting/issues>`_
page to submit questions, report bugs, and request new features.

To reach the project support team, email `pyansys.core@ansys.com <pyansys.core@ansys.com>`_.

Adhere to code style
----------------------
PyDynamicReporting is compliant with the `Coding style
<https://dev.docs.pyansys.com/coding-style/index.html>`_ described in the
*PyAnsys Developer's Guide*. It uses the tool
`pre-commit <https://pre-commit.com/>`_ to align the code style. You can
install and activate this tool with these commands:

.. code:: bash

   python -m pip install pre-commit
   pre-commit install


You can then directly execute `pre-commit <https://pre-commit.com/>`_ with
this command:

.. code:: bash

    pre-commit run --all-files --show-diff-on-failure

