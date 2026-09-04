"""wiki_ingest.py — 本地 Wiki Ingest 腳本（增強版）

用途：從 raw/ 讀取原始文件，產出 wiki/ 頁面骨架（含 frontmatter）。
支援單檔、batch（整個目錄）、auto-detect category。
不依賴 team MCP，ark-agent 可直接呼叫。

使用方式：
    # 單檔 ingest
    python scripts/wiki_ingest.py \\
        --source knowledge/raw/architecture.md \\
        --wiki_dir knowledge/wiki

    # 整個目錄 batch ingest
    python scripts/wiki_ingest.py \\
        --source knowledge/raw/ \\
        --wiki_dir knowledge/wiki \\
        --batch

    # 指定 category + page_name
    python scripts/wiki_ingest.py \\
        --source knowledge/raw/api-design.md \\
        --wiki_dir knowledge/wiki \\
        --category dev-guide \\
        --page_name api-design-patterns

    # 預覽模式
    python scripts/wiki_ingest.py \\
        --source knowledge/raw/notes.md \\
        --wiki_dir knowledge/wiki \\
        --dry_run
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import ErrorCode, emit_json, parse_frontmatter  # noqa: E402
import wiki_guard  # noqa: E402
import wiki_taxonomy  # noqa: E402

# ── stdout／stderr 分工 ────────────────────────────────────────
# **stdout 只放機器契約（--json 的 JSON）**，人看的進度一律 stderr。
# 實測踩過：update_index/update_log 的 `[index]`/`[log]` 進度行印在 stdout，
# 讓 `--json` 的輸出前面多兩行 → agent 端 json.loads 直接炸。
#
# ── v3 硬規則管線（順序寫死在 ingest_file，任何參數都不能調換）──────
#
#   guard scan ──違規→ quarantine + GUARD_BLOCKED（不落盤）
#      → 骨架產出（trust=deterministic / approved=true）
#      → taxonomy check（--schema 給時；未知 tag → TAG_NOT_IN_WHITELIST，不落盤）
#      → 落盤 wiki/{category}/{page}.md
#      → index.md + log.md（`date | op | page | trust | by | note`）
#      → wiki_index.py build（--no-index 可關，僅 batch 中間步驟用）
#
# v2 的 SKILL.md 宣告「guard-first ingest 不可跳過」，但 wiki_ingest.py 對
# wiki_guard / wiki_taxonomy 是**零呼叫**（F-6）—— 那條規則只存在於 SOP 文字，
# 靠 LLM 記得執行。deterministic 的守門必須寫在腳本裡。


# ── Category 自動偵測 ────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "architecture": ["架構", "architecture", "系統設計", "system design", "模組", "module"],
    "dev-guide": ["開發", "coding", "api", "實作", "implementation", "規範", "standard"],
    "operations": ["維運", "ops", "deploy", "部署", "監控", "monitor", "SOP"],
    "decisions": ["決策", "decision", "ADR", "選型", "trade-off"],
    "learnings": ["學習", "踩坑", "bug", "修復", "lesson", "pitfall"],
    "meetings": ["會議", "meeting", "摘要", "紀錄", "minutes"],
}


def detect_category(content: str, filename: str) -> str:
    """根據內容和檔名自動偵測 category。"""
    text = (content[:500] + filename).lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return ""


# ── Frontmatter 建立 ─────────────────────────────────────────

def extract_title_from_content(content: str, filename: str) -> str:
    """從內容第一個 # 標題或檔名取得 title。"""
    match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return filename.replace("-", " ").replace("_", " ").title()


def detect_type(content: str) -> str:
    """依內容偵測 page type。"""
    lower = content[:1000].lower()
    if any(w in lower for w in ["api", "endpoint", "request", "response"]):
        return "source"
    if any(w in lower for w in ["架構", "architecture", "設計", "design"]):
        return "concept"
    if any(w in lower for w in ["比較", "vs", "comparison", "trade-off"]):
        return "comparison"
    if any(w in lower for w in ["總覽", "overview", "簡介"]):
        return "overview"
    return "source"


def build_wiki_page(source_path: Path, page_name: str, category: str, content: str) -> str:
    """產出含 frontmatter 的 wiki 頁面骨架。"""
    today = date.today().isoformat()
    title = extract_title_from_content(content, page_name)
    page_type = detect_type(content)
    rel_source = str(source_path)

    # 從內容提取 tags（取前 5 個出現的 category keywords）
    tags = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in content.lower() and kw not in tags:
                tags.append(kw)
                if len(tags) >= 3:
                    break
        if len(tags) >= 3:
            break

    tags_str = ", ".join(tags) if tags else page_type

    return f"""---
title: "{title}"
type: {page_type}
tags: [{tags_str}]
sources: [{rel_source}]
related: [overview]
created: {today}
updated: {today}
status: seedling
trust: deterministic
approved: true
---

# {title}

> 萃取自 `{rel_source}`

<!-- LLM: 請依 source 內容填充以下章節 -->

## 概述

## 主要內容

## 相關頁面

"""


