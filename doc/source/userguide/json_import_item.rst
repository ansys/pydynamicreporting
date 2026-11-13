.. _ref_json_import_guide:

JSON item import
################

.. warning::

   **Beta.** JSON item import is a beta feature. The schema and the Python
   API may change in a future release, and a breaking change to the document
   format will raise the ``schema_version`` major. Pin the version you
   validate against, and report anything that surprises you.

PyDynamicReporting can create report items from a single JSON document. The
same document imports identically through
:func:`Service.import_items_from_json<ansys.dynamicreporting.core.Service.import_items_from_json>`
(server mode) and
:func:`ADR.import_items_from_json<ansys.dynamicreporting.core.serverless.ADR.import_items_from_json>`
(serverless mode).

This is useful when a producing application already knows what it wants to
report and simply needs to hand that description to ADR.

This page is a task-oriented introduction. For the complete field-by-field
contract, see :doc:`json_import_item_schema`.

.. note::

   Report structure is out of scope for this contract. Import report
   templates with
   :func:`Service.load_templates<ansys.dynamicreporting.core.Service.load_templates>`
   or
   :func:`ADR.load_templates_from_file<ansys.dynamicreporting.core.serverless.ADR.load_templates_from_file>`.

Quick start
-----------

Write a document:

.. code:: json

   {
     "schema_version": "1.0",
     "app_id": "adr-mechanical",
     "tags": [{ "report": "thermal_run_42" }],
     "items": [
       {
         "item_type": "text",
         "name": "Summary",
         "tags": [{ "section": "intro" }],
         "value": "Simulation completed successfully."
       },
       {
         "item_type": "image",
         "name": "Contour",
         "path": "contour.png"
       }
     ]
   }

Then import it:

.. code:: python

   import ansys.dynamicreporting.core as adr

   adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v261")
   adr_service.connect(url="http://localhost:8010")

   result = adr_service.import_items_from_json(r"D:\runs\42\report.json")
   print(result.items_saved, result.ok)

The serverless call is identical:

.. code:: python

   from ansys.dynamicreporting.core.serverless import ADR

   adr_obj = ADR(
       ansys_installation=r"C:\Program Files\ANSYS Inc\v261", db_directory=r"D:\db"
   )
   adr_obj.setup()

   result = adr_obj.import_items_from_json(r"D:\runs\42\report.json")

If the document is already in memory, for example built by your own code, pass
the dictionary to the same method. There is no file to resolve relative media
paths against, so they resolve against the current working directory. Use
absolute media paths in that case:

.. code:: python

   result = adr_obj.import_items_from_json(document)

The document envelope
---------------------

======================  ========  ===========================================
Field                   Required  Description
======================  ========  ===========================================
``schema_version``      no        ``"1.MINOR"``. Defaults to ``"1.0"``.
``app_id``              **yes**   Names the producing application.
``tags``                no        Merged into every item.
``items``               no        Report items to create.
======================  ========  ===========================================

Item types
----------

Every item carries ``item_type``, ``name``, and optionally ``tags``,
``source``, and ``sequence``.

=================  ===============================  ========================
``item_type``      Payload fields                   Created as
=================  ===============================  ========================
``text``           ``value``                        ``String``
``html``           ``value``                        ``HTML``
``table``          ``array``                        ``Table``
``tree``           ``nodes``                        ``Tree``
``image``          ``path``                         ``Image``
``animation``      ``path``                         ``Animation``
``scene``          ``path``                         ``Scene``
``file``           ``path``                         ``File``
=================  ===============================  ========================

Media paths may be absolute, or relative to the directory containing the JSON
document.

Media files must use an extension that both backends accept: ``image`` takes
``.png``, ``.jpg``, ``.tif``, or ``.tiff``; ``animation`` takes ``.mp4``;
``scene`` takes the 3D formats listed in :doc:`json_import_item_schema`; ``file``
takes any extension.

Text and HTML ``value`` payloads are passed to the existing backend validators.
Missing, null, or non-string values are per-item failures. Serverless HTML
requires at least one HTML tag; REST accepts any valid UTF-8 string.

Tables
------

Tables use the ADR table format and are passed to ADR unchanged. ``array`` holds
one inner array per row label, so each series, such as all ``time`` values,
is one inner array.

.. code:: json

   {
     "item_type": "table",
     "name": "Probe Table",
     "array": [[0.0, 1.0], [300.1, 320.5], [290.0, 295.2]],
     "labels_row": ["time", "T_max", "T_min"],
     "xaxis": "time",
     "yaxis": ["T_max", "T_min"],
     "plot": "line"
   }

``dtype`` selects how the array is stored: ``"f8"`` (the default) for numbers
or ``"S"`` for text. A table also accepts every ADR table property, such as
``labels_row``, ``labels_column``, ``xaxis``, ``yaxis``, ``plot``, ``format``,
``title``, ``rowlbls``, and ``collbls``.

Trees
-----

.. code:: json

   {
     "item_type": "tree",
     "name": "Mesh",
     "nodes": [
       {
         "key": "assembly",
         "name": "Assembly",
         "value": null,
         "state": "expanded",
         "children": [
           { "key": "part", "name": "Part A", "value": 1204 },
           { "key": "part", "name": "Part B", "value": 876 }
         ]
       }
     ]
   }

Nodes use the ADR tree format and are passed to ADR unchanged. Each node
requires ``key``, ``name``, and ``value``. The ``key`` is a hidden entity type
label, so it can repeat. A node can also have ``children`` and the optional
``state`` and ``header`` display hints.

Error handling
--------------

Contract violations raise ``ImportItemValidationError``, which reports **every**
problem found in one pass, each with its location. It and
``ImportItemVersionError`` derive from ``ADRItemImportError`` and are importable
from ``ansys.dynamicreporting.core.exceptions`` with the other ADR exceptions:

.. code:: python

   from ansys.dynamicreporting.core.exceptions import ImportItemValidationError

.. code:: text

   The ADR import item json document is not valid : 3 problems found
     app_id: is required
     items[0].name: is required
     items[2].item_type: expected one of ['text', 'html', ...], got 'spreadsheet'

Per-item failures during creation are governed by ``on_error``:

.. code:: python

   result = adr_service.import_items_from_json("report.json", on_error="collect")
   for failure in result.failures:
       print(failure.name, failure.item_type, failure.error)

``"collect"`` (the default) records failures and continues; ``"raise"`` stops at
the first one.

Unknown keys are logged as warnings and ignored, so a newer producer can talk
to an older client.

Versioning
----------

``schema_version`` is ``MAJOR.MINOR``. This release reads major ``1``: any
``1.<minor>`` is accepted, and any other major or a malformed version is
rejected with ``ImportItemVersionError``.

While the feature is in beta, the shipped version stays at ``1.0``. Treat a
major bump as the signal that the format changed incompatibly.

Format reference
----------------

:doc:`json_import_item_schema` summarizes the validation rules.

A complete working document that exercises every item type lives at
``tests/test_data/adr_import/canonical_report.json``. It is the easiest
starting point to copy, and a unit test validates it on every run, so it
cannot fall out of step with the importer.
