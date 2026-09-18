.. _connected_browser_pdf:

Browser PDF export
##################

Connected browser-PDF export is available with ADR 27.1 and later. It uses the
Chromium package shipped with the local ADR installation to render the live,
authenticated report page and print the browser view to PDF.

ADR 26.1 remains supported by PyDynamicReporting 1.x, but it does not contain
the browser package required for this export path. Use another export format
with ADR 26.1.

Export a connected report
=========================

Create the ``Service`` with a local ADR 27.1 installation, connect to the
service that hosts the report, and call
:meth:`~ansys.dynamicreporting.core.Report.export_browser_pdf`:

.. code-block:: python

   import ansys.dynamicreporting.core as adr

   service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v271")
   service.connect(
       url="http://report-server:8000",
       username="report-user",
       password="report-password",
   )

   report = service.get_report(report_name="Simulation Summary")
   exported = report.export_browser_pdf(
       file_name=r"C:\reports\simulation-summary.pdf",
       query_params={"colormode": "dark"},
       item_filter="A|i_tags|cont|project=wing;",
       landscape=True,
       page_size=adr.PDFPageSize.A3,
       margins={
           "top": "12mm",
           "right": "12mm",
           "bottom": "12mm",
           "left": "12mm",
       },
       render_timeout=45,
   )
   if not exported:
       raise RuntimeError("The report was not exported.")

The method returns ``True`` after writing the file and ``False`` if the report
is disconnected or the export fails. It does not modify the supplied
``query_params`` dictionary.

Page sizes
==========

Browser-PDF export defaults to ``adr.PDFPageSize.A3``. The following fixed
formats are available: ``adr.PDFPageSize.LETTER``,
``adr.PDFPageSize.LEGAL``, ``adr.PDFPageSize.TABLOID``,
``adr.PDFPageSize.LEDGER``, and ``adr.PDFPageSize.A0`` through
``adr.PDFPageSize.A6``.

For a custom page, set ``page_size=None`` and provide both ``width`` and
``height``:

.. code-block:: python

   exported = report.export_browser_pdf(
       file_name=r"C:\reports\custom-size.pdf",
       page_size=None,
       width="320mm",
       height="450mm",
   )

Each custom dimension can be a positive number, interpreted as CSS pixels, or
a string using ``px``, ``in``, ``cm``, or ``mm``. Supplying only one dimension
causes the export to fail. If ``page_size`` is ``None`` and neither dimension
is provided, the export falls back to A3.

``page_size`` takes precedence over ``width`` and ``height`` whenever it is not
``None``. Set it to ``None`` to activate custom dimensions. Setting
``landscape=True`` swaps the selected width and height for either fixed or
custom sizing. Content wider than the printable area is clipped and never
expands the page.

Diagnosing a ``False`` return
==============================

A ``False`` return does not raise an exception, so the specific failure reason
(for example, which readiness step timed out, such as Plotly charts not
finishing within ``render_timeout``) is not visible unless you capture it:

* Configure ADR logging before calling ``export_browser_pdf``, for example
  ``adr.Service(..., log_output="stdout")``, then look for a
  ``Can not export browser pdf report:`` message.
* Or catch the ``UserWarning`` that is raised alongside the log message, which
  carries the same failure reason and does not require logging configuration:

  .. code-block:: python

     import warnings

     with warnings.catch_warnings(record=True) as caught:
         warnings.simplefilter("always")
         exported = report.export_browser_pdf(file_name=r"C:\reports\summary.pdf")
     if not exported:
         raise RuntimeError(str(caught[-1].message))

Options
========

* ``query_params`` supplies report URL parameters. For example,
  ``{"colormode": "dark"}`` requests the report's dark color mode.
* ``item_filter`` limits the report items with an ADR query expression.
* ``landscape`` defaults to portrait output. When enabled, it swaps the
  selected page width and height.
* ``margins`` must contain exactly ``top``, ``right``, ``bottom``, and
  ``left``. Values can use pixels, inches, centimeters, or millimeters. A
  unitless value is treated as pixels. The default is 10 mm on every side.
* ``page_size`` selects a fixed ``PDFPageSize`` and defaults to A3.
* ``width`` and ``height`` define a custom page when ``page_size=None``. Both
  dimensions are required.
* ``render_timeout`` is one shared browser-side budget for browser launch,
  navigation, readiness checks, and print preparation. It defaults to 30
  seconds. It does not include work completed before the browser starts.

How the report is rendered
==========================

The browser opens the live report URL, carries the authenticated ADR web
session into that browser context, and waits for ADR web components, fonts,
MathJax, Plotly, images, and videos. Browser layout and pagination use the
selected printable page dimensions. The live page keeps its normal network
access. Authentication cookies are scoped to the originating ADR service.

Custom asynchronous JavaScript in raw HTML items or layout HTML does not have
its own readiness signal. If that code finishes outside the built-in signals,
the PDF can capture the page before the custom update completes.

Local browser requirement
=========================

Rendering happens on the machine that runs PyDynamicReporting, even when the
report service is remote. The local ``Service`` therefore needs ADR 27.1
installation metadata and the complete product-shipped browser package.
PyDynamicReporting does not fall back to a machine-wide Playwright browser
cache.

During a render, PyDynamicReporting temporarily points
``PLAYWRIGHT_BROWSERS_PATH`` at the product browser and restores the caller's
original value afterward. Because this environment variable is process-wide,
do not run browser-PDF exports concurrently in the same process.

Missing or incomplete product browser packages are reported through the ADR
export error. Browser and context cleanup failures are logged for diagnostics
and do not replace an otherwise successful export.