# ── Index / Log 更新 ─────────────────────────────────────────

def update_index(wiki_dir: Path, category: str, page_name: str, title: str) -> None:
    """將新頁面加入 index.md。"""
    # index.md 在 knowledge root（wiki_dir 的上層）
    index_path = wiki_dir.parent / "index.md"
    if not index_path.exists():
        # wiki_dir 本身也可能就是 knowledge root
        index_path = wiki_dir / ".." / "index.md"
        index_path = index_path.resolve()
    if not index_path.exists():
        return

    content = index_path.read_text(encoding="utf-8")
    link = f"- [[{page_name}]]"
    if page_name not in content:
        if category:
            section = f"### {category}"
            if section in content:
                content = content.replace(section, f"{section}\n{link} — {title}")
            else:
                content = content.rstrip() + f"\n\n{section}\n{link} — {title}\n"
        else:
            content = content.rstrip() + f"\n{link} — {title}\n"
        index_path.write_text(content, encoding="utf-8")
        print(f"  [index] 更新 {index_path}", file=sys.stderr)


def update_log(wiki_dir: Path, page_name: str, source_path: Path,
               trust: str = "deterministic", by: str = "unknown", note: str = "") -> None:
    """append log.md（append-only）。

    欄位固定為 `date | op | page | trust | by | note` —— `trust` 與 `by` 是 v3 新增：
    出了問題要能回答「這頁是誰、用什麼信任等級寫進來的」。
    """
    log_path = wiki_dir.parent / "log.md"
    if not log_path.exists():
        log_path = (wiki_dir / ".." / "log.md").resolve()
    today = date.today().isoformat()
    entry = (f"- **{today}** | ingest | `wiki/{page_name}.md` | {trust} | {by} | "
             f"{note or f'source={source_path}'}\n")

    if log_path.exists():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        log_path.write_text(f"# Wiki 操作日誌\n\n{entry}", encoding="utf-8")
    print(f"  [log] 記錄 {log_path}", file=sys.stderr)


# ── 核心邏輯 ─────────────────────────────────────────────────

def _quarantine_source(source_path: Path, findings: list[dict]) -> Path:
    """把違規來源移到 raw/_quarantine/（raw 目錄推定為 source 的所在目錄）。"""
    return wiki_guard.quarantine(source_path, findings, source_path.parent)


