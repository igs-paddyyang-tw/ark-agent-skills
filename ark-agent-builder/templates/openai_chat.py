"""OpenAI API 即時對話。"""
from __future__ import annotations

import os

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def is_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


async def chat(message: str, system_prompt: str = "", model: str = "") -> str:
    """單輪 OpenAI 對話。"""
    if not is_available():
        return ""
    try:
        client = _get_client()
        mdl = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        resp = client.chat.completions.create(model=mdl, messages=messages)
        return resp.choices[0].message.content or ""
    except Exception:
        return ""
