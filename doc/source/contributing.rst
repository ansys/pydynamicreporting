.. _ref_contributing:

============
Contributing
============
Overall guidance on contributing to a PyAnsys library appears in the
`Contributing <https://dev.docs.pyansys.com/how-to/contributing.html>`_ topic
in the *PyAnsys Developer's Guide*. Ensure that you are thoroughly familiar with
this guide, paying particular attention to the `Coding Style
<https://dev.docs.pyansys.com/coding-style/index.html>`_ topic, before
attempting to contribute to ``pydynamicreporting``.


Posting issues
--------------
Use the `GitHub Issues <https://github.com/ansys/pydynamicreporting/issues>`_ page to
submit questions, report bugs, and request new features.


Adhering to code style
----------------------
``pydynamicreporting`` is compliant with the `PyAnsys Development Code Style Guide
<https://dev.docs.pyansys.com/coding-style/index.html>`_. It uses the tool
`pre-commit <https://pre-commit.com/>`_ to align the code style. You can
install and activate this tool with:

.. code:: bash

   python -m pip install pre-commit
   pre-commit install

At which point, you can directly execute `pre-commit <https://pre-commit.com/>`_ with:

.. code:: bash

    pre-commit run --all-files --show-diff-on-failure