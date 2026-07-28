"""Layer 2 — 三路混合搜尋：語意向量 + 圖譜擴散 + RRF 融合。

選配層：
- 語意向量需要 numpy（數百頁暴力 cosine 即可）
- 圖譜擴散讀 frontmatter 的 related + [[wikilink]]
- RRF 融合多路結果
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger("wiki.search.layer2")

BASE_DIR = Path(__file__).resolve().parents[3]
WIKI_DIR = BASE_DIR / "knowledge" / "shared" / "wiki"
INDEX_DIR = BASE_DIR / "knowledge" / "shared" / ".index"


# ─── RRF 融合 ────────────────────────────────────────

def rrf_fuse(ranked_lists: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion — 合併多路搜尋結果。

    Args:
        ranked_lists: 多路排序結果，每路是 path 列表（按相關性排序）
        k: RRF 參數（預設 60）

    Returns:
        融合後的 path 列表（按 RRF score 排序）
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked):
            scores[doc] = scores.get(doc, 0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)


# ─── 圖譜擴散 ────────────────────────────────────────

def graph_expand(seed_paths: list[str], metadata: list[dict], depth: int = 1) -> list[str]:
    """從種子頁面沿 [[wikilink]] 和 related 欄位擴散。

    Args:
        seed_paths: 種子頁面的 path 列表
        metadata: 全部頁面 metadata
        depth: 擴散深度

    Returns:
        擴散到的新頁面 path 列表（不含種子本身）
    """
    # 建立 slug → path 映射
    slug_to_path = {e["slug"]: e["path"] for e in metadata}
    path_to_entry = {e["path"]: e for e in metadata}

    expanded = set(seed_paths)
    frontier = set(seed_paths)

    for _ in range(depth):
        next_frontier: set[str] = set()
        for path in frontier:
            entry = path_to_entry.get(path)
            if not entry:
                continue

            # related 欄位
            for rel in entry.get("related", []):
                rel_path = slug_to_path.get(rel, "")
                if rel_path and rel_path not in expanded:
                    next_frontier.add(rel_path)

            # [[wikilink]] 從正文擷取
            wiki_path = WIKI_DIR / path
            if wiki_path.exists():
                content = wiki_path.read_text(encoding="utf-8")
                links = re.findall(r"\[\[(.+?)\]\]", content)
                for link in links:
                    link_path = slug_to_path.get(link, "")
                    if link_path and link_path not in expanded:
                        next_frontier.add(link_path)

        expanded.update(next_frontier)
        frontier = next_frontier

    return list(expanded - set(seed_paths))


# ─── 語意向量搜尋（選配）────────────────────────────

def is_semantic_available() -> bool:
    """檢查語意搜尋是否可用（需要 numpy + embeddings 檔案）。"""
    try:
        import numpy as np
        embeddings_path = INDEX_DIR / "embeddings.npy"
        return embeddings_path.exists()
    except ImportError:
        return False


def search_semantic(q: str, metadata: list[dict], top_k: int = 10) -> list[dict]:
    """語意向量搜尋（暴力 cosine，數百頁 OK）。

    Returns:
        list of {"path": str, "title": str, "score": float, "match_type": str}
        未安裝 numpy 或無 embeddings 時回空。
    """
    try:
        import numpy as np
    except ImportError:
        return []

    embeddings_path = INDEX_DIR / "embeddings.npy"
    if not embeddings_path.exists():
        return []

    try:
        corpus_vecs = np.load(str(embeddings_path))
        query_vec = _embed_query(q)
        if query_vec is None:
            return []

        # Cosine similarity
        norms = np.linalg.norm(corpus_vecs, axis=1) * np.linalg.norm(query_vec)
        norms[norms == 0] = 1e-10  # 避免除以零
        scores = corpus_vecs @ query_vec / norms
        top_idx = np.argsort(scores)[-top_k:][::-1]

        results = []
        for idx in top_idx:
            if idx < len(metadata) and scores[idx] > 0.1:
                entry = metadata[int(idx)]
                results.append({
                    "path": entry["path"],
                    "title": entry["title"],
                    "score": float(scores[idx]),
                    "match_type": "semantic",
                })
        return results

    except Exception as e:
        log.error("Semantic search failed: %s", e)
        return []


def _embed_query(q: str):
    """Query embedding（placeholder — 需要實際 embedding model）。

    TODO: 接入 BAAI/bge-m3 或 sentence-transformers
    目前回傳 None 表示不可用。
    """
    return None


# ─── 混合搜尋主函式 ──────────────────────────────────

def search_hybrid(
    q: str,
    bm25_results: list[dict],
    metadata: list[dict],
    top_k: int = 10,
) -> list[dict]:
    """三路混合搜尋 + RRF 融合。

    輸入 BM25 結果（由 Layer 1 產出），補充語意和圖譜，最終 RRF 融合。

    Returns:
        list of {"path": str, "title": str, "score": float, "match_type": str}
    """
    # 路 1: BM25（已由 Layer 1 提供）
    bm25_paths = [r["path"] for r in bm25_results]

    # 路 2: 語意向量
    semantic_results = search_semantic(q, metadata, top_k=top_k)
    semantic_paths = [r["path"] for r in semantic_results]

    # 路 3: 圖譜擴散（從 BM25 top 3 當種子）
    seed_paths = bm25_paths[:3]
    graph_paths = graph_expand(seed_paths, metadata, depth=1) if seed_paths else []

    # RRF 融合
    ranked_lists = [bm25_paths]
    if semantic_paths:
        ranked_lists.append(semantic_paths)
    if graph_paths:
        ranked_lists.append(graph_paths)

    if len(ranked_lists) <= 1:
        # 只有 BM25，不需要融合
        return bm25_results[:top_k]

    fused_paths = rrf_fuse(ranked_lists)

    # 建立 path → 最佳 score 映射
    all_results = {r["path"]: r for r in bm25_results + semantic_results}
    path_to_entry = {e["path"]: e for e in metadata}

    final = []
    for path in fused_paths[:top_k]:
        if path in all_results:
            final.append(all_results[path])
        elif path in path_to_entry:
            entry = path_to_entry[path]
            final.append({
                "path": entry["path"],
                "title": entry["title"],
                "score": 0.3,  # 圖譜擴散的預設分數
                "match_type": "graph",
            })

    return final
