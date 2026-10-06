JSON import schema reference
############################

.. warning::

   **Beta.** This document format is a beta feature. The schema and the Python
   API may change in a future release. A breaking change to the format raises
   the ``schema_version`` major. Pin the version you validate against.

This page is the field-by-field reference for the JSON document consumed by
:func:`Service.import_from_json<ansys.dynamicreporting.core.Service.import_from_json>`
and
:func:`ADR.import_from_json<ansys.dynamicreporting.core.serverless.ADR.import_from_json>`.

For a task-oriented introduction, start with :ref:`ref_json_import_guide`. Use
this page when you are writing a producer and need to know exactly what is
accepted.

Scope
=====

The document describes report **items** only: text, HTML, tables, trees,
images, animations, 3D scenes, and files.

Report **structure** is not part of this format. Import report templates with
:func:`Service.load_templates<ansys.dynamicreporting.core.Service.load_templates>`
or
:func:`ADR.load_templates_from_file<ansys.dynamicreporting.core.serverless.ADR.load_templates_from_file>`.

The two compose through tags: give your items meaningful tags, and a template's
``item_filter`` selects them. A ``templates`` key in this document is treated as
an unknown key, not as report structure.

Design guarantees
=================

Three properties of this format are worth knowing before you write a producer.

**Every field maps to a real Ansys Dynamic Reporting field.** The schema is a
curated subset of the product data model, not a parallel invention. A continuous
integration check fails the build if a field here loses its counterpart.

**Validation reports every problem at once.** A malformed document raises a
single ``ImportValidationError`` listing every violation with its location, so
you fix a whole document in one edit instead of one error per run.

**Unknown fields are never silently dropped.** They are retained, reported, and
can be escalated to errors. See `Forward compatibility`_.

Versioning
==========

``schema_version`` is ``"MAJOR.MINOR"``. It is deliberately not semantic
versioning; there is no patch component.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Document declares
     - Result
   * - *(key absent)*
     - Accepted as ``"1.0"``, warning logged.
   * - ``"1.0"``
     - Accepted.
   * - ``"1.7"``
     - Accepted. Unrecognized fields are retained and an informational note is
       logged.
   * - ``"2.0"``
     - Rejected with ``ImportVersionError``.
   * - ``"1"`` or ``"1.0.0"``
     - Rejected with ``ImportVersionError``: malformed.

A **MAJOR** bump means a field was removed or retyped. A **MINOR** bump is
additive only, so a client built for ``1.0`` keeps working against a ``1.x``
document.

While the feature is in beta the shipped version stays at ``1.0``.

Document envelope
=================

.. list-table::
   :header-rows: 1
   :widths: 18 18 10 54

   * - Field
     - Type
     - Required
     - Description
   * - ``schema_version``
     - string
     - no
     - Format version. Defaults to ``"1.0"``.
   * - ``app_id``
     - string, non-empty
     - **yes**
     - Names the producing application and groups the imported content.
   * - ``tags``
     - array of tag objects
     - no
     - Applied to every item in the document. Defaults to ``[]``.
   * - ``metadata``
     - object
     - no
     - Free-form producer metadata, such as application version or run
       identifier. Retained but not interpreted.
   * - ``sessions``
     - array of objects
     - no
     - Accepted but **not applied** in v1.0. See `Sessions and datasets`_.
   * - ``datasets``
     - array of objects
     - no
     - Accepted but **not applied** in v1.0. See `Sessions and datasets`_.
   * - ``items``
     - array of item objects
     - no
     - The report items to create. Defaults to ``[]``.

A document with no items logs a warning and returns an empty successful result.
That is a no-op, not an error.

Tags
----

A tag is an object of string keys to scalar values:

.. code:: json

   "tags": [{ "section": "results" }, { "solver": "fluent" }]

Document tags and item tags are merged, so an item declaring
``{"section": "intro"}`` inside a document declaring ``{"report": "run42"}``
is stored with both.

For convenience these forms are also accepted and normalized:

