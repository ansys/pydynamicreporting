JSON Importer Models (Utils)
============================

``ansys.dynamicreporting.core.utils.json_importer_models`` is the shared
validation layer for JSON report-item payloads.

- This is the place where Pydantic validation is defined for import payloads.
- It should be reused across server and serverless import paths.
- It exposes the ``ReportItemsModel`` entry point and item-type models used by
  JSON importers.

.. automodule:: ansys.dynamicreporting.core.utils.json_importer_models
   :members:
   :undoc-members:
   :show-inheritance:
