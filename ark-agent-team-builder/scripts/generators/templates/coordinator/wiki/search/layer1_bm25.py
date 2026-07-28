"""Layer 1：BM25 持久化索引（中文 bigram tokenizer）。"""
from __future__ import annotations

import json
import logging
import math
import pickle
from collections import Counter
from pathlib import Path

log = logging.getLogger("wiki.search.bm25")

INDEX_DIR = Path("data/.wiki_index")
BM25_FILE = INDEX_DIR / "bm25.pkl"

# BM25 參數
K1 = 1.2
B = 0.75

_index: dict | None = None


def is_available() -> bool:
    """檢查 BM25 索引是否可用。"""
    return BM25_FILE.exists() or _index is not None


def build_bm25_index(metadata: list[dict]) -> None:
    """從 metadata 建立 BM25 倒排索引。"""
    global _index

    docs: list[dict] = []  # [{tokens: Counter, length: int}]
    inverted: dict[str, list[tuple[int, int]]] = {}  # token → [(doc_idx, tf)]

    for idx, entry in enumerate(metadata):
        text = f"{entry['title']} {' '.join(entry.get('tags', []))} {entry.get('body_preview', '')}"
        tokens = _tokenize(text)
        tf = Counter(tokens)
        docs.append({"tf": tf, "length": len(tokens)})

        for token, count in tf.items():
            if token not in inverted:
                inverted[token] = []
            inverted[token].append((idx, count))

    avg_dl = sum(d["length"] for d in docs) / len(docs) if docs else 1
    n_docs = len(docs)

    _index = {
        "docs": docs,
        "inverted": inverted,
        "avg_dl": avg_dl,
        "n_docs": n_docs,
    }

    # 持久化
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(BM25_FILE, "wb") as f:
        pickle.dump(_index, f)
    log.info("BM25 index built: %d docs, %d terms", n_docs, len(inverted))


def _load_index() -> dict | None:
    """載入持久化索引。"""
    global _index
    if _index is not None:
        return _index
    if BM25_FILE.exists():
        with open(BM25_FILE, "rb") as f:
            _index = pickle.load(f)
        return _index
    return None


def search_bm25(query: str, metadata: list[dict], top_k: int = 10) -> list[dict]:
    """BM25 搜尋。

    Args:
        query: 搜尋字串
        metadata: 頁面 metadata 列表
        top_k: 回傳筆數

    Returns:
        metadata entries + score
    """
    index = _load_index()
    if not index:
        # 沒有索引，現場建立
        build_bm25_index(metadata)
        index = _index
        if not index:
            return []

    query_tokens = _tokenize(query)
    n_docs = index["n_docs"]
    avg_dl = index["avg_dl"]
    inverted = index["inverted"]
    docs = index["docs"]

    scores: list[float] = [0.0] * n_docs

    for token in query_tokens:
        if token not in inverted:
            continue
        df = len(inverted[token])
        idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)

        for doc_idx, tf in inverted[token]:
            dl = docs[doc_idx]["length"]
            numerator = tf * (K1 + 1)
            denominator = tf + K1 * (1 - B + B * dl / avg_dl)
            scores[doc_idx] += idf * numerator / denominator

    # 排序取 top_k
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    results: list[dict] = []
    for idx, score in ranked[:top_k]:
        if score <= 0:
            break
        if idx < len(metadata):
            results.append({**metadata[idx], "score": round(score, 4), "match_type": "bm25"})

    return results


def _tokenize(text: str) -> list[str]:
    """分詞：空格分割 + 中文 bigram + unigram。"""
    tokens: list[str] = []
    for part in text.lower().split():
        # 英文 / 數字保留原樣
        if part.isascii():
            tokens.append(part)
            continue
        # 中文：unigram + bigram
        cjk = [c for c in part if "\u4e00" <= c <= "\u9fff"]
        non_cjk = "".join(c for c in part if not ("\u4e00" <= c <= "\u9fff"))
        if non_cjk.strip():
            tokens.append(non_cjk.strip())
        for c in cjk:
            tokens.append(c)
        for i in range(len(cjk) - 1):
            tokens.append(cjk[i] + cjk[i + 1])
    return tokens