def ingest_file(source_path: Path, wiki_dir: Path, category: str, page_name: str,
                dry_run: bool, *, no_guard: bool = False, schema: Path | None = None,
                by: str = "unknown") -> dict:
    """Ingest 單一檔案。回傳結果 dict（步驟順序寫死，不可由參數調換）。"""
    if not source_path.exists():
        return {"file": str(source_path), "status": "skip", "reason": "not_found"}
    if source_path.suffix not in (".md", ".txt", ".rst", ".yaml", ".yml", ".json"):
        return {"file": str(source_path), "status": "skip",
                "reason": f"unsupported_suffix:{source_path.suffix}"}

    content = source_path.read_text(encoding="utf-8", errors="replace")

    # ── 步驟 1：guard（第一道，永遠先跑）
    findings = wiki_guard.scan_text(content)
    if findings and not no_guard:
        dest = None if dry_run else _quarantine_source(source_path, findings)
        return {"file": str(source_path), "status": "blocked",
                "code": ErrorCode.GUARD_BLOCKED, "findings": findings,
                "quarantined_to": str(dest) if dest else None}
    guard_note = "no-guard" if (findings and no_guard) else ""

    if not page_name:
        page_name = source_path.stem.lower().replace("_", "-").replace(" ", "-")
    if not category:
        category = detect_category(content, source_path.name)
    out_dir = wiki_dir / category if category else wiki_dir
    out_path = out_dir / f"{page_name}.md"
    if out_path.exists():
        return {"file": str(source_path), "status": "skip", "reason": "already_exists",
                "page": str(out_path)}

    # ── 步驟 2：骨架
    wiki_content = build_wiki_page(source_path, page_name, category, content)

    # ── 步驟 3：taxonomy（在落盤之前 —— 擋下來的頁面不能留在 wiki/）
    if schema is not None:
        whitelist = wiki_taxonomy.load_whitelist(schema)
        tags = parse_frontmatter(wiki_content).get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        unknown = sorted(t for t in tags if t not in whitelist)
        if unknown:
            return {"file": str(source_path), "status": "blocked",
                    "code": ErrorCode.TAG_NOT_IN_WHITELIST, "unknown_tags": unknown,
                    "hint": "用 wiki_taxonomy.py propose 提案，不要自創 tag"}

    if dry_run:
        return {"file": str(source_path), "status": "dry_run", "page": str(out_path),
                "category": category}

    # ── 步驟 4：落盤
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(wiki_content, encoding="utf-8")

    # ── 步驟 5：index.md + log.md
    title = extract_title_from_content(content, page_name)
    update_index(wiki_dir, category, page_name, title)
    update_log(wiki_dir, page_name, source_path, trust="deterministic", by=by,
               note=guard_note)
    if guard_note:
        print(f"  ⚠️  --no-guard：{source_path} 有 {len(findings)} 項 guard 違規仍被寫入"
              f"（已在 log.md 記 no-guard 以供稽核）", file=sys.stderr)
    return {"file": str(source_path), "status": "ok", "page": str(out_path),
            "category": category, "trust": "deterministic", "by": by,
            "guard_bypassed": bool(guard_note)}


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Ingest v3 — guard-first 骨架產出")
    p.add_argument("--source", required=True, help="來源檔案或目錄")
    p.add_argument("--wiki_dir", required=True, help="目標 wiki/ 目錄")
    p.add_argument("--category", default="", help="子目錄分類（空=自動偵測）")
    p.add_argument("--page_name", default="", help="輸出頁面名稱（僅單檔模式）")
    p.add_argument("--batch", action="store_true", help="目錄 batch 模式")
    p.add_argument("--dry_run", action="store_true", help="預覽，不寫入")
    p.add_argument("--schema", default="", help="schema.md 路徑（給了才做 tags 白名單守門）")
    p.add_argument("--by", default="unknown", help="寫入 log.md 的執行者")
    p.add_argument("--no-guard", dest="no_guard", action="store_true",
                   help="繞過 guard（會在 stderr 警告並在 log.md 記 no-guard）")
    p.add_argument("--no-index", dest="no_index", action="store_true",
                   help="不在結束時重建 .index/（batch 中間步驟用）")
    p.add_argument("--json", action="store_true", help="機器可讀輸出")
    args = p.parse_args()

    source = Path(args.source)
    wiki_dir = Path(args.wiki_dir)
    if not wiki_dir.exists():
        emit_json({"ok": False,
                   "error": {"code": ErrorCode.WIKI_DIR_NOT_FOUND,
                             "msg": f"目錄不存在：{wiki_dir}"}}, 2)
    schema = Path(args.schema) if args.schema else None
    if schema is not None and not schema.exists():
        emit_json({"ok": False,
                   "error": {"code": ErrorCode.SCHEMA_NOT_FOUND,
                             "msg": f"schema 不存在：{schema}"}}, 2)

    if args.batch or source.is_dir():
        if not source.is_dir():
            emit_json({"ok": False, "error": {"code": ErrorCode.BAD_ARGUMENTS,
                                              "msg": f"--batch 需要目錄：{source}"}}, 2)
        files = sorted(f for f in source.rglob("*") if f.is_file())
    else:
        files = [source]

    results = [ingest_file(f, wiki_dir, args.category,
                           args.page_name if len(files) == 1 else "",
                           args.dry_run, no_guard=args.no_guard, schema=schema,
                           by=args.by)
               for f in files]

    blocked = [r for r in results if r["status"] == "blocked"]
    created = [r for r in results if r["status"] == "ok"]

    # ── 步驟 6：索引（有實際落盤才重建）
    index_built = False
    if created and not args.no_index and not args.dry_run:
        proc = subprocess.run([sys.executable, str(Path(__file__).parent / "wiki_index.py"),
                               "build", "--wiki_dir", str(wiki_dir)],
                              capture_output=True, text=True)
        index_built = proc.returncode == 0

    payload = {"ok": not blocked, "action": "ingest", "created": len(created),
               "blocked": len(blocked), "index_built": index_built, "results": results}
    if args.json:
        emit_json(payload, 1 if blocked else 0)

    for r in results:
        mark = {"ok": "[OK]", "blocked": "🚧", "skip": "[SKIP]", "dry_run": "[DRY]"}[r["status"]]
        extra = r.get("code") or r.get("reason") or r.get("page", "")
        print(f"  {mark} {r['file']} {extra}")
    print(f"\n{'✅' if not blocked else '⚠️'} 建立 {len(created)}｜擋下 {len(blocked)}"
          f"｜索引{'已重建' if index_built else '未重建'}")
    if blocked:
        sys.exit(1)


if __name__ == "__main__":
    main()
