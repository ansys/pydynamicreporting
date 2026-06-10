JSON Importer
=============

The JSON importer provides a structured way to create ADR report items from a
JSON payload in serverless workflows.

The importer logic lives in the serverless package, while payload validation is
centralized in shared Pydantic models under utils so the same schema can be
reused by both server and serverless import versions.

Serverless Importer
-------------------

Use ``ADR.import_json_items`` to load a JSON file, validate it through
the shared schema models, create ADR items, and generate a root report
template from the imported payload.

During import, the top-level ``app_id`` is used to build the template header
and top-level ``tags`` are applied as template-level tags so imported items are
grouped under the generated report context.

.. code-block:: python

   from ansys.dynamicreporting.core.serverless import ADR

   adr = ADR(ansys_installation=r"...", db_directory=r"...")
   adr.setup()
   data = adr.import_json_items(r"...\report_items.json")
   print(data.app_id, len(data.items))

Supported item types in the current schema are:

- ``text``
- ``table``
- ``image``
- ``file``
- ``scene``
- ``tree``

.. automodule:: ansys.dynamicreporting.core.serverless.json_importer
   :members: ServerlessReportItemImporter
   :undoc-members:
   :show-inheritance:


Shared Validation Models
------------------------

The shared Pydantic validation models are documented in
:doc:`../userguide/json_importer_models`.



ADR JSON Report Items Schema Guide
----------------------------------

This document explains what the schema validates and how to use it when creating or checking report payload files.

JSON Schema (Production)
------------------------

This is the production schema used for validating JSON report item payloads:

