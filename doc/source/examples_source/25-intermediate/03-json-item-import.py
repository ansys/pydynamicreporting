# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
.. _ref_json_item_import:

Import report items from a JSON document
========================================

Build an ADR import document in memory, write it to disk, and import it with
:func:`Service.import_from_json<ansys.dynamicreporting.core.Service.import_from_json>`.

The same document imports unchanged through
:func:`ADR.import_from_json<ansys.dynamicreporting.core.serverless.ADR.import_from_json>`
in serverless mode.

.. warning::

   **Beta.** JSON item import is a beta feature. The schema and the Python
   API may change in a future release.

.. note::

   This example assumes that you have a local Ansys installation.

"""

###############################################################################
# Build the document
# ------------------
# ``app_id`` names the generated root report. Because no ``templates`` key is
# supplied, a ``basic`` root template named after ``app_id`` is created
# automatically and every item lands under it.

import json
from pathlib import Path

import ansys.dynamicreporting.core as adr

document = {
    "schema_version": "1.0",
    "app_id": "thermal-run-42",
    "tags": [{"report": "thermal_run_42"}],
    "metadata": {"producer": "adr-mechanical", "producer_version": "2026R1"},
    "items": [
        {
            "item_type": "text",
            "name": "Summary",
            "tags": [{"section": "intro"}],
            "value": "Simulation completed successfully.",
        },
        {
            "item_type": "html",
            "name": "Notes",
            "tags": [{"section": "intro"}],
            "value": "<p>All results within range.</p>",
        },
        {
            "item_type": "table",
            "name": "Probe Table",
            "tags": [{"section": "results"}],
            "columns": ["time", "T_max", "T_min"],
            "rows": [[0.0, 300.1, 290.0], [1.0, 320.5, 295.2]],
            "plot": "line",
            "properties": [{"table_title": "Probe temperatures"}],
        },
        {
            "item_type": "tree",
            "name": "Mesh",
            "tags": [{"section": "results"}],
            "nodes": [{"name": "Assembly", "children": [{"name": "Part A"}, {"name": "Part B"}]}],
        },
    ],
}

###############################################################################
# Write it next to the media it references
# ----------------------------------------
# Relative media paths resolve against the directory holding the document, so
# keeping the JSON beside its images keeps the document portable.

run_directory = Path("thermal_run_42")
run_directory.mkdir(exist_ok=True)

document_path = run_directory / "report.json"
document_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

###############################################################################
# Import it
# ---------
# ``on_error="collect"`` is the default: every item is attempted and any
# failures are reported on the result rather than raised.

adr_service = adr.Service(ansys_installation=r"C:\Program Files\ANSYS Inc\v261")
adr_service.connect(url="http://localhost:8010")

result = adr_service.import_from_json(document_path)

###############################################################################
# Inspect the result
# ------------------
# ``templates_created`` counts every node of every template tree, not just the
# roots.

print(f"schema version:    {result.schema_version}")
print(f"app id:            {result.app_id}")
print(f"templates created: {result.templates_created}")
print(f"items saved:       {result.items_saved}")
print(f"clean import:      {result.ok}")

for failure in result.failures:
    print(f"  failed: {failure.name} ({failure.item_type}): {failure.error}")

###############################################################################
# View the report
# ---------------

adr_service.visualize_report()
