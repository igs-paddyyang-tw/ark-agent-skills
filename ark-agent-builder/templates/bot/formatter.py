"""TG 訊息格式化 — HTML/Markdown + 自動分段。

泛化自 ninja-bot src/bot/formatter.py。
"""
from __future__ import annotations

import re

MAX_TG_LENGTH = 4096


def format_html(text: str) -> str:
    """清洗 HTML，保留 TG 支援的標籤。"""
    allowed = {"b", "i", "u", "s", "code", "pre", "a"}
    # 移除不支援的標籤
    text = re.sub(r"<(?!/?)(\w+)[^>]*>", lambda m: m.group(0) if m.group(1) in allowed else "", text)
    text = re.sub(r"</(\w+)>", lambda m: m.group(0) if m.group(1) in allowed else "", text)
    return text


def split_message(text: str, max_len: int = MAX_TG_LENGTH) -> list[str]:
    """將長訊息分段，優先在段落邊界切割。"""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # 在 max_len 範圍內找最後一個換行
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks
