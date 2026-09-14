"""Export support for ADR exchange documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import ExchangeDocument


class ExchangeExporter:
    """Serialize an exchange document to JSON for round-trip export."""

    def __init__(self, document: ExchangeDocument) -> None:
        self._document = document

    def export_document(self) -> ExchangeDocument:
        return self._document

    def export_file(self, path: str | Path, *, indent: int = 2) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self._document.to_json(indent=indent), encoding="utf-8")
        return target
