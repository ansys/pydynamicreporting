"""Import orchestration for ADR exchange documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ansys.dynamicreporting.core.utils.exchange import (
    ExchangeDocument,
    ImportResult,
    ItemFailure,
    check_version,
)


class ExchangeImporter:
    """Shared core that feeds exchange documents to a backend adapter."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def import_document(
        self, document: ExchangeDocument, *, on_error: str = "collect"
    ) -> ImportResult:
        check_version(document.schema_version, getattr(self._backend, "logger", None))
        result = ImportResult(
            schema_version=document.schema_version,
            app_id=document.app_id,
        )

        if document.templates:
            for template in document.templates:
                self._backend.create_template(template, parent=None)
                result.templates_created += 1
        elif document.items:
            self._backend.create_template(
                type(
                    "_RootTemplate",
                    (),
                    {
                        "name": document.app_id,
                        "tags": [],
                        "item_filter": None,
                        "params": {},
                        "children": [],
                    },
                )(),
                parent=None,
            )
            result.templates_created += 1

        for index, item in enumerate(document.items):
            try:
                self._backend.save_item(item, self._tag_string(document.tags))
                result.items_saved += 1
            except Exception as exc:  # pragma: no cover - exercised by result semantics
                if on_error == "raise":
                    raise
                result.failures.append(
                    ItemFailure(
                        index=index,
                        name=getattr(item, "name", "<unknown>"),
                        item_type=getattr(item, "item_type", "unknown"),
                        error=str(exc),
                    )
                )

        return result

    def import_file(self, path: str | Path, *, on_error: str = "collect") -> ImportResult:
        return self.import_document(ExchangeDocument.from_json_file(path), on_error=on_error)

    @staticmethod
    def _tag_string(tags: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for entry in tags:
            for key, value in entry.items():
                if value is not None:
                    parts.append(f"{key}={value}")
        return " ".join(parts)
