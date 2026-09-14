"""Serverless backend adapter for the ADR exchange importer."""

from __future__ import annotations

from typing import Any

from ansys.dynamicreporting.core.adr_utils import get_logger
from ansys.dynamicreporting.core.serverless import (
    BasicLayout,
    File,
    Image,
    Scene,
    String,
    Table,
    Tree,
)
from ansys.dynamicreporting.core.utils.exchange.mapping._common import (
    apply_properties,
    flatten_tree,
    rows_to_array,
)


class ServerlessExchangeBackend:
    """Translate exchange models into the current serverless ADR API."""

    def __init__(self, adr: Any) -> None:
        self._adr = adr
        self.logger = get_logger()

    def ensure_ready(self) -> None:
        return None

    def create_template(self, model: Any, parent: Any = None) -> Any:
        template = self._adr.create_template(
            BasicLayout,
            name=model.name,
            parent=parent,
            tags=" ".join(
                f"{key}={value}"
                for entry in model.tags
                for key, value in entry.items()
                if value is not None
            ),
        )
        if model.html:
            template.params = f'{{"HTML": "{model.html}"}}'
        if model.item_filter:
            template.item_filter = model.item_filter
        if model.sort_selection:
            template.set_sort_selection(model.sort_selection)
        if model.sort_fields:
            template.set_sort_fields(model.sort_fields)
        if model.filter_mode:
            template.set_filter_mode(model.filter_mode)
        if model.column_count is not None:
            template.column_count = model.column_count
        if model.column_widths is not None:
            template.column_widths = model.column_widths
        template.save()
        return template

    def save_item(self, model: Any, doc_tags: str) -> Any:
        item_tags = self._coerce_tags(model.tags, doc_tags)
        if model.item_type == "text":
            item = self._adr.create_item(
                String, name=model.name, content=model.value, tags=item_tags
            )
        elif model.item_type == "html":
            item = self._adr.create_item(
                String, name=model.name, content=model.value, tags=item_tags
            )
        elif model.item_type == "table":
            rows = model.rows or model.data.rows if getattr(model, "data", None) is not None else []
            data = rows_to_array(rows)
            item = self._adr.create_item(
                Table, name=model.name, content=data, tags=item_tags, save=False
            )
            item.labels_row = [
                self._column_name(column) for column in (model.columns or model.data.columns)
            ]
            if model.columns or model.data.columns:
                item.xaxis = self._column_name((model.columns or model.data.columns)[0])
                if len((model.columns or model.data.columns)) > 1:
                    item.yaxis = [
                        self._column_name(col) for col in (model.columns or model.data.columns)[1:]
                    ]
            if getattr(model, "plot", None):
                item.plot = model.plot
            if getattr(model, "format", None):
                item.format = model.format
            if getattr(model, "xaxis", None):
                item.xaxis = model.xaxis
            if getattr(model, "yaxis", None):
                item.yaxis = model.yaxis
            item.save()
            return item
        elif model.item_type == "tree":
            tree_data = flatten_tree(model.nodes)
            item = self._adr.create_item(Tree, name=model.name, content=tree_data, tags=item_tags)
        elif model.item_type in {"image", "animation", "scene", "file"}:
            kind = {
                "image": Image,
                "animation": Image,
                "scene": Scene,
                "file": File,
            }[model.item_type]
            item = self._adr.create_item(kind, name=model.name, content=model.path, tags=item_tags)
        else:
            raise ValueError(f"Unsupported item type: {model.item_type}")

        apply_properties(item, model.properties)
        item.save()
        return item

    @staticmethod
    def _coerce_tags(model_tags: list[dict[str, Any]] | None, doc_tags: str) -> str:
        parts = [doc_tags]
        if model_tags:
            parts.append(
                " ".join(
                    f"{key}={value}"
                    for entry in model_tags
                    for key, value in entry.items()
                    if value is not None
                )
            )
        return " ".join(part for part in parts if part)

    @staticmethod
    def _column_name(column: Any) -> str:
        if isinstance(column, str):
            return column
        return column.name
