"""wiki_query.py — 本地 Wiki 查詢腳本（增強版）

用途：在 wiki/ 目錄下搜尋，支援 BM25 評分 + frontmatter 過濾。
不依賴 team MCP，ark-agent 可直接呼叫。

使用方式：
    # 基本搜尋
    python scripts/wiki_query.py --wiki_dir knowledge/wiki --query "API 設計"

    # 過濾 type
    python scripts/wiki_query.py --wiki_dir knowledge/wiki --query "架構" --type concept

    # 過濾 tags
    python scripts/wiki_query.py --wiki_dir knowledge/wiki --query "部署" --tags ops,deploy

    # 過濾 status
    python scripts/wiki_query.py --wiki_dir knowledge/wiki --query "測試" --status mature

    # 輸出完整內容（給 LLM 用）
    python scripts/wiki_query.py --wiki_dir knowledge/wiki --query "認證" --full
"""
from __future__ import annotations

import argparse
import math
import re
from collections import Counter
from pathlib import Path


# ── Frontmatter 解析 ─────────────────────────────────────────

def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter。"""
    match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # 解析 list
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
            result[k] = v
    return result


def get_body(content: str) -> str:
    """取得 frontmatter 之後的本文。"""
    match = re.match(r"^---\n.+?\n---\n?", content, re.DOTALL)
    if match:
        return content[match.end():]
    return content


# ── BM25 評分 ────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """簡易分詞：空格 + 中文字元逐字。"""
    # 英文用空格分，中文逐字
    tokens = []
    for word in re.findall(r"[a-zA-Z0-9_\-]+|[\u4e00-\u9fff]", text.lower()):
        tokens.append(word)
    return tokens


def bm25_score(query_tokens: list[str], doc_tokens: list[str],
               avg_dl: float, n_docs: int, df: dict[str, int],
               k1: float = 1.5, b: float = 0.75) -> float:
    """計算單一文件的 BM25 分數。"""
    dl = len(doc_tokens)
    tf = Counter(doc_tokens)
    score = 0.0
    for qt in query_tokens:
        if qt not in tf:
            continue
        f = tf[qt]
        idf = math.log((n_docs - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5) + 1.0)
        numerator = f * (k1 + 1)
        denominator = f + k1 * (1 - b + b * dl / avg_dl)
        score += idf * numerator / denominator
    return score


# ── 搜尋主邏輯 ───────────────────────────────────────────────

def search(wiki_dir: Path, query: str, top_k: int = 5,
           filter_type: str = "", filter_tags: list[str] = None,
           filter_status: str = "", full: bool = False) -> list[dict]:
    """執行 BM25 搜尋 + frontmatter 過濾。"""
    md_files = list(wiki_dir.rglob("*.md"))
    if not md_files:
        return []

    # 載入所有文件
    docs = []
    for f in md_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(content)
        body = get_body(content)

        # Frontmatter 過濾
        if filter_type and fm.get("type", "") != filter_type:
            continue
        if filter_tags:
            doc_tags = fm.get("tags", [])
            if isinstance(doc_tags, str):
                doc_tags = [doc_tags]
            if not any(t in doc_tags for t in filter_tags):
                continue
        if filter_status and fm.get("status", "") != filter_status:
            continue

        docs.append({
            "path": f,
            "content": content,
            "body": body,
            "fm": fm,
            "tokens": tokenize(body),
        })

    if not docs:
        return []

    # 計算 BM25
    query_tokens = tokenize(query)
    n_docs = len(docs)
    avg_dl = sum(len(d["tokens"]) for d in docs) / n_docs

    # Document frequency
    df: dict[str, int] = {}
    for d in docs:
        seen = set(d["tokens"])
        for t in seen:
            df[t] = df.get(t, 0) + 1

    # 評分
    results = []
    for d in docs:
        s = bm25_score(query_tokens, d["tokens"], avg_dl, n_docs, df)
        if s > 0:
            results.append({**d, "score": s})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ── Context Window 摘要 ──────────────────────────────────────

def extract_context(content: str, query: str, window: int = 4) -> str:
    """取得包含 query 關鍵字的前後 window 行。"""
    lines = content.splitlines()
    hits = []
    query_lower = query.lower()
    for i, line in enumerate(lines):
        if query_lower in line.lower():
            start = max(0, i - window)
            end = min(len(lines), i + window + 1)
            snippet = "\n".join(lines[start:end])
            hits.append(snippet)
            if len(hits) >= 2:
                break
    return hits[0] if hits else content[:400]


# ── CLI ──────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Query — BM25 搜尋 + frontmatter 過濾")
    p.add_argument("--wiki_dir", required=True, help="wiki/ 目錄路徑")
    p.add_argument("--query", required=True, help="搜尋關鍵字")
    p.add_argument("--top_k", type=int, default=5, help="回傳筆數")
    p.add_argument("--type", default="", help="過濾 page type（concept/source/overview...）")
    p.add_argument("--tags", default="", help="過濾 tags（逗號分隔）")
    p.add_argument("--status", default="", help="過濾 status（seedling/developing/mature）")
    p.add_argument("--full", action="store_true", help="輸出完整內容（給 LLM context）")
    args = p.parse_args()

    wiki_dir = Path(args.wiki_dir)
    if not wiki_dir.exists():
        print(f"[ERROR] 目錄不存在：{wiki_dir}", file=sys.stderr)
        return

    filter_tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None

    results = search(
        wiki_dir, args.query,
        top_k=args.top_k,
        filter_type=args.type,
        filter_tags=filter_tags,
        filter_status=args.status,
        full=args.full,
    )

    if not results:
        print(f"（找不到包含「{args.query}」的頁面）")
        return

    print(f"🔍 查詢：{args.query}  找到 {len(results)} 筆\n")

    for i, r in enumerate(results):
        fm = r["fm"]
        title = fm.get("title", r["path"].stem)
        rel = r["path"].relative_to(wiki_dir) if wiki_dir in r["path"].parents else r["path"]
        tags = fm.get("tags", [])
        tags_str = f" [{', '.join(tags)}]" if tags else ""
        status = fm.get("status", "")
        status_str = f" ({status})" if status else ""

        print(f"[{i+1}] {title}{tags_str}{status_str}")
        print(f"    路徑：{rel}  score={r['score']:.2f}")

        if args.full:
            print(f"    ---")
            print(f"    {r['body'][:800]}")
        else:
            ctx = extract_context(r["content"], args.query)
            print(f"    {ctx[:200].replace(chr(10), ' ')}")
        print()


if __name__ == "__main__":
    main()
