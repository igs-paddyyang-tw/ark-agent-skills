"""Gemini API 即時對話（1-5 秒，選配）。"""
import os

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def is_available() -> bool:
    """檢查 Gemini API Key 是否有設定。"""
    return bool(os.getenv("GEMINI_API_KEY"))


async def chat(message: str, system_prompt: str = "") -> str:
    """單輪 Gemini API 對話。無 Key 時回傳空字串。"""
    if not is_available():
        return ""
    try:
        import asyncio
        return await asyncio.to_thread(_sync_chat, message, system_prompt)
    except Exception:
        return ""


def _sync_chat(message: str, system_prompt: str) -> str:
    """同步 Gemini API 呼叫（由 to_thread 包裝）。"""
    client = _get_client()
    config = {"system_instruction": system_prompt} if system_prompt else None
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=message,
        config=config,
    )
    return response.text or ""
