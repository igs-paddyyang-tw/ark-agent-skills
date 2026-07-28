"""Layer 2：TF-IDF 向量 + RRF 融合。"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

log = logging.getLogger("wiki.search.tfidf")

INDEX_DIR = Path("data/.wiki_index")
TFIDF_FILE = INDEX_DIR / "tfidf.pkl"

_vectorizer = None
_matrix = None


def is_available() -> bool:
    """檢查 sklearn 是否可用。"""
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def build_tfidf_index(metadata: list[dict]) -> bool:
    """建立 TF-IDF 索引。

    Returns:
        是否成功
    """
    global _vectorizer, _matrix
    if not is_available():
        return False

    from sklearn.feature_extraction.text import TfidfVectorizer

    corpus: list[str] = []
    for entry in metadata:
        text = f"{entry['title']} {' '.join(entry.get('tags', []))} {entry.get('body_preview', '')}"
        corpus.append(text)

    if not corpus:
        return False

    # 使用 char_wb analyzer 對中文友善
    _vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 3),
        max_features=10000,
        sublinear_tf=True,
    )
    _matrix = _vectorizer.fit_transform(corpus)

    # 持久化
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(TFIDF_FILE, "wb") as f:
        pickle.dump({"vectorizer": _vectorizer, "matrix": _matrix}, f)

    log.info("TF-IDF index built: %d docs, %d features", len(corpus), _matrix.shape[1])
    return True


def _load_index() -> bool:
    """載入持久化索引。"""
    global _vectorizer, _matrix
    if _vectorizer is not None and _matrix is not None:
        return True
    if TFIDF_FILE.exists():
        with open(TFIDF_FILE, "rb") as f:
            data = pickle.load(f)
            _vectorizer = data["vectorizer"]
            _matrix = data["matrix"]
        return True
    return False


def search_tfidf(query: str, metadata: list[dict], top_k: int = 10) -> list[dict]:
    """TF-IDF 餘弦相似搜尋。"""
    if not is_available():
        return []

    if not _load_index():
        # 現場建立
        if not build_tfidf_index(metadata):
            return []

    from sklearn.metrics.pairwise import cosine_similarity

    query_vec = _vectorizer.transform([query])
    scores = cosine_similarity(query_vec, _matrix).flatten()

    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    results: list[dict] = []
    for idx, score in ranked[:top_k]:
        if score <= 0.01:
            break
        if idx < len(metadata):
            results.append({**metadata[idx], "score": round(float(score), 4), "match_type": "tfidf"})

    return results


def search_hybrid(
    query: str,
    bm25_results: list[dict],
    metadata: list[dict],
    top_k: int = 10,
) -> list[dict]:
    """混合搜尋：BM25 + TF-IDF → RRF 融合。"""
    tfidf_results = search_tfidf(query, metadata, top_k=top_k * 2)

    if not tfidf_results:
        return bm25_results[:top_k]

    # RRF (Reciprocal Rank Fusion)
    k = 60  # RRF 常數
    rrf_scores: dict[str, float] = {}

    for rank, entry in enumerate(bm25_results):
        path = entry["path"]
        rrf_scores[path] = rrf_scores.get(path, 0) + 1 / (k + rank + 1)

    for rank, entry in enumerate(tfidf_results):
        path = entry["path"]
        rrf_scores[path] = rrf_scores.get(path, 0) + 1 / (k + rank + 1)

    # 合併結果
    all_entries: dict[str, dict] = {}
    for entry in bm25_results + tfidf_results:
        if entry["path"] not in all_entries:
            all_entries[entry["path"]] = entry

    # 按 RRF 分數排序
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    results: list[dict] = []
    for path, score in ranked[:top_k]:
        if path in all_entries:
            entry = all_entries[path].copy()
            entry["score"] = round(score, 4)
            entry["match_type"] = "hybrid"
            results.append(entry)

    return results
