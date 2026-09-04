"""wiki_index.py — Wiki 索引（v3：子命令化）

    build      建 .index/（metadata / graph / bm25 postings / userdict / manifest）
    md         重建 index.md（= v2 行為）
    freshness  索引是否仍對得上 wiki 現況（exit 0 fresh / 1 stale）
    （無子命令）= md，保留 v2 相容

## 兩個設計約束

1. **原子性**：先寫 `.index.tmp/`，全部完成才 `os.replace` 成 `.index/`。
   查詢端永遠看到完整索引，不會讀到半寫入的狀態。
2. **互斥**：build 取 `.index.lock`（fcntl），第二個 build 直接回 BUILD_LOCKED。
   15 個 instance 併發時不會互相寫壞。

## W0 範圍說明

`bm25_backend` 目前只實作 **purepy**（postings.json，零依賴可讀）。
`--backend bm25s` 回 BAD_ARGUMENTS —— bm25s 對照與導入排在 W4（T4.1），
在沒有召回對照數據前不預設引入第三方依賴。
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import (  # noqa: E402
    INDEX_VERSION,
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

parse_frontmatter = parse_frontmatter  # 明示：不再自帶一份（v2 有重複實作）


def build_index(wiki_dir: Path) -> str:
    """掃描 wiki/ 建立 index.md 內容。"""
    md_files = sorted(wiki_dir.rglob("*.md"))
    if not md_files:
        return "# 知識庫索引\n\n（尚無頁面）\n"

    # 按子目錄分組
    categories: dict[str, list[dict]] = {}
    total = 0
    status_count = {"seedling": 0, "developing": 0, "mature": 0}

    for f in md_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(content)
        title = fm.get("title", f.stem)
        status = fm.get("status", "seedling")
        page_type = fm.get("type", "")

        # 判斷 category
        rel = f.relative_to(wiki_dir)
        if len(rel.parts) > 1:
            category = rel.parts[0]
        else:
            category = "_root"

        if category not in categories:
            categories[category] = []

        categories[category].append({
            "name": f.stem,
            "title": title,
            "status": status,
            "type": page_type,
            "path": str(rel),
        })

        total += 1
        if status in status_count:
            status_count[status] += 1

    # 產出 Markdown
    today = date.today().isoformat()
    lines = [
        f"# 知識庫索引",
        f"",
        f"> 自動產生 by `wiki_index.py` — {today}",
        f"> 共 {total} 頁面 | 🌱 seedling: {status_count['seedling']} | 🌿 developing: {status_count['developing']} | 🌳 mature: {status_count['mature']}",
        f"",
    ]

    # 排序 category（_root 放最後）
    sorted_cats = sorted(categories.keys(), key=lambda x: (x == "_root", x))

    for cat in sorted_cats:
        pages = categories[cat]
        if cat == "_root":
            lines.append("## 根目錄")
        else:
            lines.append(f"## {cat}/")
        lines.append("")

        for page in sorted(pages, key=lambda x: x["title"]):
            status_icon = {"seedling": "🌱", "developing": "🌿", "mature": "🌳"}.get(page["status"], "")
            lines.append(f"- {status_icon} [[{page['name']}]] — {page['title']}")

        lines.append("")

    return "\n".join(lines)



# ── build：產出 .index/ ──────────────────────────────────────

def _collect(wiki_dir: Path, tokenizer: str) -> tuple[dict, dict, dict]:
    """掃一次 wiki/，同時產出 metadata / graph / bm25 三份資料。"""
    metadata: dict[str, dict] = {}
    out_links: dict[str, list[str]] = {}
    tokens_by_page: dict[str, list[str]] = {}
    userdict_terms: set[str] = set()

    for f in iter_pages(wiki_dir):
        if index_dir(wiki_dir) in f.parents:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        pid = page_id(wiki_dir, f)
        aliases = fm.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        title = str(fm.get("title", f.stem))
        metadata[pid] = {
            "slug": f.stem,
            "title": title,
            "aliases": aliases,
            "tags": tags,
            "type": fm.get("type", ""),
            "status": fm.get("status", ""),
            "trust": fm.get("trust", ""),
            "approved": fm.get("approved", None),
            "path": str(f.relative_to(wiki_dir)),
        }
        out_links[pid] = extract_wikilinks(text)
        body = strip_frontmatter(text)
        # title/aliases 一併進索引詞，否則「查標題」要靠本文剛好提到自己
        tokens_by_page[pid] = tokenize(f"{title} {' '.join(aliases)}\n{body}", tokenizer)
        userdict_terms.update([title, *aliases])

    # graph：slug 或 page_id 都可被 [[link]] 指到
    slug_to_pid = {v["slug"]: k for k, v in metadata.items()}
    graph_out: dict[str, list[str]] = {}
    graph_in: dict[str, list[str]] = {p: [] for p in metadata}
    for pid, links in out_links.items():
        resolved = []
        for l in links:
            target = l if l in metadata else slug_to_pid.get(l)
            if target and target != pid:
                resolved.append(target)
                graph_in[target].append(pid)
        graph_out[pid] = sorted(set(resolved))
    graph = {"out": graph_out, "in": {k: sorted(set(v)) for k, v in graph_in.items()}}

    # bm25 postings（purepy）
    df: dict[str, int] = {}
    docs: dict[str, dict] = {}
    for pid, toks in tokens_by_page.items():
        tf = Counter(toks)
        docs[pid] = {"len": len(toks), "tf": dict(tf)}
        for t in tf:
            df[t] = df.get(t, 0) + 1
    n_docs = len(docs) or 1
    postings = {
        "df": df,
        "docs": docs,
        "n_docs": len(docs),
        "avg_dl": (sum(d["len"] for d in docs.values()) / n_docs) if docs else 0.0,
    }
    return metadata, graph, {"postings": postings, "userdict": sorted(t for t in userdict_terms if t)}


def cmd_build(wiki_dir: Path, tokenizer_mode: str, backend: str, embed: bool) -> None:
    if backend == "bm25s":
        emit_error(ErrorCode.BAD_ARGUMENTS,
                   "--backend bm25s 尚未實作（排在 W4／T4.1，需先有召回對照數據）")
    tokenizer = resolve_tokenizer(tokenizer_mode)

    idx = index_dir(wiki_dir)
    # lock 放 tempdir 而非 wiki_dir —— 放在 wiki 目錄裡會在每個消費端 repo
    # 留下一個未追蹤檔（`.index/` 自帶 .gitignore 自我忽略，lock 檔不在其內），
    # 等於每個專案都要記得加一條 ignore 規則。用路徑 hash 命名避免不同 wiki 互鎖。
    lock_key = hashlib.sha256(str(wiki_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    lock_path = Path(tempfile.gettempdir()) / f"ark-wiki-index-{lock_key}.lock"
    lock_path.touch(exist_ok=True)
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_fd.close()
        emit_error(ErrorCode.BUILD_LOCKED,
                   "另一個 build 正在進行（.index.lock 被持有）", exit_code=2)

    try:
        metadata, graph, bm = _collect(wiki_dir, tokenizer)
        tmp = wiki_dir / ".index.tmp"
        if tmp.exists():
            shutil.rmtree(tmp)
        (tmp / "bm25").mkdir(parents=True)
        _w = lambda p, o: (tmp / p).write_text(
            json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
        _w("metadata.json", metadata)
        _w("graph.json", graph)
        _w("bm25/postings.json", bm["postings"])
        (tmp / "userdict.txt").write_text("\n".join(bm["userdict"]) + "\n", encoding="utf-8")
        manifest = {
            "index_version": INDEX_VERSION,
            "built_at": datetime.now().isoformat(timespec="seconds"),
            "page_count": len(metadata),
            "tokenizer": tokenizer,
            "bm25_backend": "purepy",
            "embed_model": None,
            "content_hash": content_hash(wiki_dir),
        }
        _w("manifest.json", manifest)
        (tmp / ".gitignore").write_text("*\n", encoding="utf-8")

        if idx.exists():
            shutil.rmtree(idx)
        os.replace(tmp, idx)   # 原子切換
        emit_json({"ok": True, "action": "build", "index_dir": str(idx), "manifest": manifest,
                   "meta": {"embed": embed and "not_implemented" or "skipped"}})
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def cmd_freshness(wiki_dir: Path) -> None:
    mf = load_manifest(wiki_dir)
    if mf is None:
        emit_json({"ok": True, "action": "freshness", "index_present": False,
                   "fresh": False, "reason": ErrorCode.INDEX_MISSING}, exit_code=1)
    now = content_hash(wiki_dir)
    fresh = mf.get("content_hash") == now
    emit_json({"ok": True, "action": "freshness", "index_present": True, "fresh": fresh,
               "built_at": mf.get("built_at"), "page_count": mf.get("page_count"),
               "reason": None if fresh else ErrorCode.INDEX_STALE},
              exit_code=0 if fresh else 1)


def cmd_md(wiki_dir: Path, output: str, dry_run: bool) -> None:
    content = build_index(wiki_dir)
    if dry_run:
        print(content)
        return
    out_path = Path(output) if output else wiki_dir.parent / "index.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"✅ index.md 已重建：{out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Index v3 — build / md / freshness")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="建 .index/（metadata / graph / bm25 / manifest）")
    b.add_argument("--wiki_dir", required=True)
    b.add_argument("--tokenizer", default="auto", choices=["auto", "jieba", "bigram"])
    b.add_argument("--backend", default="auto", choices=["auto", "purepy", "bm25s"])
    b.add_argument("--embed", action="store_true", help="產 embeddings/（W4，尚未實作）")

    m = sub.add_parser("md", help="重建 index.md（= v2 行為）")
    m.add_argument("--wiki_dir", required=True)
    m.add_argument("--output", default="")
    m.add_argument("--dry_run", action="store_true")

    f = sub.add_parser("freshness", help="索引是否對得上現況（exit 0 fresh / 1 stale）")
    f.add_argument("--wiki_dir", required=True)

    # 無子命令 = md（v2 相容）
    p.add_argument("--wiki_dir", dest="legacy_wiki_dir", help=argparse.SUPPRESS)
    p.add_argument("--output", dest="legacy_output", default="", help=argparse.SUPPRESS)
    p.add_argument("--dry_run", dest="legacy_dry_run", action="store_true", help=argparse.SUPPRESS)

    args = p.parse_args()
    cmd = args.cmd or "md"
    wiki_dir = Path(getattr(args, "wiki_dir", None) or args.legacy_wiki_dir or "")
    if not str(wiki_dir):
        p.error("--wiki_dir 為必填")
    if not wiki_dir.exists():
        emit_error(ErrorCode.WIKI_DIR_NOT_FOUND, f"目錄不存在：{wiki_dir}")

    if cmd == "build":
        cmd_build(wiki_dir, args.tokenizer, args.backend, args.embed)
    elif cmd == "freshness":
        cmd_freshness(wiki_dir)
    else:
        cmd_md(wiki_dir,
               getattr(args, "output", "") or args.legacy_output,
               getattr(args, "dry_run", False) or args.legacy_dry_run)


if __name__ == "__main__":
    main()
