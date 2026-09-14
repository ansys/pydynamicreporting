"""Tag normalization helpers for ADR exchange documents."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def normalize_tags(raw_tags: Any) -> str:
    """Normalize ADR tags into the space-delimited string format the backend expects."""
    if raw_tags is None:
        return ""
    if isinstance(raw_tags, str):
        return raw_tags

    values: list[str] = []
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

    return " ".join(part for part in values if part)


def combine_tags(*parts: Any) -> str:
    """Combine tag payloads by normalizing each part and joining the non-empty results."""
    normalized_parts: list[str] = []
    for part in parts:
        tag_text = normalize_tags(part)
        if tag_text:
            normalized_parts.append(tag_text)
    return " ".join(normalized_parts)
