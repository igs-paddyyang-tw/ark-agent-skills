"""Anthropic Provider — anthropic SDK。"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.llm.provider import FunctionCall, LLMResponse

log = logging.getLogger(__name__)


@dataclass
class AnthropicProvider:
    """Anthropic API Provider with Tool Use support."""

    name: str = "anthropic"
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7

    def __post_init__(self):
        try:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic SDK not installed. Run: pip install anthropic")

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """呼叫 Anthropic API。"""
        temp = temperature if temperature is not None else self.temperature

        # Messages 轉換
        ant_messages = self._convert_messages(messages)

        # Tools 轉換
        ant_tools = None
        if tools:
            ant_tools = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                }
                for t in tools
            ]

        try:
            kwargs = {
                "model": self.model,
                "messages": ant_messages,
                "max_tokens": 4096,
                "temperature": temp,
            }
            if system:
                kwargs["system"] = system
            if ant_tools:
                kwargs["tools"] = ant_tools
            response = await self._client.messages.create(**kwargs)
        except Exception as e:
            log.error("Anthropic API error: %s", e)
            return LLMResponse(text=f"⚠️ Anthropic API 錯誤: {e}")

        return self._parse_response(response)

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """統一格式 → Anthropic 格式。"""
        ant_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            if role in ("model", "assistant"):
                role = "assistant"
            elif role == "system":
                continue  # system 是獨立參數

            parts = msg.get("parts")
            if parts:
                content_blocks = []
                for part in parts:
                    if isinstance(part, dict):
                        if "function_call" in part:
                            fc = part["function_call"]
                            content_blocks.append({
                                "type": "tool_use",
                                "id": fc.get("id", f"toolu_{fc['name']}"),
                                "name": fc["name"],
                                "input": fc.get("args", {}),
                            })
                        elif "function_response" in part:
                            fr = part["function_response"]
                            content_blocks.append({
                                "type": "tool_result",
                                "tool_use_id": f"toolu_{fr['name']}",
                                "content": json.dumps(fr["response"]) if isinstance(fr["response"], dict) else str(fr["response"]),
                            })
                        elif "text" in part:
                            content_blocks.append({"type": "text", "text": part["text"]})
                if content_blocks:
                    # tool_result 必須是 user role
                    has_tool_result = any(b.get("type") == "tool_result" for b in content_blocks)
                    msg_role = "user" if has_tool_result else role
                    ant_messages.append({"role": msg_role, "content": content_blocks})
            else:
                content = msg.get("content", "")
                if content:
                    ant_messages.append({"role": role, "content": content})

        return ant_messages

    def _parse_response(self, response) -> LLMResponse:
        """解析 Anthropic response → 統一 LLMResponse。"""
        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

        function_calls = []
        text_parts = []

        for block in response.content:
            if block.type == "tool_use":
                function_calls.append(FunctionCall(
                    name=block.name,
                    args=block.input or {},
                    id=block.id,
                ))
            elif block.type == "text":
                text_parts.append(block.text)

        if function_calls:
            return LLMResponse(function_calls=function_calls, usage=usage)
        return LLMResponse(text="\n".join(text_parts) or None, usage=usage)
