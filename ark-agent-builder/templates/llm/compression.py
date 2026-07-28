"""Context Compression：messages 超限時壓縮中間段。"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# 估算：1 token ≈ 4 英文字元 / 2 中文字元
CHARS_PER_TOKEN = 3  # 取中間值
DEFAULT_MAX_TOKENS = 25000  # 預設上限（留餘量給 response）
THRESHOLD_RATIO = 0.85  # 85% 時觸發壓縮
KEEP_FIRST = 1  # 保留最前 N 輪（含 system context 的 user 第一輪）
KEEP_LAST = 3  # 保留最後 N 輪


def estimate_tokens(messages: list[dict]) -> int:
    """粗估 messages 總 token 數。"""
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        parts = msg.get("parts", [])
        if content:
            total_chars += len(content)
        for p in parts:
            if isinstance(p, dict):
                if "text" in p:
                    total_chars += len(p["text"])
                elif "function_call" in p:
                    total_chars += len(str(p["function_call"]))
                elif "function_response" in p:
                    total_chars += len(str(p["function_response"]))
    return total_chars // CHARS_PER_TOKEN


def should_compress(messages: list[dict], max_tokens: int = DEFAULT_MAX_TOKENS) -> bool:
    """判斷是否需要壓縮。"""
    estimated = estimate_tokens(messages)
    threshold = int(max_tokens * THRESHOLD_RATIO)
    return estimated > threshold


def compress_messages(
    messages: list[dict],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[dict]:
    """壓縮 messages：保留頭尾，中間摘要。

    策略：
    1. 保留前 KEEP_FIRST 輪（使用者初始意圖）
    2. 保留後 KEEP_LAST 輪（最近 context）
    3. 中間段替換為一個摘要 message

    不呼叫 LLM（避免額外延遲和費用），用簡單萃取。
    """
    if not should_compress(messages, max_tokens):
        return messages

    total = len(messages)
    if total <= KEEP_FIRST + KEEP_LAST + 1:
        # 太短不壓
        return messages

    first_part = messages[:KEEP_FIRST]
    last_part = messages[-KEEP_LAST:]
    middle_part = messages[KEEP_FIRST:-KEEP_LAST]

    # 從中間段萃取摘要
    summary = _extract_summary(middle_part)

    compressed = (
        first_part
        + [{"role": "user", "content": f"[context compressed: {summary}]"}]
        + last_part
    )

    original_tokens = estimate_tokens(messages)
    compressed_tokens = estimate_tokens(compressed)
    log.info(
        "Messages compressed: %d → %d msgs, ~%d → ~%d tokens",
        total, len(compressed), original_tokens, compressed_tokens,
    )

    return compressed


def _extract_summary(middle: list[dict]) -> str:
    """從中間段萃取關鍵資訊（不用 LLM）。"""
    tool_calls = []
    topics = []

    for msg in middle:
        parts = msg.get("parts", [])
        content = msg.get("content", "")

        # 收集 tool calls
        for p in parts:
            if isinstance(p, dict) and "function_call" in p:
                fc = p["function_call"]
                tool_calls.append(fc.get("name", "unknown"))

        # 收集 user messages 的前 30 字
        if msg.get("role") == "user" and content:
            topics.append(content[:30])

    parts = []
    if tool_calls:
        unique_tools = list(dict.fromkeys(tool_calls))  # 去重保序
        parts.append(f"used tools: {', '.join(unique_tools)}")
    if topics:
        parts.append(f"discussed: {'; '.join(topics[:3])}")

    return " | ".join(parts) if parts else f"{len(middle)} messages omitted"
