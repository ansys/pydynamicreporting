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

"""Backend-agnostic orchestration for ADR JSON item imports.

Mirrors the template JSON import: validation and the per-item error policy
live here, and each backend passes in the callable that turns one validated
item into its own existing model, the way ``populate_template`` receives a
``create_template_func``.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Literal

from .mapping import combine_tags
from .models import ImportDocument, ImportResult, ItemFailure

OnError = Literal["collect", "raise"]
"""Per-item failure strategy accepted by :func:`import_items`."""

ON_ERROR_STRATEGIES: tuple[OnError, ...] = ("collect", "raise")
"""Accepted ``on_error`` strategies."""


def import_items(
    document: ImportDocument,
    populate_item: Callable[[dict[str, Any], str], object],
    *,
    on_error: OnError = "collect",
    logger: logging.Logger | None = None,
) -> ImportResult:
    """Create and persist every item of a validated document.

    Parameters
    ----------
    document : ImportDocument
        Validated document.
    populate_item : callable
        Backend hook called as ``populate_item(item_data, doc_tags)``. It must
        create and persist one item, raising on failure.
    on_error : {'collect', 'raise'}, default: 'collect'
        ``'collect'`` records per-item failures and continues;
        ``'raise'`` stops at the first failure.
    logger : logging.Logger, optional
        Logger used to report per-item failures.

    Returns
    -------
    ImportResult
        Counts and any per-item failures.

    Raises
    ------
    ValueError
        If ``on_error`` is not a known strategy.
    """
    if on_error not in ON_ERROR_STRATEGIES:
        allowed = ", ".join(repr(name) for name in ON_ERROR_STRATEGIES)
        raise ValueError(f"on_error must be one of [{allowed}], got {on_error!r}")

    result = ImportResult(schema_version=document.schema_version, app_id=document.app_id)

    doc_tags = combine_tags(document.tags)
    for index, item in enumerate(document.items):
        try:
            populate_item(item, doc_tags)
        except Exception as exc:
            if logger is not None:
                logger.error(
                    "Failed to import item %r (%s): %s", item["name"], item["item_type"], exc
                )
            if on_error == "raise":
                raise
            result.failures.append(ItemFailure(index, item["name"], item["item_type"], str(exc)))
        else:
            result.items_saved += 1

    return result
