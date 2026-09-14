from __future__ import annotations

from unittest.mock import MagicMock, patch

from ansys.dynamicreporting.core import Service


def test_service_import_from_json_delegates_to_server_backend():
    service = Service.__new__(Service)
    service.logger = MagicMock()

    with patch("ansys.dynamicreporting.core.adr_service.ExchangeImporter") as importer_cls:
        importer = importer_cls.return_value
        importer.import_file.return_value = {"ok": True}

        result = service.import_from_json("report.json")

    assert result == {"ok": True}
    importer_cls.assert_called_once()
    importer.import_file.assert_called_once_with("report.json", on_error="collect")