.. code-block:: json

     {
         "$schema": "https://json-schema.org/draft/2020-12/schema",
         "$id": "https://example.local/adr-json-report-items/report-items.schema.json",
         "title": "ADR JSON Report Items",
         "type": "object",
         "additionalProperties": true,
         "required": [
             "app_id",
             "tags",
             "items"
         ],
         "properties": {
             "app_id": {
                 "type": "string"
             },
             "tags": {
                 "$ref": "#/$defs/tagsArray"
             },
             "items": {
                 "type": "array",
                 "items": {
                     "$ref": "#/$defs/item"
                 }
             }
         },
         "$defs": {
             "tagObject": {
                 "type": "object",
                 "minProperties": 1,
                 "additionalProperties": {
                     "type": "string"
                 }
             },
             "tagsArray": {
                 "type": "array",
                 "items": {
                     "$ref": "#/$defs/tagObject"
                 }
             },
             "propertyObject": {
                 "type": "object",
                 "minProperties": 1,
                 "additionalProperties": {
                     "anyOf": [
                         {
                             "type": "string"
                         },
                         {
                             "type": "number"
                         },
                         {
                             "type": "boolean"
                         },
                         {
                             "type": "null"
                         },
                         {
                             "type": "array"
                         },
                         {
                             "type": "object"
                         }
                     ]
                 }
             },
             "itemBase": {
                 "type": "object",
                 "required": [
                     "item_type",
                     "name",
                     "tags"
                 ],
                 "properties": {
                     "id": {
                         "type": "string"
                     },
                     "name": {
                         "type": "string"
                     },
                     "label": {
                         "type": "string"
                     },
                     "tags": {
                         "$ref": "#/$defs/tagsArray"
                     },
                     "properties": {
                         "type": "array",
                         "items": {
                             "$ref": "#/$defs/propertyObject"
                         }
                     }
                 }
             },
             "textItem": {
                 "allOf": [
                     {
                         "$ref": "#/$defs/itemBase"
                     },
                     {
                         "type": "object",
                         "required": [
                             "item_type",
                             "value"
                         ],
                         "properties": {
                             "item_type": {
                                 "const": "text"
                             },
                             "value": {
                                 "type": "string"
                             }
                         }
                     }
                 ]
             },
             "imageItem": {
                 "allOf": [
                     {
                         "$ref": "#/$defs/itemBase"
                     },
                     {
                         "type": "object",
                         "required": [
                             "item_type",
                             "src"
                         ],
                         "properties": {
                             "item_type": {
                                 "const": "image"
                             },
                             "src": {
                                 "type": "string"
                             }
                         }
                     }
                 ]
             },
             "fileItem": {
                 "allOf": [
                     {
                         "$ref": "#/$defs/itemBase"
                     },
                     {
                         "type": "object",
                         "required": [
                             "item_type",
                             "src"
                         ],
                         "properties": {
                             "item_type": {
                                 "const": "file"
                             },
                             "src": {
                                 "type": "string"
                             }
                         }
                     }
                 ]
             },
             "sceneItem": {
                 "allOf": [
                     {
                         "$ref": "#/$defs/itemBase"
                     },
                     {
                         "type": "object",
                         "required": [
                             "item_type",
                             "src"
                         ],
                         "properties": {
                             "item_type": {
                                 "const": "scene"
                             },
                             "src": {
                                 "type": "string"
                             }
                         }
                     }
                 ]
             },
             "tableItem": {
                 "allOf": [
                     {
                         "$ref": "#/$defs/itemBase"
                     },
                     {
                         "type": "object",
                         "required": [
                             "item_type",
                             "columns",
                             "rows"
                         ],
                         "properties": {
                             "item_type": {
                                 "const": "table"
                             },
                             "columns": {
                                 "type": "array",
                                 "items": {
                                     "type": "string"
                                 }
                             },
                             "rows": {
                                 "type": "array",
                                 "items": {
                                     "type": "array",
                                     "items": {
                                         "anyOf": [
                                             {
                                                 "type": "string"
                                             },
                                             {
                                                 "type": "number"
                                             },
                                             {
                                                 "type": "boolean"
                                             },
                                             {
                                                 "type": "null"
                                             }
                                         ]
                                     }
                                 }
                             },
                             "plot": {
                                 "type": "string"
                             },
                             "xaxis": {
                                 "type": "string"
                             },
                             "yaxis": {
                                 "type": "array",
                                 "items": {
                                     "type": "string"
                                 }
                             }
                         }
                     }
                 ]
             },
             "treeNode": {
                 "type": "object",
                 "required": [
                     "name"
                 ],
                 "properties": {
                     "name": {
                         "type": "string"
                     },
                     "children": {
                         "type": "array",
                         "items": {
                             "$ref": "#/$defs/treeNode"
                         }
                     }
                 },
                 "additionalProperties": true
             },
             "treeItem": {
                 "allOf": [
                     {
                         "$ref": "#/$defs/itemBase"
                     },
                     {
                         "type": "object",
                         "required": [
                             "item_type",
                             "data"
                         ],
                         "properties": {
                             "item_type": {
                                 "const": "tree"
                             },
                             "data": {
                                 "type": "object",
                                 "required": [
                                     "nodes"
                                 ],
                                 "properties": {
                                     "nodes": {
                                         "type": "array",
                                         "items": {
                                             "$ref": "#/$defs/treeNode"
                                         }
                                     }
                                 },
                                 "additionalProperties": true
                             }
                         }
                     }
                 ]
             },
             "item": {
                 "oneOf": [
                     {
                         "$ref": "#/$defs/textItem"
                     },
                     {
                         "$ref": "#/$defs/imageItem"
                     },
                     {
                         "$ref": "#/$defs/fileItem"
                     },
                     {
                         "$ref": "#/$defs/sceneItem"
                     },
                     {
                         "$ref": "#/$defs/tableItem"
                     },
                     {
                         "$ref": "#/$defs/treeItem"
                     }
                 ]
             }
         }
     }

Sample JSON payload:

