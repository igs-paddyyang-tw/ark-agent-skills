"""Output Parser — _extract_conclusion 四步清洗。

用途：從 kiro-cli / LLM 的 raw stdout 中提取乾淨結論文字。
四步驟：
  1. 移除 ANSI escape sequences
  2. 取最後一個 JSON block（模型偶爾用工具，kiro-cli 回顯參數）
  3. 去除 `> ` 前綴（kiro-cli 引用格式）
  4. 去除 `▸ Time: ...` 尾巴（kiro-cli 計時輸出）
"""
from __future__ import annotations

import json
import re

# ANSI escape 正則
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07")

# JSON block 正則（貪婪匹配最後一個）
_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)

# kiro-cli 引用前綴
_QUOTE_PREFIX_RE = re.compile(r"^> ", re.MULTILINE)

# kiro-cli 計時尾巴
_TIME_SUFFIX_RE = re.compile(r"▸ Time:.*$", re.MULTILINE)


def extract_conclusion(raw: str) -> str:
    """從 raw LLM/CLI 輸出中提取乾淨結論。

    Args:
        raw: 原始輸出字串（可能含 ANSI、JSON、引用前綴、計時）

    Returns:
        清洗後的純文字結論。
    """
    if not raw:
        return ""

    # Step 1: 移除 ANSI escape sequences
    text = _ANSI_RE.sub("", raw)

    # Step 2: 取最後一個 JSON（若存在）
    text = _extract_last_json_or_text(text)

    # Step 3: 去除 `> ` 前綴
    text = _QUOTE_PREFIX_RE.sub("", text)

    # Step 4: 去除 `▸ Time: ...` 尾巴
    text = _TIME_SUFFIX_RE.sub("", text)

    return text.strip()


def _extract_last_json_or_text(text: str) -> str:
    """嘗試取最後一個 JSON block 的內容；無 JSON 則回傳原文。"""
    matches = _JSON_BLOCK_RE.findall(text)
    if not matches:
        return text

    last_json = matches[-1]
    try:
        parsed = json.loads(last_json)
        # 如果是 dict 且有 output/text/content 欄位，取其值
        if isinstance(parsed, dict):
            for key in ("output", "text", "content", "result"):
                if key in parsed and isinstance(parsed[key], str):
                    return parsed[key]
        # 整個 JSON 有效但無已知欄位，回傳原文（排除工具參數）
        return text
    except (json.JSONDecodeError, ValueError):
        return text
