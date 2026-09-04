"""wiki_query.py — Wiki 四層搜尋（v3 executor）

    python wiki_query.py --wiki_dir knowledge/hoyeah/wiki --query "留存口徑"
    python wiki_query.py --knowledge_root knowledge --domains hoyeah,shared --query "DAU 定義"
    python wiki_query.py --wiki_dir ... --query ... --top_k 3 --full --max_chars 6000
    python wiki_query.py --wiki_dir ... --query ... --trust deterministic --approved-only
    python wiki_query.py --wiki_dir ... --query ... --layers L0,L1,L3
    python wiki_query.py --wiki_dir ... --query ... --format text      # 給人看（v2 相容）

## 四層與降級（每一層可缺，兜底永不掛零）

| 層 | 資料來源            | 缺失時                                   |
|----|--------------------|------------------------------------------|
| L0 | .index/metadata    | 現場掃 frontmatter，`index_used:false`   |
| L1 | .index/bm25        | 記憶體重算 BM25                          |
| L2 | .index/embeddings  | 跳過，記 `layers_skipped.L2`             |
| L3 | .index/graph.json  | 現場解析 [[wikilink]]                    |
| 兜底 | wiki/ 全文子字串   | 永遠可用                                 |

## 兩個刻意的行為（D-4 / D-5）

- **多 domain 必須顯式 `--domains`**（D-4）—— 不預設把所有 domain 掃進來，
  避免 A 專案的口徑污染 B 專案的回答。
- **索引過期只警告，不自動重建**（D-5）—— 15 個 instance 併發時自動重建
  會撞 build lock 並拖慢查詢。要重建請顯式 `--rebuild-if-stale`。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import (  # noqa: E402
    ErrorCode,
    content_hash,
    emit_error,
    emit_json,
    extract_wikilinks,
    index_dir,
    iter_pages,
    load_manifest,
    page_id,
    parse_frontmatter,
    resolve_tokenizer,
    strip_frontmatter,
    tokenize,
)

RRF_K = 60
ALL_LAYERS = ("L0", "L1", "L2", "L3")


# ── 資料載入 ─────────────────────────────────────────────────

def _read_index(wiki_dir: Path) -> dict:
    """讀 .index/。任一檔缺就當該層沒有索引，不拋例外。"""
    idx = index_dir(wiki_dir)
    out: dict = {"manifest": load_manifest(wiki_dir)}
    for key, rel in (("metadata", "metadata.json"), ("graph", "graph.json"),
                     ("postings", "bm25/postings.json")):
        p = idx / rel
        try:
            out[key] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        except Exception:
            out[key] = None
    out["embeddings"] = (idx / "embeddings").is_dir()
    out["userdict"] = idx / "userdict.txt"
    return out


def _scan_pages(wiki_dir: Path) -> dict[str, dict]:
    """現場掃 wiki/（索引缺失時的來源）。"""
    pages: dict[str, dict] = {}
    idx = index_dir(wiki_dir)
    for f in iter_pages(wiki_dir):
        if idx in f.parents:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        aliases = fm.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        pid = page_id(wiki_dir, f)
        pages[pid] = {
            "slug": f.stem, "title": str(fm.get("title", f.stem)), "aliases": aliases,
            "tags": tags, "type": fm.get("type", ""), "status": fm.get("status", ""),
            "trust": fm.get("trust", ""), "approved": fm.get("approved", None),
            "path": str(f.relative_to(wiki_dir)), "_text": text,
            "_body": strip_frontmatter(text),
        }
    return pages


def _page_text(wiki_dir: Path, meta: dict) -> str:
    p = wiki_dir / meta["path"]
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ── 各層 ─────────────────────────────────────────────────────

def layer0(query: str, metadata: dict[str, dict]) -> list[tuple[str, float]]:
    """metadata 精確層：slug / title 相等 1.0、alias 相等 0.95、title 包含 0.8。"""
    q = query.strip().lower()
    hits: dict[str, float] = {}
    for pid, m in metadata.items():
        cands_exact = {str(m.get("slug", "")).lower(), str(m.get("title", "")).lower(), pid.lower()}
        aliases = [str(a).lower() for a in (m.get("aliases") or [])]
        if q in cands_exact:
            hits[pid] = max(hits.get(pid, 0), 1.0)
        elif q in aliases:
            hits[pid] = max(hits.get(pid, 0), 0.95)
        elif q and (q in str(m.get("title", "")).lower()
                    or any(q in a for a in aliases)):
            hits[pid] = max(hits.get(pid, 0), 0.8)
    return sorted(hits.items(), key=lambda kv: -kv[1])


def _bm25(query_tokens: list[str], df: dict, docs: dict, n_docs: int, avg_dl: float,
          k1: float = 1.5, b: float = 0.75) -> list[tuple[str, float]]:
    if not docs or avg_dl <= 0:
        return []
    scored: list[tuple[str, float]] = []
    for pid, d in docs.items():
        tf, dl, s = d["tf"], d["len"], 0.0
        for qt in query_tokens:
            f = tf.get(qt)
            if not f:
                continue
            n_q = df.get(qt, 0)
            idf = math.log((n_docs - n_q + 0.5) / (n_q + 0.5) + 1.0)
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avg_dl))
        if s > 0:
            scored.append((pid, s))
    return sorted(scored, key=lambda kv: -kv[1])


def layer1(query: str, postings: dict | None, pages: dict[str, dict] | None,
           tokenizer: str, userdict: Path | None) -> tuple[list[tuple[str, float]], bool]:
    """BM25 層。回傳 (結果, 是否用了持久索引)。"""
    qt = tokenize(query, tokenizer, userdict)
    if postings and postings.get("docs"):
        return _bm25(qt, postings["df"], postings["docs"],
                     postings.get("n_docs") or len(postings["docs"]),
                     postings.get("avg_dl", 0.0)), True
    if not pages:
        return [], False
    docs, df = {}, {}
    for pid, m in pages.items():
        toks = tokenize(f"{m['title']} {' '.join(m['aliases'])}\n{m['_body']}", tokenizer, userdict)
        c = Counter(toks)
        docs[pid] = {"len": len(toks), "tf": dict(c)}
        for t in c:
            df[t] = df.get(t, 0) + 1
    n = len(docs) or 1
    avg = sum(d["len"] for d in docs.values()) / n
    return _bm25(qt, df, docs, len(docs), avg), False


def layer3(seed_pids: list[str], graph: dict | None,
           wiki_dir: Path, metadata: dict[str, dict]) -> list[tuple[str, float]]:
    """圖譜擴散：seed 的 1-hop 出/入鄰居。graph.json 缺就現場解析。"""
    if graph is None:
        out: dict[str, list[str]] = {}
        inn: dict[str, list[str]] = {p: [] for p in metadata}
        slug_to_pid = {m["slug"]: p for p, m in metadata.items()}
        for pid, m in metadata.items():
            links = extract_wikilinks(_page_text(wiki_dir, m))
            resolved = [l if l in metadata else slug_to_pid.get(l) for l in links]
            resolved = [r for r in resolved if r and r != pid]
            out[pid] = resolved
            for r in resolved:
                inn.setdefault(r, []).append(pid)
        graph = {"out": out, "in": inn}
    neigh: dict[str, float] = {}
    for rank, pid in enumerate(seed_pids):
        w = 1.0 / (rank + 1)
        for nb in (graph.get("out", {}).get(pid, []) + graph.get("in", {}).get(pid, [])):
            if nb not in seed_pids:
                neigh[nb] = max(neigh.get(nb, 0.0), w)
    return sorted(neigh.items(), key=lambda kv: -kv[1])


def fallback_layer(query: str, wiki_dir: Path, metadata: dict[str, dict],
                   texts: dict[str, str]) -> list[tuple[str, float]]:
    """兜底：全文子字串。永遠可用，分數固定 0.4。"""
    q = query.strip().lower()
    if not q:
        return []
    hits = []
    for pid, m in metadata.items():
        t = texts.get(pid) or _page_text(wiki_dir, m)
        texts[pid] = t
        if q in t.lower():
            hits.append((pid, 0.4))
    return hits


# ── 融合與輸出 ───────────────────────────────────────────────

def rrf(layer_results: dict[str, list[tuple[str, float]]]) -> dict[str, dict]:
    """Reciprocal Rank Fusion：score = Σ 1/(k+rank)。"""
    fused: dict[str, dict] = {}
    for layer, results in layer_results.items():
        for rank, (pid, _score) in enumerate(results):
            e = fused.setdefault(pid, {"score": 0.0, "layers": []})
            e["score"] += 1.0 / (RRF_K + rank + 1)
            if layer not in e["layers"]:
                e["layers"].append(layer)
    return fused


def best_paragraph(body: str, query: str, tokenizer: str, limit: int = 200) -> str:
    """取含最多查詢詞的段落（段落 = 連續非空行）。"""
    qt = set(tokenize(query, tokenizer)) or {query.lower()}
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paras:
        return ""
    def hit(p: str) -> int:
        low = p.lower()
        return sum(1 for t in qt if t in low)
    best = max(paras, key=lambda p: (hit(p), -paras.index(p)))
    one = " ".join(best.split())
    return one[:limit]


def run_query(wiki_dir: Path, query: str, args, domain: str = "") -> tuple[list[dict], dict]:
    idx = _read_index(wiki_dir)
    mf = idx["manifest"] or {}
    warnings: list[str] = []
    skipped: dict[str, str] = {}

    metadata = idx["metadata"]
    pages = None
    if not metadata:
        pages = _scan_pages(wiki_dir)
        metadata = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                    for k, v in pages.items()}
        if idx["manifest"] is None:
            warnings.append(ErrorCode.INDEX_MISSING)

    # tokenizer 一致性：manifest 記的 mode 與本機能力不符 → 警告 + 記憶體重算
    want = mf.get("tokenizer") or args.tokenizer
    have = resolve_tokenizer(args.tokenizer if args.tokenizer != "auto" else "auto")
    tokenizer = want if want in ("jieba", "bigram") else have
    postings = idx["postings"]
    if want and have != want:
        warnings.append(ErrorCode.TOKENIZER_MISMATCH)
        tokenizer = have
        postings = None                      # 索引用別的分詞建的，不能拿來查
        if pages is None:
            pages = _scan_pages(wiki_dir)

    # freshness（D-5：只警告）
    index_fresh = True
    if idx["manifest"]:
        index_fresh = mf.get("content_hash") == content_hash(wiki_dir)
        if not index_fresh:
            warnings.append(ErrorCode.INDEX_STALE)

    want_layers = [l.strip().upper() for l in args.layers.split(",")] if args.layers else list(ALL_LAYERS)
    lr: dict[str, list[tuple[str, float]]] = {}

    l0 = layer0(query, metadata) if "L0" in want_layers else []
    if l0:
        lr["L0"] = l0
    index_used = False
    if "L1" in want_layers:
        if pages is None and postings is None:
            pages = _scan_pages(wiki_dir)
        l1, index_used = layer1(query, postings, pages, tokenizer,
                                idx["userdict"] if idx["userdict"].exists() else None)
        if l1:
            lr["L1"] = l1
    if "L2" in want_layers:
        skipped["L2"] = "no_embeddings" if not idx["embeddings"] else "not_implemented"
    if "L3" in want_layers:
        seeds = [p for p, _ in (lr.get("L0", []) + lr.get("L1", []))][:3]
        l3 = layer3(seeds, idx["graph"], wiki_dir, metadata) if seeds else []
        if l3:
            lr["L3"] = l3

    texts: dict[str, str] = {pid: m["_text"] for pid, m in (pages or {}).items()}
    if not lr:
        fb = fallback_layer(query, wiki_dir, metadata, texts)
        if fb:
            lr["fallback"] = fb

    fused = rrf(lr)
    # L0 命中 1.0 固定置頂（避免 alias 精確命中被 RRF 稀釋）
    exact = {p for p, s in lr.get("L0", []) if s >= 1.0}
    ranked = sorted(fused.items(), key=lambda kv: (kv[0] not in exact, -kv[1]["score"]))

    results: list[dict] = []
    for pid, info in ranked:
        m = metadata.get(pid)
        if not m:
            continue
        if args.type and m.get("type") != args.type:
            continue
        if args.status and m.get("status") != args.status:
            continue
        if args.trust and m.get("trust") != args.trust:
            continue
        if args.approved_only and m.get("approved") is not True:
            continue
        if args.tags:
            want_tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            if not any(t in (m.get("tags") or []) for t in want_tags):
                continue
        text = texts.get(pid) or _page_text(wiki_dir, m)
        texts[pid] = text
        body = strip_frontmatter(text)
        row = {
            "page": f"{domain}/{pid}" if domain else pid,
            "slug": m.get("slug", ""), "title": m.get("title", ""),
            "score": round(info["score"], 6), "layers": info["layers"],
            "type": m.get("type", ""), "status": m.get("status", ""),
            "trust": m.get("trust", ""), "approved": m.get("approved", None),
            "tags": m.get("tags") or [],
            "summary": best_paragraph(body, query, tokenizer),
        }
        if args.full:
            row["content"] = body
        results.append(row)
        if len(results) >= args.top_k:
            break

    meta = {
        "total": len(fused), "top_k": args.top_k, "truncated": False, "out_file": None,
        "domains": [domain] if domain else [],
        "index_used": index_used, "index_version": mf.get("index_version"),
        "index_fresh": index_fresh,
        "layers_used": [l for l in lr], "layers_skipped": skipped,
        "tokenizer": tokenizer, "bm25_backend": mf.get("bm25_backend", "purepy"),
        "warnings": warnings,
    }
    return results, meta


def _merge_domains(per_domain: list[tuple[str, list[dict], dict]], top_k: int) -> tuple[list[dict], dict]:
    """跨 domain 再做一次 RRF。"""
    fused: dict[str, dict] = {}
    for _dom, rows, _meta in per_domain:
        for rank, r in enumerate(rows):
            e = fused.setdefault(r["page"], {"row": r, "score": 0.0})
            e["score"] += 1.0 / (RRF_K + rank + 1)
    merged = sorted(fused.values(), key=lambda e: -e["score"])
    rows = []
    for e in merged[:top_k]:
        r = dict(e["row"])
        r["score"] = round(e["score"], 6)
        rows.append(r)
    meta = {
        "total": len(fused), "top_k": top_k, "truncated": False, "out_file": None,
        "domains": [d for d, _, _ in per_domain],
        "index_used": all(m["index_used"] for _, _, m in per_domain),
        "index_version": next((m["index_version"] for _, _, m in per_domain), None),
        "index_fresh": all(m["index_fresh"] for _, _, m in per_domain),
        "layers_used": sorted({l for _, _, m in per_domain for l in m["layers_used"]}),
        "layers_skipped": {k: v for _, _, m in per_domain for k, v in m["layers_skipped"].items()},
        "tokenizer": next((m["tokenizer"] for _, _, m in per_domain), "bigram"),
        "bm25_backend": next((m["bm25_backend"] for _, _, m in per_domain), "purepy"),
        "warnings": sorted({w for _, _, m in per_domain for w in m["warnings"]}),
    }
    return rows, meta


def _apply_budget(rows: list[dict], max_chars: int, out: str, meta: dict) -> None:
    """--full 時保護 context window：超預算就落盤，不硬塞。"""
    if not rows or "content" not in rows[0]:
        return
    total = sum(len(r.get("content") or "") for r in rows)
    if out:
        Path(out).write_text(
            "\n\n---\n\n".join(f"# {r['title']}\n\n{r.get('content','')}" for r in rows),
            encoding="utf-8")
        meta["out_file"] = out
        for r in rows:
            r.pop("content", None)
        meta["truncated"] = False
        return
    if total > max_chars:
        budget = max_chars
        for r in rows:
            c = r.get("content") or ""
            if len(c) <= budget:
                budget -= len(c)
            else:
                r["content"] = c[:max(budget, 0)]
                budget = 0
        meta["truncated"] = True


def _print_text(query: str, rows: list[dict], meta: dict) -> None:
    """v2 的人類可讀輸出（相容用）。"""
    if not rows:
        print(f"（找不到包含「{query}」的頁面）")
        return
    print(f"🔍 查詢：{query}  找到 {len(rows)} 筆"
          f"{'' if meta['index_fresh'] else '  ⚠️ 索引過期'}\n")
    for i, r in enumerate(rows, 1):
        tags = f" [{', '.join(r['tags'])}]" if r["tags"] else ""
        flag = "" if r.get("approved") is not False else " ⚠未審核"
        print(f"[{i}] {r['title']}{tags} ({r['status']}){flag}")
        print(f"    {r['page']}  score={r['score']:.4f}  layers={'+'.join(r['layers'])}")
        print(f"    {r['summary']}\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki 四層搜尋（v3 executor）")
    p.add_argument("--wiki_dir", default="")
    p.add_argument("--knowledge_root", default="")
    p.add_argument("--domains", default="", help="逗號分隔；與 --knowledge_root 併用（D-4：必須顯式）")
    p.add_argument("--query", required=True)
    p.add_argument("--top_k", type=int, default=5)
    p.add_argument("--type", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--status", default="")
    p.add_argument("--trust", default="", choices=["", "deterministic", "llm-distilled"])
    p.add_argument("--approved-only", dest="approved_only", action="store_true")
    p.add_argument("--layers", default="", help="顯式指定層，如 L0,L1,L3")
    p.add_argument("--full", action="store_true")
    p.add_argument("--max_chars", type=int, default=8000)
    p.add_argument("--out", default="")
    p.add_argument("--tokenizer", default="auto", choices=["auto", "jieba", "bigram"])
    p.add_argument("--rebuild-if-stale", dest="rebuild_if_stale", action="store_true",
                   help="索引過期時先重建（D-5：預設只警告）")
    p.add_argument("--format", default="json", choices=["json", "text"])
    args = p.parse_args()

    t0 = time.time()
    if bool(args.wiki_dir) == bool(args.knowledge_root):
        emit_error(ErrorCode.BAD_ARGUMENTS,
                   "--wiki_dir 與 --knowledge_root/--domains 二擇一（不可同時給或都不給）")

    targets: list[tuple[str, Path]] = []
    if args.wiki_dir:
        targets = [("", Path(args.wiki_dir))]
    else:
        root = Path(args.knowledge_root)
        if not root.exists():
            emit_error(ErrorCode.WIKI_DIR_NOT_FOUND, f"knowledge_root 不存在：{root}")
        doms = [d.strip() for d in args.domains.split(",") if d.strip()]
        if not doms:
            emit_error(ErrorCode.BAD_ARGUMENTS,
                       "--knowledge_root 必須搭配 --domains（D-4：不預設掃全部 domain）")
        for d in doms:
            targets.append((d, root / d / "wiki"))

    for _d, wd in targets:
        if not wd.exists():
            emit_error(ErrorCode.WIKI_DIR_NOT_FOUND, f"目錄不存在：{wd}")

    if args.rebuild_if_stale:
        for _d, wd in targets:
            mf = load_manifest(wd)
            if mf is None or mf.get("content_hash") != content_hash(wd):
                subprocess.run([sys.executable, str(Path(__file__).parent / "wiki_index.py"),
                                "build", "--wiki_dir", str(wd)],
                               capture_output=True, check=False)

    if len(targets) == 1 and not targets[0][0]:
        rows, meta = run_query(targets[0][1], args.query, args)
    else:
        per = [(d, *run_query(wd, args.query, args, domain=d)) for d, wd in targets]
        rows, meta = _merge_domains([(d, r, m) for d, r, m in per], args.top_k)

    _apply_budget(rows, args.max_chars, args.out, meta)
    meta["elapsed_ms"] = int((time.time() - t0) * 1000)

    if args.format == "text":
        _print_text(args.query, rows, meta)
        return
    emit_json({"ok": True, "query": args.query, "results": rows, "meta": meta})


if __name__ == "__main__":
    main()
