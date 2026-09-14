"""Enumerations used by the ADR exchange contract."""

from __future__ import annotations

from enum import Enum


class ItemType(str, Enum):
    """Known item payload types in the ADR exchange contract."""

    TEXT = "text"
    HTML = "html"
    TABLE = "table"
    TREE = "tree"
    IMAGE = "image"
    ANIMATION = "animation"
    SCENE = "scene"
    FILE = "file"


class TemplateType(str, Enum):
    """Known template/report types in the ADR exchange contract."""

    BASIC = "basic"
    PANEL = "panel"
    BOX = "box"
    TABS = "tabs"
