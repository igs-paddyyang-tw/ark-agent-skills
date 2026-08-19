"""Gemini API 快答路徑 — 簡化版單次對話。"""
from __future__ import annotations

import logging
from typing import Any

from .provider import get_default_provider, LLMResponse

log = logging.getLogger(__name__)


async def gemini_quick_chat(
    prompt: str,
    system: str = "",
    temperature: float = 0.7,
) -> str:
    """快速呼叫 Gemini（或當前 Provider）取得文字回應。

    適用於不需要 tool-use 的簡單問答場景。

    Args:
        prompt: 使用者訊息
        system: system prompt（可選）
        temperature: 創意度

    Returns:
        LLM 回覆文字。失敗時回傳空字串。
    """
    provider = get_default_provider()
    messages = [{"role": "user", "content": prompt}]

    try:
        response: LLMResponse = await provider.chat(
            messages=messages,
            system=system,
            temperature=temperature,
        )
        return response.text or ""
    except Exception as e:
        log.error("Gemini quick chat failed: %s", e)
        return ""


async def gemini_structured_chat(
    prompt: str,
    system: str = "",
    tools: list[dict] | None = None,
    temperature: float = 0.7,
) -> LLMResponse:
    """結構化呼叫 — 支援 function calling。

    Args:
        prompt: 使用者訊息
        system: system prompt
        tools: function declarations
        temperature: 創意度

    Returns:
        完整 LLMResponse（text 或 function_calls）。
    """
    provider = get_default_provider()
    messages = [{"role": "user", "content": prompt}]

    try:
        return await provider.chat(
            messages=messages,
            system=system,
            tools=tools,
            temperature=temperature,
        )
    except Exception as e:
        log.error("Gemini structured chat failed: %s", e)
        return LLMResponse(text=f"Error: {e}")