.. code:: json

   "tags": { "section": "results" }
   "tags": ["section=results", "solver=fluent"]

A string entry without ``=`` is a validation error.

Sessions and datasets
---------------------

``sessions`` and ``datasets`` are parsed and checked for shape, then **ignored**.
Every item is created against the backend default session and dataset. An
informational note is logged when a document supplies either key.

They are reserved in the envelope so that adding real support later is a MINOR
bump rather than a breaking change. Do not rely on them taking effect in v1.0.

Items
=====

Common fields
-------------

Every item accepts these fields regardless of type.

.. list-table::
   :header-rows: 1
   :widths: 18 18 10 54

   * - Field
     - Type
     - Required
     - Description
   * - ``item_type``
     - closed set
     - **yes**
     - Selects the payload type. See `Item types`_.
   * - ``name``
     - string, non-empty
     - **yes**
     - Item name.
   * - ``tags``
     - array of tag objects
     - no
     - Merged with the document tags. This is how a report template later
       selects the item.
   * - ``source``
     - string
     - no
     - Producing application or component. Defaults to ``""``.
   * - ``sequence``
     - integer
     - no
     - Ordering hint within a report. Defaults to ``0``.
   * - ``properties``
     - array of objects
     - no
     - Escape hatch for fields not promoted to first class. See `Properties`_.

Item types
----------

.. list-table::
   :header-rows: 1
   :widths: 18 32 50

   * - ``item_type``
     - Additional required fields
     - Payload
   * - ``text``
     - ``value``
     - Plain text body.
   * - ``html``
     - ``value``
     - HTML fragment. Validated as markup.
   * - ``table``
     - ``columns``, ``rows``
     - Two-dimensional data. See `Tables`_.
   * - ``tree``
     - ``nodes``
     - Hierarchical data. See `Trees`_.
   * - ``image``
     - ``path``
     - Image file.
   * - ``animation``
     - ``path``
     - MP4 file.
   * - ``scene``
     - ``path``
     - 3D scene file, such as AVZ.
   * - ``file``
     - ``path``
     - Any other file.

An ``item_type`` outside this set is a validation error naming the offending
value and listing what is accepted.

File paths
----------

``path`` may be absolute, or relative to the directory containing the JSON
document. Pass ``base_dir`` to the import call to resolve relative paths against
a different directory instead.

Keeping the document beside its media keeps it portable:

.. code:: text

   thermal_run_42/
       report.json
       media/
           contour.png
           transient.mp4

.. note::

   Path resolution does not check that the file exists. Existence, readability,
   and extension are validated when the item is saved. A missing file surfaces
   as a per-item failure, not a parse error. See `Error handling`_.

.. note::

   ``src`` is accepted as a deprecated alias for ``path`` and logs a warning.
   Use ``path`` in new documents.

Tables
------

Tables are written **record-oriented**: ``columns`` names the fields, and each
entry of ``rows`` is one record.

.. code:: json

   {
     "item_type": "table",
     "name": "Probe Table",
     "columns": ["time", "T_max", "T_min"],
     "rows": [
       [0.0, 300.1, 290.0],
       [1.0, 320.5, 295.2],
       [2.0, 318.7, 294.1]
     ],
     "plot": "line",
     "format": "floatdot1",
     "xaxis": "time",
     "yaxis": ["T_max", "T_min"]
   }

A column may be a plain string or an object carrying an informational type:

.. code:: json

   "columns": [{ "name": "time", "type": "float" }]

.. list-table::
   :header-rows: 1
   :widths: 18 18 10 54

   * - Field
     - Type
     - Required
     - Description
   * - ``columns``
     - array
     - **yes**
     - Column definitions in record order.
   * - ``rows``
     - array of arrays
     - **yes**
     - One inner array per record.
   * - ``plot``
     - string
     - no
     - Plot style, such as ``"line"`` or ``"bar"``.
   * - ``format``
     - string
     - no
     - Cell value format, such as ``"floatdot1"``.
   * - ``xaxis``
     - string
     - no
     - Must name a column. Derived when omitted.
   * - ``yaxis``
     - array of strings
     - no
     - Each entry must name a column. Derived when omitted.

