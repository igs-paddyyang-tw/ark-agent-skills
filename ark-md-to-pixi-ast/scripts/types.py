"""資料結構定義 — Token / Node / LayoutConfig / TokenType。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TokenType(str, Enum):
    """Markdown 節點類型。"""

    HEADING1 = "Heading1"
    HEADING2 = "Heading2"
    HEADING3 = "Heading3"
    TEXT = "Text"
    CODE_BLOCK = "CodeBlock"
    LIST_ITEM = "ListItem"
    BLOCKQUOTE = "Blockquote"
    DIVIDER = "Divider"


@dataclass
class Token:
    """Parser 產出的中間表示。"""

    token_type: TokenType
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class Node:
    """Layout 計算後的渲染節點。"""

    id: str
    node_type: str
    text: str
    font_size: int
    font_family: str
    x: int
    y_offset: int
    max_width: int | None = None
    word_wrap: bool | None = None
    background_color: str | None = None


@dataclass
class LayoutConfig:
    """可調整的 Layout 參數。"""

    viewport_width: int = 1280
    viewport_height: int = 720
    margin_left: int = 80
    max_width: int = 960
    spacing: dict[str, int] = field(default_factory=lambda: {
        "Heading1": 80,
        "Heading2": 60,
        "Heading3": 50,
        "Text": 40,
        "CodeBlock": 80,
        "ListItem": 30,
        "Blockquote": 50,
        "Divider": 30,
    })
