"""LLM Router — 統一多模型呼叫，自動 fallback。"""
from __future__ import annotations

from src.llm import gemini_chat, openai_chat


def available_backends() -> list[str]:
    """列出可用的 LLM 後端。"""
    backends = []
    if gemini_chat.is_available():
        backends.append("gemini")
    if openai_chat.is_available():
        backends.append("openai")
    return backends


async def chat(
    message: str,
    system_prompt: str = "",
    backend: str = "",
    model: str = "",
) -> str:
    """統一對話介面。backend 可指定 gemini/openai，空字串自動選擇。"""
    if backend == "openai" and openai_chat.is_available():
        return await openai_chat.chat(message, system_prompt, model)
    if backend == "gemini" and gemini_chat.is_available():
        return await gemini_chat.chat(message, system_prompt)

    # 自動 fallback: gemini → openai
    if gemini_chat.is_available():
        result = await gemini_chat.chat(message, system_prompt)
        if result:
            return result
    if openai_chat.is_available():
        result = await openai_chat.chat(message, system_prompt, model)
        if result:
            return result
    return ""
