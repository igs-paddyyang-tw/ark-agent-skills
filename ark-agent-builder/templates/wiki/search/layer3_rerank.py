"""Layer 3 — LLM Rerank（選配）。

有 Gemini API 時啟用，讓 LLM 從候選中挑最相關的結果。
沒有 API Key 時直接回傳原始排序。
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("wiki.search.layer3")


def is_available() -> bool:
    """檢查 rerank 是否可用（需要 Gemini API Key）。"""
    key = os.getenv("GEMINI_API_KEY", "")
    return bool(key) and key != "your_gemini_api_key_here"


async def rerank(q: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """LLM rerank — 從候選中挑最相關的。

    Args:
        q: 查詢字串
        candidates: 候選結果列表，每個含 path, title, summary
        top_k: 回傳筆數

    Returns:
        重新排序後的候選列表（最多 top_k 個）
        LLM 不可用時直接回傳前 top_k 個。
    """
    if not is_available():
        return candidates[:top_k]

    if len(candidates) <= top_k:
        return candidates

    # 組裝 prompt
    prompt = (
        f"以下是知識庫搜尋「{q}」的候選結果。\n"
        f"請從中選出最相關的 {top_k} 個，回傳它們的編號（用逗號分隔，如：1,3,5）。\n"
        f"只回傳數字，不要解釋。\n\n"
    )
    for i, c in enumerate(candidates, 1):
        title = c.get("title", "")
        summary = c.get("summary", "")[:150]
        prompt += f"{i}. [{title}] {summary}\n"

    try:
        import httpx
        api_key = os.getenv("GEMINI_API_KEY", "")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                log.warning("Rerank API failed: %d", resp.status_code)
                return candidates[:top_k]
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]

        # 解析回傳的編號
        numbers = [int(x.strip()) for x in re.findall(r"\d+", text)]
        reranked = []
        seen = set()
        for num in numbers:
            idx = num - 1  # 1-based → 0-based
            if 0 <= idx < len(candidates) and idx not in seen:
                reranked.append(candidates[idx])
                seen.add(idx)
            if len(reranked) >= top_k:
                break

        # 如果 LLM 回傳不夠，補上原始排序
        if len(reranked) < top_k:
            for c in candidates:
                if c not in reranked:
                    reranked.append(c)
                if len(reranked) >= top_k:
                    break

        return reranked

    except Exception as e:
        log.error("Rerank failed: %s", e)
        return candidates[:top_k]
