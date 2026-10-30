.. _serverless_logging:

Logging
========

Serverless ADR uses the shared ``ansys.dynamicreporting.core`` logger.
PyDynamicReporting does not change the application's root logger.

Write logs to standard output
-----------------------------

Pass ``log_output="stdout"`` when constructing
:class:`~ansys.dynamicreporting.core.serverless.adr.ADR`:

.. code-block:: python

   import logging

   from ansys.dynamicreporting.core.serverless import ADR

   adr = ADR(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v261",
       db_directory=r"C:\reports\database",
       log_output="stdout",
       log_level=logging.INFO,
   )

Write logs to a file
--------------------

Any other ``log_output`` value is treated as a file path:

.. code-block:: python

   adr = ADR(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v261",
       db_directory=r"C:\reports\database",
       log_output=r"C:\reports\pydynamicreporting.log",
       log_level="DEBUG",
   )

If ``log_level`` is omitted, the existing level on the shared ADR logger is
left unchanged. If ``log_output`` is omitted, PyDynamicReporting adds no
visible output handler.

Repeated calls with the same standard-output stream or normalized file path do
not add duplicate PyDynamicReporting-owned handlers. This matters in
serverless applications that initialize more than one ADR-backed component in
the same process.

Configure the package logger directly
-------------------------------------

Use :func:`~ansys.dynamicreporting.core.adr_utils.get_logger` when logging must
be configured before constructing ``ADR``:

.. code-block:: python

   from ansys.dynamicreporting.core.adr_utils import get_logger

   logger = get_logger(log_output="stdout", log_level="WARNING")

The positional ``logfile`` argument remains available for compatibility but is
deprecated. It emits ``DeprecationWarning``. Passing both ``logfile`` and
``log_output`` raises ``ValueError``.
