from __future__ import annotations

import json
from pathlib import Path

from ansys.dynamicreporting.core.serverless.item import ItemType
from ansys.dynamicreporting.core.utils.exchange import ItemType as ExchangeItemType, TemplateType
from ansys.dynamicreporting.core.utils.exchange.schema import ExchangeDocument


def test_schema_drift_guard_matches_exchange_enums():
    assert ExchangeItemType.TEXT.value == "text"
    assert ExchangeItemType.TABLE.value == "table"
    assert TemplateType.BASIC.value == "basic"
    assert ItemType.STRING.value == "string"


def test_committed_schema_matches_generated_schema():
    generated = ExchangeDocument.model_json_schema()
    committed = json.loads(Path("adr_exchange.schema.json").read_text(encoding="utf-8"))
    assert generated == committed
