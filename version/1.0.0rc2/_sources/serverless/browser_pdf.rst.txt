.. _serverless_browser_pdf:

Browser PDF export
==================

Serverless browser-PDF export is available with ADR 27.1 and later. It stages
an offline report bundle, opens that bundle with the Chromium package shipped
with ADR, and prints the browser-rendered report to PDF.

ADR 26.1 remains supported by PyDynamicReporting 1.x, but it does not contain
the required browser package. Serverless PDF rendering is therefore
unavailable with ADR 26.1.

Configure static assets
-----------------------

Set a local ADR 27.1 installation and a ``static_directory``, then collect the
product's static files during setup:

.. code-block:: python

   from ansys.dynamicreporting.core.serverless import ADR

   adr = ADR(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v271",
       db_directory=r"C:\reports\database",
       media_directory=r"C:\reports\media",
       static_directory=r"C:\reports\static",
   )
   adr.setup(collect_static=True)

Both ``static_directory`` and ``collect_static=True`` are required so the
offline bundle contains the report's styles, scripts, fonts, and other static
assets.

Render PDF bytes
----------------

Use
:meth:`~ansys.dynamicreporting.core.serverless.adr.ADR.render_report_as_browser_pdf`
when another API or storage layer needs the PDF as bytes:

.. code-block:: python

   pdf_bytes = adr.render_report_as_browser_pdf(
       name="Simulation Summary",
       context={"project": "wing"},
       item_filter="A|i_tags|cont|project=wing;",
       dark_mode=True,
       landscape=True,
       margins={
           "top": "12mm",
           "right": "12mm",
           "bottom": "12mm",
           "left": "12mm",
       },
       render_timeout=45,
   )

   with open("simulation-summary.pdf", "wb") as pdf_file:
       pdf_file.write(pdf_bytes)

Write a PDF file
----------------

Use
:meth:`~ansys.dynamicreporting.core.serverless.adr.ADR.export_report_as_browser_pdf`
to write the report directly:

.. code-block:: python

   adr.export_report_as_browser_pdf(
       filename="simulation-summary.pdf",
       name="Simulation Summary",
       context={"project": "wing"},
       item_filter="A|i_tags|cont|project=wing;",
       dark_mode=True,
   )

If ``filename`` is omitted, the export uses the report template GUID with a
``.pdf`` suffix. Both methods require at least one template lookup argument,
such as ``name`` or ``guid``.

Diagnosing failures
--------------------

Unlike the connected-service :meth:`~ansys.dynamicreporting.core.Report.export_browser_pdf`,
which returns ``False`` on failure for backward compatibility, both serverless methods
raise ``ADRException`` when the export fails, for example when a readiness signal such as
Plotly charts does not finish within ``render_timeout``. Catch that exception to see the
specific reason:

.. code-block:: python

   from ansys.dynamicreporting.core.exceptions import ADRException

   try:
       adr.export_report_as_browser_pdf(
           filename="simulation-summary.pdf", name="Simulation Summary"
       )
   except ADRException as exc:
       raise RuntimeError(f"Browser PDF export failed: {exc}") from exc

Options
-------

* ``context`` supplies template rendering values.
* ``item_filter`` limits report items with an ADR query expression.
* ``dark_mode`` selects the report's dark presentation.
* ``landscape`` defaults to portrait output.
* ``margins`` must contain exactly ``top``, ``right``, ``bottom``, and
  ``left``. Values can use pixels, inches, centimeters, or millimeters. A
  unitless value is treated as pixels. The default is 10 mm on every side.
* ``render_timeout`` is one shared browser-side budget for browser launch,
  navigation, readiness checks, and print preparation. It defaults to 30
  seconds. Server-side template rendering and offline asset staging occur
  before that budget starts.

Offline rendering behavior
--------------------------

The renderer waits for ADR web components, fonts, MathJax, Plotly, images, and
videos. Print styling keeps headings with the following content and preserves
the report canvas used by responsive charts.

The staged report blocks external network requests. All content needed by the
PDF must therefore be present in the offline bundle. Custom asynchronous
JavaScript in raw HTML items or layout HTML does not have its own readiness
signal and can still be captured before it finishes.

Browser and process requirements
--------------------------------

PyDynamicReporting uses the Chromium package from the configured ADR 27.1
installation; it does not use a machine-wide Playwright browser cache. A
missing or incomplete product browser package raises an ADR-owned error.

During rendering, PyDynamicReporting temporarily points
``PLAYWRIGHT_BROWSERS_PATH`` at the product browser and restores the caller's
original value afterward. Because this environment variable is process-wide,
do not run browser-PDF exports concurrently in the same process.

Temporary offline bundles are removed after the operation. Cleanup failures
are retained for debug logging and do not mask a successful PDF or the primary
rendering error.
