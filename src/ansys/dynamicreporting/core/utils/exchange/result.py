"""Result objects returned by the exchange importer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ItemFailure:
    """Information about a single failed import item."""

    index: int
    name: str
    item_type: str
    error: str


@dataclass
class ImportResult:
    """Summary returned from a JSON document import."""

    schema_version: str
    app_id: str
    templates_created: int = 0
    items_saved: int = 0
    failures: list[ItemFailure] = field(default_factory=list)
    root_guids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures
