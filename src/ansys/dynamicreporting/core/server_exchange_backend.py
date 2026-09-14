"""Server-side backend adapter for the ADR exchange importer."""

from __future__ import annotations

from typing import Any

from ansys.dynamicreporting.core.adr_item import Item
from ansys.dynamicreporting.core.utils.exchange.mapping._common import (
    apply_properties,
    rows_to_array,
)


class ServerExchangeBackend:
    """Bridge the exchange document model to the REST Service API."""

    def __init__(self, service: Any) -> None:
        self._service = service
        self.logger = service.logger

    def ensure_ready(self) -> None:
        return None

    def create_template(self, model: Any, parent: Any = None) -> Any:
        template = self._service.serverobj.create_template(
            name=model.name,
            parent=parent,
            report_type="Layout:basic",
        )
        if model.html:
            template.set_params({"HTML": model.html})
        if model.item_filter:
            template.set_filter(model.item_filter)
        if model.sort_selection:
            template.set_sort_selection(model.sort_selection)
        if model.sort_fields:
            template.set_sort_fields(model.sort_fields)
        if model.filter_mode:
            template.set_filter_mode(model.filter_mode)
        if model.column_count is not None:
            template.set_params({**template.get_params(), "column_count": model.column_count})
        if model.column_widths is not None:
            template.set_params({**template.get_params(), "column_widths": model.column_widths})
        return template

    def save_item(self, model: Any, doc_tags: str) -> Any:
        item = self._service.create_item(obj_name=model.name, source=model.source or "ADR")
        item.set_tags(doc_tags)
        if model.item_type == "text":
            item.item_text = model.value
        elif model.item_type == "html":
            item.item_text = model.value
        elif model.item_type == "table":
            rows = model.rows or model.data.rows if getattr(model, "data", None) is not None else []
            item.item_table = rows_to_array(rows)
            item.labels_row = [
                self._column_name(column) for column in (model.columns or model.data.columns)
            ]
            if model.columns or model.data.columns:
                item.xaxis = self._column_name((model.columns or model.data.columns)[0])
                if len((model.columns or model.data.columns)) > 1:
                    item.yaxis = [
                        self._column_name(col) for col in (model.columns or model.data.columns)[1:]
                    ]
            if model.plot:
                item.plot = model.plot
            if model.format:
                item.format = model.format
            if model.xaxis:
                item.xaxis = model.xaxis
            if model.yaxis:
                item.yaxis = model.yaxis
        elif model.item_type == "tree":
            item.item_tree = [
                {"key": f"node_{idx}", "name": node.name, "value": node.name, "children": []}
                for idx, node in enumerate(model.nodes)
            ]
        elif model.item_type in {"image", "animation", "scene", "file"}:
            setattr(item, f"item_{model.item_type}", model.path)
        else:
            raise ValueError(f"Unsupported item type: {model.item_type}")

        apply_properties(item, model.properties)
        item.set_tags(
            doc_tags
            + (" " + self._coerce_tags(model.tags) if self._coerce_tags(model.tags) else "")
        )
        return item

    @staticmethod
    def _coerce_tags(model_tags: list[dict[str, Any]] | None) -> str:
        if not model_tags:
            return ""
        return " ".join(
            f"{key}={value}"
            for entry in model_tags
            for key, value in entry.items()
            if value is not None
        )

    @staticmethod
    def _column_name(column: Any) -> str:
        if isinstance(column, str):
            return column
        return column.name
