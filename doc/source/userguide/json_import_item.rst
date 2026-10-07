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
contract, see :doc:`json_import_schema`.

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

The document envelope
---------------------

======================  ========  ===========================================
Field                   Required  Description
======================  ========  ===========================================
``schema_version``      no        ``"MAJOR.MINOR"``. Defaults to ``"1.0"``.
``app_id``              **yes**   Names the producing application.
``tags``                no        Merged into every item.
``metadata``            no        Free-form producer metadata. Retained but
                                  not interpreted.
``sessions``            no        Accepted but **not applied** in v1.0.
``datasets``            no        Accepted but **not applied** in v1.0.
``items``               no        Report items to create.
======================  ========  ===========================================

Item types
----------

Every item carries ``item_type``, ``name``, and optionally ``tags``,
``source``, ``sequence``, and ``properties``.

=================  ===============================  ========================
``item_type``      Payload fields                   Created as
=================  ===============================  ========================
``text``           ``value``                        ``String``
``html``           ``value``                        ``HTML``
``table``          ``columns``, ``rows``            ``Table``
``tree``           ``nodes``                        ``Tree``
``image``          ``path``                         ``Image``
``animation``      ``path``                         ``Animation``
``scene``          ``path``                         ``Scene``
``file``           ``path``                         ``File``
=================  ===============================  ========================

Media paths may be absolute, or relative to the directory containing the JSON
document. Pass ``base_dir`` to resolve them against a different directory.

Tables
------

Tables are written **record-oriented**: ``columns`` names the fields and each
entry of ``rows`` is one record.

.. code:: json

   {
     "item_type": "table",
     "name": "Probe Table",
     "columns": ["time", "T_max", "T_min"],
     "rows": [[0.0, 300.1, 290.0], [1.0, 320.5, 295.2]],
     "plot": "line",
     "properties": [{ "line_width": 2 }]
   }

ADR stores tables series-per-row, so the importer transposes the data on the
way in. The example above becomes a ``(3, 2)`` array whose row labels are
``["time", "T_max", "T_min"]``.

If ``xaxis`` and ``yaxis`` are omitted, the first column becomes the x axis and
the remaining columns become the y axes. When supplied, they must name
columns.

Anything ADR models but the schema does not promote to a first-class field is
reachable through ``properties``.

Trees
-----

.. code:: json

   {
     "item_type": "tree",
     "name": "Mesh",
     "nodes": [
       { "name": "Assembly", "children": [{ "name": "Part A" }, { "name": "Part B" }] }
     ]
   }

A node value defaults to the node name. Node keys are generated from the
position in the tree, so repeated names never collide.

Error handling
--------------

Contract violations raise ``ImportValidationError``, which reports **every**
problem found in one pass, each with its location:

.. code:: text

   The ADR import document is not valid : 3 problems found
     app_id: is required
     items[0].value: is required
     items[2].item_type: expected one of ['text', 'html', ...], got 'spreadsheet'

Per-item failures during creation are governed by ``on_error``:

.. code:: python

   result = adr_service.import_items_from_json("report.json", on_error="collect")
   for failure in result.failures:
       print(failure.name, failure.item_type, failure.error)

``"collect"`` (the default) records failures and continues; ``"raise"`` stops at
the first one.

Unknown keys are retained and logged as warnings, so a newer producer can talk
to an older client. Pass ``strict_keys=True`` to turn them into errors.

Versioning
----------

``schema_version`` is ``MAJOR.MINOR``. A document whose major exceeds the
supported major is rejected with ``ImportVersionError``. A newer minor is
accepted and its unrecognized fields are retained.

While the feature is in beta, the shipped version stays at ``1.0``. Treat a
major bump as the signal that the format changed incompatibly.

Schema reference
----------------

:doc:`json_import_schema` documents every field, its type, and its validation
rules.

The machine-readable contract is generated from the same field tables the
parser validates against, and is committed at the repository root as
``adr_item_import.schema.json``. To validate your own document before importing it:

.. code:: text

   check-jsonschema --schemafile adr_item_import.schema.json my_report.json

A complete working document that exercises every item type lives at
``tests/test_data/adr_import/canonical_report.json``. It is the easiest
starting point to copy, and it is validated against the committed schema on
every commit, so it cannot fall out of step with the contract.
