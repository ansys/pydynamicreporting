from __future__ import annotations

from pathlib import Path

from unittest.mock import MagicMock, patch

import pytest

from ansys.dynamicreporting.core.serverless.adr import ADR
from ansys.dynamicreporting.core.utils.exchange import ExchangeDocument, normalize_tags


@pytest.fixture
def sample_json(tmp_path: Path):
    payload = {
        "schema_version": "1.0",
        "app_id": "demo-app",
        "tags": [{"report": "demo"}],
        "items": [
            {
                "item_type": "text",
                "name": "Summary",
                "tags": [{"section": "intro"}],
                "value": "Hello world",
            },
            {
                "item_type": "image",
                "name": "Plot",
                "tags": [{"section": "results"}],
                "src": "plot.png",
            },
        ],
    }
    path = tmp_path / "exchange.json"
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    return path


def test_exchange_document_parses_json_file(sample_json: Path):
    doc = ExchangeDocument.from_json_file(sample_json)

    assert doc.app_id == "demo-app"
    assert doc.schema_version == "1.0"
    assert len(doc.items) == 2
    assert doc.items[0].item_type == "text"


def test_exchange_document_accepts_legacy_src_alias():
    doc = ExchangeDocument.model_validate(
        {
            "app_id": "demo-app",
            "tags": [{"report": "demo"}],
            "items": [
                {
                    "item_type": "image",
                    "name": "legacy",
                    "tags": [{"section": "results"}],
                    "src": "legacy.png",
                }
            ],
        }
    )

    assert doc.items[0].path == "legacy.png"


def test_normalize_tags_handles_scalar_values():
    assert normalize_tags("already-a-string") == "already-a-string"
    assert normalize_tags(42) == "42"


def test_adr_import_from_json_delegates_to_importer():
    adr = ADR.__new__(ADR)
    adr._logger = MagicMock()

    with patch(
        "ansys.dynamicreporting.core.serverless.exchange_importer.ExchangeImporter"
    ) as importer_cls:
        importer = importer_cls.return_value
        importer.import_file.return_value = {"ok": True}

        result = adr.import_from_json("report.json")

    assert result == {"ok": True}
    importer_cls.assert_called_once()
    importer.import_file.assert_called_once_with("report.json", on_error="collect")