Rules
~~~~~

- Every row must have the same number of cells, and that count must match
  ``columns``. A ragged table is rejected with the offending row index.
- Cells must be scalars: string, number, boolean, or null.
- If ``xaxis`` and ``yaxis`` are omitted, the first column becomes the x axis
  and the remaining columns become the y axes.
- If supplied, ``xaxis`` and ``yaxis`` must name real columns.
- Numeric tables are stored as floats. A table containing any text is stored as
  text, with no truncation of long values.

Storage orientation
~~~~~~~~~~~~~~~~~~~

Ansys Dynamic Reporting stores tables **series-per-row**, which is the transpose
of the wire format. The importer performs the transpose, so the example above is
stored as a 3 by 3 array whose first row is the ``time`` series and whose row
labels are ``["time", "T_max", "T_min"]``.

You write records; Ansys Dynamic Reporting stores series. You do not need to
transpose anything yourself.

Trees
-----

.. code:: json

   {
     "item_type": "tree",
     "name": "Mesh",
     "nodes": [
       {
         "name": "Assembly",
         "children": [
           { "name": "Part A", "value": 1204 },
           { "name": "Part B", "value": 876 }
         ]
       }
     ]
   }

.. list-table::
   :header-rows: 1
   :widths: 18 18 10 54

   * - Field
     - Type
     - Required
     - Description
   * - ``name``
     - string, non-empty
     - **yes**
     - Node label.
   * - ``value``
     - scalar or array of scalars
     - no
     - Defaults to the node name.
   * - ``key``
     - string
     - no
     - Stable node key. Generated when absent.
   * - ``children``
     - array of nodes
     - no
     - Nested nodes. Recursive to any depth.

Generated keys embed the position of the node in the tree, so two siblings with
the same name never collide. Supply ``key`` explicitly only when you need a
stable identifier of your own.

Properties
----------

``properties`` reaches any item field that the schema does not promote to a
first-class field. Each entry is a single-key object:

.. code:: json

   "properties": [
     { "line_width": 2 },
     { "plot_title": "Probe temperatures" },
     { "stacked": 1 }
   ]

This covers the full table attribute vocabulary, including ``line_color``,
``line_style``, ``palette``, ``show_legend``, ``xtitle``, ``ytitle``,
``xrange``, ``yrange``, ``histogram_bin_size``, and many more.

Names that are private or that would shadow a method are refused and logged;
a document cannot overwrite behavior through this channel.

Forward compatibility
=====================

A key the importer does not recognize is **retained**, not dropped, and logged
at warning level with its full location:

.. code:: text

   items[3]: unknown key 'colums' is retained but not interpreted.

This keeps a newer producer compatible with an older client. It also means a
typo validates. To catch typos in your own pipeline, enable strict mode:

.. code:: python

   result = adr_service.import_from_json("report.json", strict_keys=True)

With ``strict_keys=True`` every unknown key becomes a validation error. Using it
in your continuous integration and leaving it off in production gives you both
properties.

Error handling
==============

Validation errors
-----------------

A document that violates the contract raises ``ImportValidationError`` before
anything is written. The error lists **every** problem found, each with its
location:

.. code:: text

   The ADR import document is not valid : 3 problems found
     app_id: is required
     items[0].value: is required
     items[2].item_type: expected one of ['text', 'html', ...], got 'spreadsheet'

Locations are precise, including inside nested structures, for example
``items[4].nodes[0].children[1].name``.

A rejected document never reaches the database. Nothing is partially written.

Version errors
--------------

An unsupported or malformed ``schema_version`` raises ``ImportVersionError``.
This is checked before any other field, because a newer major version may
redefine everything below it.

Per-item failures
-----------------

A document can be valid and still contain an item that cannot be saved, most
commonly a media file that does not exist. These are governed by ``on_error``:

