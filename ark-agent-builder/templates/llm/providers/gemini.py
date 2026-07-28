"""Gemini Provider — google-genai SDK（新版統一介面）。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.llm.provider import FunctionCall, LLMResponse

log = logging.getLogger(__name__)


@dataclass
class GeminiProvider:
    """Gemini API Provider with Function Calling support (google-genai SDK)."""

    name: str = "gemini"
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.7
    _client: object = field(default=None, init=False, repr=False)

    def __post_init__(self):
        from google import genai
        self._client = genai.Client(api_key=self.api_key)

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """呼叫 Gemini API。"""
        from google.genai import types

        temp = temperature if temperature is not None else self.temperature

        # Tools 轉換：function declarations
        genai_tools = None
        if tools:
            func_decls = []
            for t in tools:
                func_decls.append(types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters"),
                ))
            genai_tools = [types.Tool(function_declarations=func_decls)]

        # 組裝 config
        config = types.GenerateContentConfig(
            temperature=temp,
            tools=genai_tools,
        )
        if system:
            config.system_instruction = system

        # Messages 轉換
        contents = self._convert_messages(messages)

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            log.error("Gemini API error: %s", e)
            return LLMResponse(text=f"⚠️ Gemini API 錯誤: {e}")

        return self._parse_response(response)

    def _convert_messages(self, messages: list[dict]) -> list:
        """統一格式 → Gemini Content 格式。"""
        from google.genai import types

        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            gemini_role = "model" if role in ("assistant", "model") else "user"

            parts = msg.get("parts")
            if parts:
                # 已經是 parts 格式（function_call / function_response）
                genai_parts = []
                for p in parts:
                    if "function_call" in p:
                        fc = p["function_call"]
                        part_obj = types.Part.from_function_call(
                            name=fc["name"],
                            args=fc.get("args", {}),
                        )
                        # 還原 thought_signature（Gemini 3.x 必要）
                        if "thought_signature" in p and p["thought_signature"]:
                            part_obj.thought_signature = p["thought_signature"]
                        genai_parts.append(part_obj)
                    elif "function_response" in p:
                        fr = p["function_response"]
                        genai_parts.append(types.Part.from_function_response(
                            name=fr["name"],
                            response=fr.get("response", {}),
                        ))
                    elif "text" in p:
                        genai_parts.append(types.Part.from_text(text=p["text"]))
                contents.append(types.Content(role=gemini_role, parts=genai_parts))
            else:
                text = msg.get("content", "")
                if text:
                    contents.append(types.Content(
                        role=gemini_role,
                        parts=[types.Part.from_text(text=text)],
                    ))

        return contents

    def _parse_response(self, response) -> LLMResponse:
        """解析 Gemini response → 統一 LLMResponse。"""
        try:
            candidate = response.candidates[0]
            parts = candidate.content.parts
        except (IndexError, AttributeError):
            return LLMResponse(text="⚠️ Gemini 回傳無內容")

        function_calls = []
        text_parts = []

        for part in parts:
            if hasattr(part, "function_call") and part.function_call and part.function_call.name:
                fc = part.function_call
                args = dict(fc.args) if fc.args else {}
                # 保留 thought_signature（Gemini 3.x 必要）
                thought_sig = getattr(part, "thought_signature", None)
                function_calls.append(FunctionCall(
                    name=fc.name,
                    args=args,
                    thought_signature=thought_sig,
                ))
            elif hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        # 解析 usage
        usage = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "input_tokens": getattr(um, "prompt_token_count", 0),
                "output_tokens": getattr(um, "candidates_token_count", 0),
            }

        if function_calls:
            return LLMResponse(function_calls=function_calls, usage=usage)
        else:
            return LLMResponse(text="\n".join(text_parts) or None, usage=usage)
