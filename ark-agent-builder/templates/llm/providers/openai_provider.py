"""OpenAI Provider — openai SDK。"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.llm.provider import FunctionCall, LLMResponse

log = logging.getLogger(__name__)


@dataclass
class OpenAIProvider:
    """OpenAI API Provider with Function Calling support."""

    name: str = "openai"
    api_key: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai SDK not installed. Run: pip install openai")

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """呼叫 OpenAI API。"""
        temp = temperature if temperature is not None else self.temperature

        # Messages 轉換
        oai_messages = self._convert_messages(messages, system)

        # Tools 轉換
        oai_tools = None
        if tools:
            oai_tools = [
                {"type": "function", "function": t} for t in tools
            ]

        try:
            kwargs = {
                "model": self.model,
                "messages": oai_messages,
                "temperature": temp,
            }
            if oai_tools:
                kwargs["tools"] = oai_tools
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            log.error("OpenAI API error: %s", e)
            return LLMResponse(text=f"⚠️ OpenAI API 錯誤: {e}")

        return self._parse_response(response)

    def _convert_messages(self, messages: list[dict], system: str) -> list[dict]:
        """統一格式 → OpenAI 格式。"""
        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"

            # 處理 function_call / function_response（從 Gemini 格式轉）
            parts = msg.get("parts")
            if parts:
                for part in parts:
                    if isinstance(part, dict):
                        if "function_call" in part:
                            fc = part["function_call"]
                            oai_messages.append({
                                "role": "assistant",
                                "tool_calls": [{
                                    "id": fc.get("id", f"call_{fc['name']}"),
                                    "type": "function",
                                    "function": {
                                        "name": fc["name"],
                                        "arguments": json.dumps(fc.get("args", {})),
                                    },
                                }],
                            })
                        elif "function_response" in part:
                            fr = part["function_response"]
                            oai_messages.append({
                                "role": "tool",
                                "tool_call_id": f"call_{fr['name']}",
                                "content": json.dumps(fr["response"]) if isinstance(fr["response"], dict) else str(fr["response"]),
                            })
                        elif "text" in part:
                            oai_messages.append({"role": role, "content": part["text"]})
            else:
                content = msg.get("content", "")
                if content:
                    oai_messages.append({"role": role, "content": content})

        return oai_messages

    def _parse_response(self, response) -> LLMResponse:
        """解析 OpenAI response → 統一 LLMResponse。"""
        choice = response.choices[0]
        msg = choice.message

        # Usage
        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }

        # Tool calls
        if msg.tool_calls:
            function_calls = []
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                function_calls.append(FunctionCall(
                    name=tc.function.name,
                    args=args,
                    id=tc.id,
                ))
            return LLMResponse(function_calls=function_calls, usage=usage)

        return LLMResponse(text=msg.content, usage=usage)
