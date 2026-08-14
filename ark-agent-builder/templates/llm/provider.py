"""LLM Provider 抽象層：統一介面，支援 Gemini / OpenAI / Anthropic。"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass
class FunctionCall:
    """統一的 function call 結構。"""
    name: str
    args: dict
    id: str = ""  # OpenAI 需要 tool_call_id
    thought_signature: str | None = None  # Gemini 3.x thinking 模型必要


@dataclass
class LLMResponse:
    """統一的 LLM 回應結構。"""
    text: str | None = None
    function_calls: list[FunctionCall] = field(default_factory=list)
    usage: dict | None = None


class LLMProvider(Protocol):
    """LLM 提供者介面。所有 Provider 實作此協議。"""

    name: str

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """呼叫 LLM API。

        Args:
            messages: 對話歷史（統一格式）
            system: system prompt
            tools: function declarations（統一格式）
            temperature: 創意度

        Returns:
            LLMResponse（text 或 function_calls 二擇一）
        """
        ...


# ─── Provider 工廠 ───

_default_provider: LLMProvider | None = None


def get_default_provider() -> LLMProvider:
    """根據環境變數建立 Provider 實例。Bot 生命週期內不變。"""
    global _default_provider
    if _default_provider is not None:
        return _default_provider

    name = os.getenv("LLM_PROVIDER", "gemini")
    model = os.getenv("LLM_MODEL", "gemini-3.5-flash")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))

    if name == "gemini":
        from src.llm.providers.gemini import GeminiProvider
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        _default_provider = GeminiProvider(api_key=api_key, model=model, temperature=temperature)

    elif name == "openai":
        from src.llm.providers.openai_provider import OpenAIProvider
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        _default_provider = OpenAIProvider(
            api_key=api_key,
            model=os.getenv("OPENAI_MODEL", model),
            temperature=temperature,
        )

    elif name == "anthropic":
        from src.llm.providers.anthropic import AnthropicProvider
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        _default_provider = AnthropicProvider(
            api_key=api_key,
            model=os.getenv("ANTHROPIC_MODEL", model),
            temperature=temperature,
        )

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {name}")

    log.info("LLM Provider initialized: %s (model=%s)", name, model)
    return _default_provider


def reset_provider() -> None:
    """重置 provider（測試用）。"""
    global _default_provider
    _default_provider = None
