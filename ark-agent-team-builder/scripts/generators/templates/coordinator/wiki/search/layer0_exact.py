"""Layer 0：精確匹配 + 子字串兜底（永不掛零）。"""
from __future__ import annotations

import re


def search_exact(query: str, metadata: list[dict]) -> list[dict]:
    """標題 / 檔名精確匹配。"""
    q_lower = query.lower().strip()
    results: list[dict] = []

    for entry in metadata:
        title = entry["title"].lower()
        path = entry["path"].lower()

        # 完全匹配
        if q_lower == title or q_lower == path.replace(".md", ""):
            results.append({**entry, "score": 1.0, "match_type": "exact_title"})
        # 標題包含
        elif q_lower in title:
            score = len(q_lower) / len(title) if title else 0
            results.append({**entry, "score": min(0.9, score + 0.5), "match_type": "title_contains"})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def search_substring(query: str, metadata: list[dict], max_results: int = 10) -> list[dict]:
    """子字串兜底：搜尋 body_preview 中包含 query 的。"""
    keywords = _tokenize(query)
    results: list[dict] = []

    for entry in metadata:
        text = (entry["title"] + " " + entry.get("body_preview", "")).lower()
        score = sum(1 for kw in keywords if kw in text) / len(keywords) if keywords else 0
        if score > 0:
            results.append({**entry, "score": score * 0.5, "match_type": "substring"})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def extract_summary(file_path, keywords: list[str], max_len: int = 200) -> str:
    """從檔案中提取含關鍵字的段落作為摘要。"""
    from pathlib import Path
    p = Path(file_path)
    if not p.exists():
        return ""
    content = p.read_text(encoding="utf-8")
    lines = content.split("\n")
    for line in lines:
        if any(kw in line.lower() for kw in keywords):
            return line[:max_len]
    return lines[0][:max_len] if lines else ""


def _tokenize(query: str) -> list[str]:
    """分詞：空格分割 + 中文 bigram。"""
    tokens: list[str] = []
    for part in query.lower().split():
        tokens.append(part)
        cjk = [c for c in part if "\u4e00" <= c <= "\u9fff"]
        if len(cjk) >= 2:
            for i in range(len(cjk) - 1):
                tokens.append(cjk[i] + cjk[i + 1])
    return list(set(tokens))
