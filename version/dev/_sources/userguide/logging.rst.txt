.. _connected_logging:

Logging
#######

Connected-service logging uses the shared
``ansys.dynamicreporting.core`` logger. PyDynamicReporting does not change the
application's root logger.

Write logs to standard output
=============================

Pass ``log_output="stdout"`` when constructing a
:class:`~ansys.dynamicreporting.core.Service`:

.. code-block:: python

   import logging

   import ansys.dynamicreporting.core as adr

   service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v261",
       log_output="stdout",
       log_level=logging.INFO,
   )

Write logs to a file
====================

Any other ``log_output`` value is treated as a file path:

.. code-block:: python

   service = adr.Service(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v261",
       log_output=r"C:\reports\pydynamicreporting.log",
       log_level="DEBUG",
   )

If ``log_level`` is omitted, the existing level on the shared ADR logger is
left unchanged. If ``log_output`` is omitted, PyDynamicReporting adds no
visible output handler.

Repeated calls with the same standard-output stream or normalized file path do
not add duplicate PyDynamicReporting-owned handlers. This prevents duplicate
lines when multiple ``Service`` objects reuse the package logger.

Configure the package logger directly
=====================================

Use :func:`~ansys.dynamicreporting.core.adr_utils.get_logger` when you need to
configure logging before constructing a service:

.. code-block:: python

   from ansys.dynamicreporting.core.adr_utils import get_logger

   logger = get_logger(log_output="stdout", log_level="WARNING")

The positional ``logfile`` argument remains available for compatibility but is
deprecated. It emits ``DeprecationWarning``. Passing both ``logfile`` and
``log_output`` raises ``ValueError``.
