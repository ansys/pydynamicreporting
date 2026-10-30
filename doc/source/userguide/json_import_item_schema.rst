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
- Document tags are merged into every item's tags.

**Items**

- ``item_type`` is one of ``text``, ``html``, ``table``, ``tree``, ``image``,
  ``animation``, ``scene``, or ``file``.
- ``name`` is a required, non-empty string. ``source`` is a string and
  ``sequence`` an integer; a boolean is not an integer.
- ``text`` and ``html`` require a string ``value``. An ``html`` value must
  contain at least one HTML tag.

**Media paths**

- ``image``, ``animation``, ``scene``, and ``file`` require a non-empty
  ``path``, absolute or relative to the document directory (or ``base_dir``).
- Extensions are matched case-insensitively: ``image`` takes ``.png``, ``.jpg``,
  ``.tif``, ``.tiff``; ``animation`` takes ``.mp4``; ``scene`` takes ``.stl``,
  ``.ply``, ``.csf``, ``.avz``, ``.scdoc``, ``.scdocx``, ``.dsco``, ``.glb``,
  ``.obj``; ``file`` takes any extension.
- File existence is checked when the item is saved, so a missing file is a
  per-item failure, not a validation error.

**Tables**

- ``columns`` (strings, or objects with a non-empty ``name``) and ``rows``
  (arrays of cells) are required.
- Every row has the same number of cells as ``columns``.
- Cells are strings, numbers, booleans, or ``null``. ``NaN`` and ``Infinity``
  are rejected; use ``null`` for a missing number.
- ``xaxis`` and every ``yaxis`` entry must name a column.

**Trees**

- Each node requires a non-empty ``name``. ``value`` is a scalar or an array of
  scalars and defaults to the name; ``key`` is optional; ``children`` is an
  array of nodes.
- Nesting deeper than 100 levels is rejected.

**Unknown keys**

- Keys that the schema does not define, at any level, are logged as warnings
  and ignored. A ``templates`` key is ignored the same way: report structure is
  imported with ``load_templates``.

Validating a document
=====================

Validate a document before importing it:

.. code:: text

   check-jsonschema --schemafile adr_item_import.schema.json my_report.json

Any validator that supports draft 2020-12 works. The schema checks field types,
required fields, and the version pattern. The rules that JSON Schema cannot
express, such as equal row widths and axis names, are checked by the importer.

If you need a field or item type that the schema does not offer, open an issue
at https://github.com/ansys/pydynamicreporting/issues.