.. code-block:: json

     {
         "app_id": "adr-mechanical",
         "tags": [
             { "report": "template_json_import" }
         ],
         "items": [
             {
                 "item_type": "text",
                 "name": "Summary",
                 "value": "Simulation completed successfully.",
                 "tags": [
                     { "section": "child_json_import" }
                 ]
             },
             {
                 "item_type": "text",
                 "name": "Formatted Report HTML",
                 "value": "<h1>Report</h1><p>All results are within range.</p>",
                 "tags": [
                     { "section": "child_json_import" }
                 ]
             },
             {
                 "item_type": "image",
                 "name": "Result Plot",
                 "src": "C://ANSYSDev/repos/adr_mechanical/assets/image.png",
                 "tags": [
                     { "section": "child_json_import" }
                 ]
             },
             {
                 "item_type": "file",
                 "name": "Raw Data File",
                 "src": "C://ANSYSDev/repos/adr_mechanical/assets/results.csv",
                 "tags": [
                     { "section": "child_json_import" }
                 ]
             },
             {
                 "item_type": "scene",
                 "name": "3D Scene",
                 "src": "C://ANSYSDev/repos/adr_mechanical/assets/scene.avz",
                 "tags": [
                     { "section": "child_json_import" }
                 ]
             },
             {
                 "item_type": "table",
                 "name": "Temperature Table One",
                 "tags": [
                     { "section": "child_json_import" }
                 ],
                 "columns": [],
                 "rows": [
                     [0.5, 10, 101325],
                     [0.5, 12, 101300],
                     [1, 15, 101280]
                 ]
             },
             {
                 "item_type": "table",
                 "name": "Temperature Table One",
                 "tags": [
                     { "section": "child_json_import" }
                 ],
                 "columns": ["X", "Sin", "Cos"],
                 "rows": [[1, 2], [3, 4]],
                 "plot": "line",
                 "xaxis": "X",
                 "yaxis": ["Sin", "Cos"],
                 "properties": [
                     { "format" : "floatdot0" },
                     { "zaxis": "Z" },
                     { "xaxis_format": "floatdot0" },
                     { "ytitle": "Values" },
                     { "ytitle": "X" }
                 ]
             },
             {
                 "item_type": "tree",
                 "name": "Hierarchy",
                 "tags": [
                     { "section": "child_json_import" }
                 ],
                 "data": {
                     "nodes": [
                         {
                             "name": "Parent-Root",
                             "children": [
                                 { "name": "Child One", "children": [ {"name":"Child One One"} ] },
                                 {
                                     "name": "Child Two",
                                     "children": [
                                         { "name": "Grandchild One", "children": [ {"name":"Child Two Two"} ] }
                                     ]
                                 }
                             ]
                         }
                     ]
                 }
             }
         ]
     }

What this schema is for
^^^^^^^^^^^^^^^^^^^^^^^

The schema validates a report items with this top-level structure:
- app_id: application identifier
- tags: report-level tags (array of key/value objects)
- items: list of report items

It is designed for the current sample format where table items use top-level columns and rows.

Supported item types
^^^^^^^^^^^^^^^^^^^^

Each object in items must include:
- item_type
- name
- tags

Then each type has its own required fields:
- text: value
- image: src
- file: src
- scene: src
- table: columns and rows
- tree: data.nodes

Optional common fields:
- properties

You can omit properties entirely. It is optional for all item types.

Tag format
^^^^^^^^^^

Tags are arrays of objects with one or more string values.

Examples:
- [ { "report": "json_import_tags" } ]
- [ { "section": "json_import_tags_1" } ]
- [ { "report": "json_import_tags" }, { "section": "json_import_tags_1" } ]

How to validate in VS Code
^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Open the JSON file you want to validate.
2. Add this line at the top of the JSON file:
   "$schema": "./report_items.schema.json",
3. Save the file.
4. VS Code will show schema validation errors in the Problems panel if any fields are missing or invalid.

Note: The schema path is resolved relative to the JSON file. If your JSON file is in another folder, adjust the relative path.

If validation fails, jsonschema raises an exception that tells you the failing path and rule.

Common mistakes to avoid
^^^^^^^^^^^^^^^^^^^^^^^^

- Missing item_type, name, or tags in an item.
- Using a table item without columns or rows.
- Using non-string values inside tag objects.
- Using a wrong structure for tree data (must include data.nodes).

