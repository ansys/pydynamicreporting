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

"""Backend-agnostic orchestration for ADR JSON imports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .models import ImportDocument, TemplatePayload
from .parser import load_document
from .result import ImportResult, ItemFailure
from .tags import combine_tags

ON_ERROR_STRATEGIES = ("collect", "raise")
"""Accepted ``on_error`` strategies."""


@runtime_checkable
class ImportBackend(Protocol):
    """Seam between the importer core and a concrete ADR backend."""

    @property
    def logger(self) -> Any:  # pragma: no cover - structural protocol member
        """Logger used for import diagnostics."""

    def ensure_ready(self) -> None:  # pragma: no cover - structural protocol member
        """Raise if the backend cannot accept writes."""

    def create_template(
        self, model: TemplatePayload, parent: Any
    ) -> Any:  # pragma: no cover - structural protocol member
        """Create and persist one template, attached to ``parent``."""

    def save_item(
        self, model: Any, doc_tags: str
    ) -> Any:  # pragma: no cover - structural protocol member
        """Create and persist one item."""


class JSONImporter:
    """Drives an :class:`ImportBackend` from a validated import document."""

    def __init__(self, backend: ImportBackend) -> None:
        self._backend = backend

    @property
    def _logger(self) -> Any:
        return getattr(self._backend, "logger", None)

    @staticmethod
    def _default_root(document: ImportDocument) -> TemplatePayload:
        """Build the implicit root template for an items-only document.

        This is a real :class:`TemplatePayload`, so every field an adapter
        reads is present. Fabricating an ad-hoc object here would raise
        ``AttributeError`` the moment an adapter touched a field it omitted.
        """
        return TemplatePayload(
            template_type="basic",
            name=document.app_id,
            tags=document.tags,
            params=dict(document.metadata),
        )

    def _create_tree(self, model: TemplatePayload, parent: Any, result: ImportResult) -> Any:
        """Create ``model`` and its whole subtree, parent-first."""
        node = self._backend.create_template(model, parent)
        result.templates_created += 1
        for child in model.children:
            self._create_tree(child, node, result)
        return node

    def import_document(
        self, document: ImportDocument, *, on_error: str = "collect"
    ) -> ImportResult:
        """Import a validated document through the backend.

        Parameters
        ----------
        document : ImportDocument
            Validated document.
        on_error : {'collect', 'raise'}, default: 'collect'
            ``'collect'`` records per-item failures and continues;
            ``'raise'`` stops at the first failure.

        Returns
        -------
        ImportResult
            Counts, root template GUIDs, and any per-item failures.

        Raises
        ------
        ValueError
            If ``on_error`` is not a known strategy.
        """
        if on_error not in ON_ERROR_STRATEGIES:
            allowed = ", ".join(repr(name) for name in ON_ERROR_STRATEGIES)
            raise ValueError(f"on_error must be one of [{allowed}], got {on_error!r}")

        self._backend.ensure_ready()

        result = ImportResult(
            schema_version=document.schema_version,
            app_id=document.app_id,
        )

        # Structure is a precondition for content: a template failure is fatal
        # and is never absorbed by the collect strategy.
        roots = document.templates or (self._default_root(document),)
        for root_model in roots:
            root = self._create_tree(root_model, None, result)
            guid = getattr(root, "guid", None)
            if guid is not None:
                result.root_guids.append(str(guid))

        doc_tags = combine_tags(document.tags)
        for index, item in enumerate(document.items):
            try:
                self._backend.save_item(item, doc_tags)
            except Exception as exc:
                if self._logger is not None:
                    self._logger.error(
                        "Failed to import item %r (%s): %s", item.name, item.item_type, exc
                    )
                if on_error == "raise":
                    raise
                result.failures.append(
                    ItemFailure(
                        index=index,
                        name=item.name,
                        item_type=item.item_type,
                        error=str(exc),
                    )
                )
            else:
                result.items_saved += 1

        return result

    def import_file(
        self,
        path: str | Path,
        *,
        on_error: str = "collect",
        base_dir: str | None = None,
        strict_keys: bool = False,
    ) -> ImportResult:
        """Read, validate, and import a JSON document.

        Parameters
        ----------
        path : str or pathlib.Path
            Path to the JSON document.
        on_error : {'collect', 'raise'}, default: 'collect'
            Per-item failure strategy.
        base_dir : str, optional
            Directory that relative media paths resolve against. Defaults to
            the directory containing ``path``.
        strict_keys : bool, default: False
            Treat unknown keys as validation errors.

        Returns
        -------
        ImportResult
            Counts, root template GUIDs, and any per-item failures.
        """
        document = load_document(
            path, base_dir=base_dir, strict_keys=strict_keys, logger=self._logger
        )
        return self.import_document(document, on_error=on_error)
