"""Layer 3：Rerank（已移除 Gemini 依賴，直接 passthrough）。"""
from __future__ import annotations


def is_available() -> bool:
    return False


async def rerank(query: str, results: list[dict], top_k: int = 5) -> list[dict]:
    """Passthrough — LLM rerank 已移除，直接回傳原順序。"""
    return results[:top_k]
