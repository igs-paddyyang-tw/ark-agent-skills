"""簡單 LLM 呼叫（不帶 tools）— 統一走 Provider 層。

用於：daily_log 摘要、consolidate 蒸餾、recommend 草稿等內部模組。
對話請走 agent_loop()。
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def simple_chat(prompt: str, system: str = "") -> str | None:
    """呼叫 LLM（不帶 tools），回傳純文字或 None。

    統一走 Provider 層，改 .env LLM_PROVIDER 就換模型。
    """
    try:
        from src.llm.provider import get_default_provider
        provider = get_default_provider()
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            tools=None,
        )
        return response.text
    except Exception as e:
        log.error("simple_chat failed: %s", e)
        return None
