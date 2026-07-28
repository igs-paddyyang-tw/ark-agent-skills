"""Layer 1 — BM25 持久化索引搜尋。

需要：bm25s + jieba（選配，沒裝則整層跳過）。
索引由 indexer.py rebuild_index() 建置到 .index/bm25s/。
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("wiki.search.layer1")

BASE_DIR = Path(__file__).resolve().parents[3]
INDEX_DIR = BASE_DIR / "knowledge" / ".index"
BM25_DIR = INDEX_DIR / "bm25s"


def is_available() -> bool:
    """檢查 BM25 索引是否可用。"""
    try:
        import bm25s
        return (BM25_DIR / "params.index.json").exists()
    except ImportError:
        return False


def search_bm25(q: str, metadata: list[dict], top_k: int = 10) -> list[dict]:
    """BM25 搜尋。

    Args:
        q: 查詢字串
        metadata: 頁面 metadata 列表（用於對應 index → path/title）
        top_k: 回傳筆數

    Returns:
        list of {"path": str, "title": str, "score": float, "match_type": str}
        如果 bm25s 未安裝或索引不存在，回傳空列表。
    """
    try:
        import bm25s
    except ImportError:
        log.debug("bm25s not installed, skipping Layer 1")
        return []

    if not BM25_DIR.exists():
        log.debug("BM25 index not found at %s", BM25_DIR)
        return []

    # 分詞 query
    from src.wiki.indexer import tokenize_text
    query_tokens = tokenize_text(q)

    if not query_tokens:
        return []

    try:
        retriever = bm25s.BM25.load(str(BM25_DIR))
        results, scores = retriever.retrieve([query_tokens], k=min(top_k, len(metadata)))
    except Exception as e:
        log.error("BM25 search failed: %s", e)
        return []

    # 對應回 metadata
    hits = []
    for i in range(len(results[0])):
        idx = int(results[0][i])
        score = float(scores[0][i])

        if score <= 0:
            continue

        if idx < len(metadata):
            entry = metadata[idx]
            hits.append({
                "path": entry["path"],
                "title": entry["title"],
                "score": score,
                "match_type": "bm25",
            })

    return hits
