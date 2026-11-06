JSON import schema reference
############################

.. warning::

   **Beta.** This document format is a beta feature. The schema and the Python
   API may change in a future release. A breaking change to the format raises
   the ``schema_version`` major.

This page summarizes the validation rules for the JSON document consumed by
:func:`Service.import_items_from_json<ansys.dynamicreporting.core.Service.import_items_from_json>`
and
:func:`ADR.import_items_from_json<ansys.dynamicreporting.core.serverless.ADR.import_items_from_json>`.
For the fields, examples, and error handling, start with :ref:`ref_json_import_guide`.

The complete machine-readable contract is the JSON Schema (draft 2020-12)
``adr_item_import.schema.json`` at the root of the PyDynamicReporting
repository. It is generated from the same definitions the importer validates
against.

Validation rules
================

Validation reports every problem in one ``ImportItemValidationError``, each with
its location, such as ``items[3].rows[1]``.

**Envelope**

- ``app_id`` is a required, non-empty string.
- ``schema_version`` is ``"1.<minor>"``, for example ``"1.0"``. An absent version
  means ``"1.0"``. Any other major, or a value such as ``"1"`` or ``"1.0.0"``,
  raises ``ImportItemVersionError`` before anything else is checked.
- A document with no items is valid and imports nothing.

**Tags**

- ``tags`` is an array of objects. Each object has at least one key, and every
  value is a string, number, or boolean.
- Each backend checks and merges document/item tags before saving. Invalid item
  tags fail that item; invalid document tags fail every item.

**Items**

- ``item_type`` is one of ``text``, ``html``, ``table``, ``tree``, ``image``,
  ``animation``, ``scene``, or ``file``.
- ``name`` is a required, non-empty string. ``source`` is a string and
  ``sequence`` an integer; a boolean is not an integer.
- ``text`` and ``html`` values are checked by the backend during item creation,
  not by the schema or importer. Missing, null, or non-string values are
  per-item failures. Serverless HTML requires at least one HTML tag; REST
  accepts any valid UTF-8 string.

**Media paths**

- ``image``, ``animation``, ``scene``, and ``file`` take a ``path``, absolute or
  relative to the document directory (or ``base_dir``).
- Extensions are matched case-insensitively: ``image`` takes ``.png``, ``.jpg``,
  ``.tif``, ``.tiff``; ``animation`` takes ``.mp4``; ``scene`` takes ``.stl``,
  ``.ply``, ``.csf``, ``.avz``, ``.scdoc``, ``.scdocx``, ``.dsco``, ``.glb``,
  ``.obj``; ``file`` takes any extension.
- An ``image`` path is checked during validation: it is required, non-empty,
  and has a supported extension.
- ``animation``, ``scene``, and ``file`` paths are checked when the item is
  saved, so a missing, empty, or non-string path, an unsupported extension, or
  a missing file is a per-item failure, not a validation error.
- Image file existence is also checked when the item is saved.

**Tables**

- ``array`` is required: the table data in the ADR table format, one inner array
  per row label. ``dtype`` is ``"f8"`` (the default) for numbers or ``"S"`` for
  text.
- Every ADR table property, such as ``labels_row``, ``xaxis``, ``yaxis``,
  ``plot``, ``format``, ``rowlbls``, and ``collbls``, is accepted and passed to
  the backend unchanged.
- The backend checks ``array`` and ``dtype`` when the item is saved, so a
  non-array, ragged, or non-numeric array, or an invalid ``dtype``, is a
  per-item failure, not a validation error. It does not check that labels or
  axes match the array.

**Trees**

- ``nodes`` is an array of complete ADR tree nodes, which are passed to the
  backend unchanged. Each node requires ``key``, ``name``, and ``value``.
  ``children`` is an optional array of nodes; ``state`` and ``header`` are
  optional display hints.
- ``key`` is a hidden entity type label, not an identifier, so it need not be
  unique. ``value`` is ``null``, a scalar, or an array of them, and arrays may
  nest.
- The backend checks ``nodes`` when the item is saved, so a missing or
  non-array ``nodes`` value, or a malformed node, is a per-item failure, not a
  validation error. The backend does not check the types of ``key``, ``name``,
  ``state``, or ``header``, and it accepts ``NaN`` and ``Infinity`` values;
  validate against the schema to catch these.

**Unknown keys**

- Keys that the schema does not define are logged as warnings and ignored, except
  inside tree nodes, which are passed to the backend unchanged. A ``templates``
  key is ignored the same way: report structure is imported with
  ``load_templates``.

Validating a document
=====================

Validate a document before importing it:

.. code:: text

   check-jsonschema --schemafile adr_item_import.schema.json my_report.json

Any validator that supports draft 2020-12 works. The schema checks field types,
required fields, and the version pattern. Tags, text, HTML, table arrays, and
tree nodes are checked by ADR during item creation.

If you need a field or item type that the schema does not offer, open an issue
at https://github.com/ansys/pydynamicreporting/issues.
