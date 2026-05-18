"""JSON Emitter — Node → JSON 字串。"""
from __future__ import annotations

import json

from .types import Node


def emit(nodes: list[Node]) -> str:
    """將 Node 列表序列化為 JSON 字串。

    只輸出非 None 欄位，使用 camelCase 命名。
    """
    result: dict = {"nodes": []}

    for node in nodes:
        entry: dict = {
            "id": node.id,
            "nodeType": node.node_type,
            "text": node.text,
            "fontSize": node.font_size,
            "fontFamily": node.font_family,
            "x": node.x,
            "yOffset": node.y_offset,
        }
        if node.max_width is not None:
            entry["maxWidth"] = node.max_width
        if node.word_wrap is not None:
            entry["wordWrap"] = node.word_wrap
        if node.background_color is not None:
            entry["backgroundColor"] = node.background_color

        result["nodes"].append(entry)

    return json.dumps(result, ensure_ascii=False, indent=2)
