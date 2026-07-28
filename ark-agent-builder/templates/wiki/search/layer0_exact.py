"""Layer 0 — 保底層：metadata 精確查找 + 子字串掃描。

設計原則：永不掛零。任何查詢至少有 fallback 結果。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger("wiki.search.layer0")

BASE_DIR = Path(__file__).resolve().parents[3]
WIKI_DIR = BASE_DIR / "knowledge" / "shared" / "wiki"


def search_exact(q: str, metadata: list[dict]) -> list[dict]:
    """精確匹配：slug / title / aliases 命中 → 直接回該頁面。

    Returns:
        list of {"path": str, "title": str, "score": float, "match_type": str}
    """
    q_lower = q.strip().lower()
    results = []

    for entry in metadata:
        # slug 完全匹配
        if q_lower == entry["slug"].lower():
            results.append({
                "path": entry["path"],
                "title": entry["title"],
                "score": 1.0,
                "match_type": "slug_exact",
            })
            continue

        # title 完全匹配
        if q_lower == entry["title"].lower():
            results.append({
                "path": entry["path"],
                "title": entry["title"],
                "score": 1.0,
                "match_type": "title_exact",
            })
            continue

        # aliases 匹配
        for alias in entry.get("aliases", []):
            if q_lower == alias.lower():
                results.append({
                    "path": entry["path"],
                    "title": entry["title"],
                    "score": 0.95,
                    "match_type": "alias_exact",
                })
                break

        # title 包含 query（部分匹配）
        if not results or results[-1]["path"] != entry["path"]:
            if q_lower in entry["title"].lower():
                results.append({
                    "path": entry["path"],
                    "title": entry["title"],
                    "score": 0.8,
                    "match_type": "title_contains",
                })

    return results


def search_substring(q: str, metadata: list[dict], max_results: int = 10) -> list[dict]:
    """子字串掃描兜底 — 逐檔搜尋正文（跳過 frontmatter）。

    數百頁規模 <100ms，不需要外部工具。

    Returns:
        list of {"path": str, "title": str, "score": float, "match_type": str}
    """
    q_lower = q.strip().lower()
    if not q_lower:
        return []

    results = []

    for entry in metadata:
        wiki_path = WIKI_DIR / entry["path"]
        if not wiki_path.exists():
            continue

        content = wiki_path.read_text(encoding="utf-8")
        body = _strip_frontmatter(content).lower()

        if q_lower in body:
            # 計算出現次數作為分數
            count = body.count(q_lower)
            score = min(0.6, 0.3 + count * 0.1)  # 0.3 ~ 0.6
            results.append({
                "path": entry["path"],
                "title": entry["title"],
                "score": score,
                "match_type": "substring",
            })

        if len(results) >= max_results:
            break

    # 按 score 排序
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def extract_summary(file_path: Path, keywords: list[str], max_len: int = 300) -> str:
    """從正文擷取最相關段落作為摘要。

    規則：
    - 跳過 frontmatter
    - 以段落（paragraph = 連續非空行）為單位
    - 選擇包含最多關鍵字的段落
    """
    if not file_path.exists():
        return ""

    content = file_path.read_text(encoding="utf-8")
    body = _strip_frontmatter(content)

    # 切段落（以空行分隔）
    paragraphs = re.split(r"\n\s*\n", body)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return body[:max_len]

    if not keywords:
        return paragraphs[0][:max_len]

    # 計算每個段落的關鍵字命中數
    best_para = paragraphs[0]
    best_score = 0

    for para in paragraphs:
        para_lower = para.lower()
        score = sum(1 for kw in keywords if kw in para_lower)
        if score > best_score:
            best_score = score
            best_para = para

    return best_para[:max_len]


def _strip_frontmatter(content: str) -> str:
    """移除 frontmatter，回傳純正文。"""
    if content.startswith("\ufeff"):
        content = content[1:]
    if not content.startswith("---"):
        return content
    end = content.find("---", 3)
    if end == -1:
        return content
    return content[end + 3:].strip()
