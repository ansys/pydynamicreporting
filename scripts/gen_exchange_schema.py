"""Generate the committed ADR exchange JSON schema file."""

from __future__ import annotations

import json
from pathlib import Path

from ansys.dynamicreporting.core.utils.exchange.schema import ExchangeDocument


OUTPUT_PATH = Path(__file__).resolve().parent.parent / "adr_exchange.schema.json"


def main() -> None:
    payload = ExchangeDocument.model_json_schema()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
