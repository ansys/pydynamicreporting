# Copyright (C) 2023 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ansys.dynamicreporting.core.serverless import (
    BasicLayout,
    File,
    Image,
    Scene,
    String,
    Table,
    Tree,
)
from ansys.dynamicreporting.core.adr_utils import get_logger
from ansys.dynamicreporting.core.utils.json_importer_models import (
    FileItemModel,
    ImageItemModel,
    ReportItemsModel,
    SceneItemModel,
    TableItemModel,
    TextItemModel,
    TreeItemModel,
)


class ServerlessReportItemImporter:
    """Imports ADR report items from a JSON file in serverless mode.

    Reads a structured JSON file that describes report items (text, tables,
    images, files, scenes, trees), creates a default ``BasicLayout`` template,
    and persists all items to the configured ADR serverless instance.
    """

    def __init__(self, adr: Any) -> None:
        """Initialize the serverless importer.

        Parameters
        ----------
        adr : Any
            Configured ADR serverless client instance used to create templates and items.

        Raises
        ------
        ValueError
            If ``adr`` is ``None``.
        """
        if adr is None:
            raise ValueError("ADR instance must be provided")

        self._adr = adr
        self.template_tags: str = ""
        self._logger = get_logger()

    def _normalize_tags(self, raw_tags: Any) -> str:
        """Convert JSON-style tags to the string format expected by ADR."""
        if raw_tags is None:
            return ""

        if isinstance(raw_tags, str):
            return raw_tags

        values = []

        if isinstance(raw_tags, dict):
            raw_tags = [raw_tags]

        if isinstance(raw_tags, list):
            for entry in raw_tags:
                if isinstance(entry, dict):
                    for key, value in entry.items():
                        if value is not None:
                            values.append(f"{key}={value}")
                elif entry is not None:
                    values.append(str(entry))
        else:
            values.append(str(raw_tags))

        return " ".join(v for v in values if v)

    def _import_json_items(self, json_file_path: str | Path) -> ReportItemsModel:
        """Load a JSON file, create a default template, and save all report items to ADR.

        Parameters
        ----------
        json_file_path : str or Path
            Path to the JSON file containing the serialized report items.

        Returns
        -------
        ReportItemsModel
            The parsed report items model loaded from the JSON file.
        """
        report_items = ReportItemsModel.from_json_file(json_file_path)
        self._logger.info(
            "Loaded report items JSON: app_id=%s, total_items=%d",
            report_items.app_id,
            len(report_items.items),
        )
        self.template_tags = self._normalize_tags(report_items.tags)
        self._create_default_template(report_items.app_id)
        self._save_items(report_items)
        return report_items

    def _create_default_template(self, app_id: str) -> None:
        """Create a simple root template used by imported report items."""

        self._logger.info("Creating default template with tags: %s", self.template_tags)
        template = self._adr.create_template(
            BasicLayout,
            name=app_id,
            parent=None,
            tags=self.template_tags,
        )
        template.params = f'{{"HTML": "<h1>{app_id}</h1>"}}'
        template.save()

    def _build_tags(self, item_tags: Any) -> str:
        """Combine template tags and item tags into one ADR tag string."""
        parts = [self.template_tags, self._normalize_tags(item_tags)]
        return " ".join(part for part in parts if part)

    def _flatten_properties(self, properties: Any) -> dict[str, Any]:
        """Merge a list of property dicts into a single flat dict.

        The JSON schema represents item properties as an array of single-key
        objects (e.g. ``[{"format": "floatdot0"}, {"ytitle": "Values"}]``).
        This helper collapses that list into one dict so attributes can be set
        with a single loop.

        Parameters
        ----------
        properties : list or None
            Raw ``properties`` value from the parsed item model.

        Returns
        -------
        dict
            Flat mapping of property name → value.  Returns an empty dict
            when *properties* is ``None`` or empty.
        """
        if not properties:
            return {}
        flat: dict[str, Any] = {}
        for entry in properties:
            if isinstance(entry, dict):
                flat.update(entry)
        return flat

    def _apply_properties(self, adr_item: Any, properties: Any) -> None:
        """Set item attributes from the JSON ``properties`` list before saving.

        Each entry in *properties* is a dict whose keys map directly to ADR
        item attribute names (e.g. ``plot``, ``format``, ``xtitle``,
        ``source``, ``sequence``).  Attributes are set with :func:`setattr`;
        for :class:`~ansys.dynamicreporting.core.serverless.item.Table` items
        the values are automatically included in the pickled payload by
        ``Table.save()``.  Base item fields such as ``source`` and ``sequence``
        are persisted through the normal ORM save path.

        Parameters
        ----------
        adr_item : Any
            ADR item instance whose attributes are to be populated.
        properties : list or None
            Raw ``properties`` value from the parsed item model.
        """
        flat = self._flatten_properties(properties)
        for key, value in flat.items():
            if not isinstance(key, str) or key.startswith("_"):
                continue

            # Guard against overriding actual methods.  Check the class
            # hierarchy rather than the instance so that MagicMock objects
            # used in tests (whose instance attributes are all callable) are
            # handled correctly.
            cls_attr = getattr(type(adr_item), key, None)
            if callable(cls_attr) and not isinstance(cls_attr, property):
                self._logger.warning(
                    "Skipping property '%s' for item '%s' because it would override a method",
                    key,
                    getattr(adr_item, "name", ""),
                )
                continue

            setattr(adr_item, key, value)
            self._logger.debug(
                "Applied property '%s' to item '%s'",
                key,
                getattr(adr_item, "name", ""),
            )

    def _save_item(self, item: Any) -> Any:
        """Save one item to ADR based on item class name."""
        if isinstance(item, TextItemModel):
            return self._save_text_item(item)
        if isinstance(item, TableItemModel):
            return self._save_table_item(item)
        if isinstance(item, ImageItemModel):
            return self._save_image_item(item)
        if isinstance(item, FileItemModel):
            return self._save_file_item(item)
        if isinstance(item, SceneItemModel):
            return self._save_scene_item(item)
        if isinstance(item, TreeItemModel):
            return self._save_tree_item(item)

        self._logger.warning("Unsupported item type skipped: %s", type(item).__name__)
        return None

    def _create_and_save_item(
        self,
        item_type: Any,
        *,
        name: str,
        content: Any,
        tags: Any,
        properties: Any = None,
        save: bool = True,
    ) -> Any:
        """Create and persist an ADR item with normalized tags and properties.

        Parameters
        ----------
        item_type : Any
            ADR item class to instantiate (e.g. ``String``, ``Table``).
        name : str
            Item name.
        content : Any
            Primary payload for the item (type-dependent).
        tags : Any
            Raw tags from the JSON model; combined with template-level tags.
        properties : list or None, optional
            Raw ``properties`` list from the JSON model.  Each entry is a
            dict whose keys are ADR item attribute names.  Attributes are set
            before the item is saved.  Defaults to ``None`` (no extra
            properties applied).
        save : bool, optional
            When ``True`` (default) the item is saved immediately.  Pass
            ``False`` to defer saving so the caller can set additional
            attributes (e.g. table column labels) before persisting.

        Returns
        -------
        Any
            The created ADR item instance.
        """
        adr_item = self._adr.create_item(
            item_type,
            name=name,
            content=content,
            tags=self._build_tags(tags),
        )
        self._apply_properties(adr_item, properties)
        if save:
            adr_item.save()
        return adr_item

    def _save_text_item(self, item: Any) -> Any:
        """Save text item as String."""
        text_item = self._create_and_save_item(
            String,
            name=item.name,
            content=item.value,
            tags=item.tags,
            properties=item.properties,
        )
        self._logger.info("Saved text item: %s", item.name)
        return text_item

    def _save_table_item(self, item: Any) -> Any:
        """Save table item."""
        # Convert rows to numpy array.  TableContent accepts float ("f") or byte-string
        # ("S") dtypes.  Attempt numeric conversion first; fall back to bytes so that
        # tables with textual or mixed-type columns are preserved rather than skipped.
        try:
            data = np.array(item.data.rows, dtype="float")
        except (ValueError, TypeError):
            data = np.array(item.data.rows, dtype="|S20")

        # Create table item with data
        table_item = self._create_and_save_item(
            Table,
            name=item.name,
            content=data,
            tags=item.tags,
            properties=item.properties,
            save=False,
        )

        def _column_name(column):
            if isinstance(column, str):
                return column
            return column.name

        # Set table metadata from columns
        labels_row = [_column_name(col) for col in item.data.columns]
        table_item.labels_row = labels_row

        # Set axis labels
        if len(item.data.columns) > 0:
            table_item.xaxis = _column_name(item.data.columns[0])

        if len(item.data.columns) > 1:
            table_item.yaxis = [_column_name(col) for col in item.data.columns[1:]]

        table_item.save()
        self._logger.info("Saved table item: %s", item.name)
        return table_item

    def _save_image_item(self, item: Any) -> Any:
        """Save image item."""
        image_item = self._create_and_save_item(
            Image,
            name=item.name,
            content=item.src,
            tags=item.tags,
            properties=item.properties,
        )
        self._logger.info("Saved image item: %s", item.name)
        return image_item

    def _save_file_item(self, item: Any) -> Any:
        """Save file item."""
        file_item = self._create_and_save_item(
            File,
            name=item.name,
            content=item.src,
            tags=item.tags,
            properties=item.properties,
        )
        self._logger.info("Saved file item: %s", item.name)
        return file_item

    def _save_scene_item(self, item: Any) -> Any:
        """Save scene item."""
        scene_item = self._create_and_save_item(
            Scene,
            name=item.name,
            content=item.src,
            tags=item.tags,
            properties=item.properties,
        )
        self._logger.info("Saved scene item: %s", item.name)
        return scene_item

    def _save_tree_item(self, item: Any) -> Any:
        """Save tree item."""
        # Convert tree nodes to list structure
        tree_data = [
            self._flatten_tree_node(node, f"node_{idx}") for idx, node in enumerate(item.data.nodes)
        ]

        # Create tree item
        tree_item = self._create_and_save_item(
            Tree,
            name=item.name,
            content=tree_data,
            tags=item.tags,
            properties=item.properties,
        )
        self._logger.info("Saved tree item: %s", item.name)
        return tree_item

    def _flatten_tree_node(self, node: Any, parent_key: str = "", level: int = 0) -> dict[str, Any]:
        """Flatten a tree node to a dictionary with required ``key`` and ``value`` fields.

        Parameters
        ----------
        node : Any
            Tree node model with ``name`` and ``children`` attributes.
        parent_key : str, optional
            Prefix used to build a unique key for this node, by default ``""``.
        level : int, optional
            Depth of this node in the tree, by default ``0``.

        Returns
        -------
        dict
            Dictionary with ``key``, ``value``, ``name``, ``level``, and
            ``children`` fields, where ``children`` is a list of recursively
            flattened child dictionaries.
        """
        node_key = f"{parent_key}_{node.name}".replace(" ", "_").lower()

        node_dict = {
            "key": node_key,
            "value": node.name,
            "name": node.name,
            "level": level,
            "children": [],
        }

        # Recursively add children
        for idx, child in enumerate(node.children):
            child_key = f"{node_key}_child_{idx}"
            node_dict["children"].append(self._flatten_tree_node(child, child_key, level + 1))

        return node_dict

    def _save_items(self, data_items: Any) -> None:
        """Save all items from ``data_items.items`` while continuing on item-level failures."""
        for item in data_items.items:
            try:
                self._save_item(item)
            except Exception:
                item_id = getattr(item, "id", "<unknown>")
                self._logger.exception("Error saving item %s", item_id)