.. code:: python

   result = adr_service.import_from_json("report.json", on_error="collect")

   print(result.items_saved, result.ok)
   for failure in result.failures:
       print(failure.index, failure.name, failure.item_type, failure.error)

``"collect"``, the default, records the failure and continues with the remaining
items. ``"raise"`` stops at the first failure.

Result object
=============

Both import methods return an ``ImportResult``:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Attribute
     - Description
   * - ``schema_version``
     - Resolved version of the imported document.
   * - ``app_id``
     - ``app_id`` declared by the document.
   * - ``items_saved``
     - Number of items successfully persisted.
   * - ``failures``
     - List of per-item failures, each with ``index``, ``name``, ``item_type``,
       and ``error``.
   * - ``ok``
     - ``True`` when there were no failures.

Complete example
================

.. code:: json

   {
     "schema_version": "1.0",
     "app_id": "adr-mechanical",
     "tags": [{ "report": "thermal_run_42" }],
     "metadata": { "producer": "adr-mechanical", "producer_version": "2026R1" },
     "items": [
       {
         "item_type": "text",
         "name": "Summary",
         "tags": [{ "section": "intro" }],
         "source": "adr-mechanical",
         "sequence": 0,
         "value": "Simulation completed successfully."
       },
       {
         "item_type": "html",
         "name": "Notes",
         "tags": [{ "section": "intro" }],
         "value": "<p>All results within range.</p>"
       },
       {
         "item_type": "image",
         "name": "Contour",
         "tags": [{ "section": "results" }],
         "path": "media/contour.png"
       },
       {
         "item_type": "animation",
         "name": "Transient",
         "tags": [{ "section": "results" }],
         "path": "media/transient.mp4"
       },
       {
         "item_type": "scene",
         "name": "Assembly View",
         "tags": [{ "section": "results" }],
         "path": "media/assembly.avz"
       },
       {
         "item_type": "file",
         "name": "Solver Log",
         "tags": [{ "section": "appendix" }],
         "path": "media/solver.log"
       },
       {
         "item_type": "table",
         "name": "Probe Table",
         "tags": [{ "section": "results" }],
         "columns": ["time", "T_max", "T_min"],
         "rows": [
           [0.0, 300.1, 290.0],
           [1.0, 320.5, 295.2],
           [2.0, 318.7, 294.1]
         ],
         "plot": "line",
         "format": "floatdot1",
         "xaxis": "time",
         "yaxis": ["T_max", "T_min"],
         "properties": [{ "line_width": 2 }, { "plot_title": "Probe temperatures" }]
       },
       {
         "item_type": "tree",
         "name": "Mesh",
         "tags": [{ "section": "results" }],
         "nodes": [
           {
             "name": "Assembly",
             "children": [
               { "name": "Part A", "value": 1204 },
               { "name": "Part B", "value": 876 }
             ]
           }
         ]
       }
     ]
   }

The ``section`` tags are what connect this content to a report. A ``panel``
template whose ``item_filter`` is ``A|i_tags|cont|section=results;`` picks up
the results items, without this document describing any structure.

Validating a document
=====================

A machine-readable JSON Schema (draft 2020-12) is published as
``adr_item_import.schema.json`` at the root of the PyDynamicReporting repository. It
is generated from the same definitions the importer validates against, so the
two cannot disagree.

Validate a document before importing it:

.. code:: text

   check-jsonschema --schemafile adr_item_import.schema.json my_report.json

Any validator that supports draft 2020-12 works equally well. This is the
recommended check to add to a producing application's own test suite.

When Ansys Dynamic Reporting does not model something
=====================================================

Put it in ``properties`` for an item, or in ``metadata`` for the document. Both
are honored where Ansys Dynamic Reporting recognizes the name, and retained with
a warning otherwise. Nothing you supply is silently discarded.

If you need a field promoted to first class, or a new item type, open an issue
at https://github.com/ansys/pydynamicreporting/issues describing the producing
application and the data you need to send.
