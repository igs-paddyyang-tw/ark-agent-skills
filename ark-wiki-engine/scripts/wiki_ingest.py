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
import sys
from datetime import date
from pathlib import Path


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
        print(f"  [index] 更新 {index_path}")


def update_log(wiki_dir: Path, page_name: str, source_path: Path) -> None:
    """append log.md。"""
    log_path = wiki_dir.parent / "log.md"
    if not log_path.exists():
        log_path = (wiki_dir / ".." / "log.md").resolve()
    today = date.today().isoformat()
    entry = f"- **{today}** | ingest | `{source_path}` → `wiki/{page_name}.md`\n"

    if log_path.exists():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        log_path.write_text(f"# Wiki 操作日誌\n\n{entry}", encoding="utf-8")
    print(f"  [log] 記錄 {log_path}")


# ── 核心邏輯 ─────────────────────────────────────────────────

def ingest_file(source_path: Path, wiki_dir: Path, category: str, page_name: str, dry_run: bool) -> bool:
    """Ingest 單一檔案。回傳是否成功。"""
    if not source_path.exists():
        print(f"  [SKIP] 不存在：{source_path}", file=sys.stderr)
        return False

    if source_path.suffix not in (".md", ".txt", ".rst", ".yaml", ".yml", ".json"):
        print(f"  [SKIP] 不支援的格式：{source_path.suffix}")
        return False

    content = source_path.read_text(encoding="utf-8", errors="replace")

    # Auto-detect
    if not page_name:
        page_name = source_path.stem.lower().replace("_", "-").replace(" ", "-")
    if not category:
        category = detect_category(content, source_path.name)

    # 輸出路徑
    if category:
        out_dir = wiki_dir / category
    else:
        out_dir = wiki_dir
    out_path = out_dir / f"{page_name}.md"

    # 已存在跳過
    if out_path.exists():
        print(f"  [SKIP] 已存在：{out_path}")
        return False

    # 產出
    wiki_content = build_wiki_page(source_path, page_name, category, content)

    if dry_run:
        print(f"  [DRY] {source_path} → {out_path} (category={category})")
        return True

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(wiki_content, encoding="utf-8")
    print(f"  [OK] {source_path} → {out_path}")

    title = extract_title_from_content(content, page_name)
    update_index(wiki_dir, category, page_name, title)
    update_log(wiki_dir, page_name, source_path)
    return True


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Ingest — raw/ → wiki/ 骨架產出")
    p.add_argument("--source", required=True, help="來源檔案或目錄")
    p.add_argument("--wiki_dir", required=True, help="目標 wiki/ 目錄")
    p.add_argument("--category", default="", help="子目錄分類（空=自動偵測）")
    p.add_argument("--page_name", default="", help="輸出頁面名稱（僅單檔模式）")
    p.add_argument("--batch", action="store_true", help="目錄 batch 模式")
    p.add_argument("--dry_run", action="store_true", help="預覽，不寫入")
    args = p.parse_args()

    source = Path(args.source)
    wiki_dir = Path(args.wiki_dir)

    if args.batch or source.is_dir():
        # Batch 模式：掃描目錄下所有檔案
        if not source.is_dir():
            print(f"[ERROR] --batch 需要目錄：{source}", file=sys.stderr)
            sys.exit(1)
        files = sorted(f for f in source.rglob("*") if f.is_file())
        print(f"📦 Batch ingest: {len(files)} files from {source}\n")
        success = 0
        for f in files:
            if ingest_file(f, wiki_dir, args.category, "", args.dry_run):
                success += 1
        print(f"\n✅ 完成：{success}/{len(files)} 頁面{'（預覽）' if args.dry_run else '已建立'}")
    else:
        # 單檔模式
        if not source.exists():
            print(f"[ERROR] 來源不存在：{source}", file=sys.stderr)
            sys.exit(1)
        ok = ingest_file(source, wiki_dir, args.category, args.page_name, args.dry_run)
        if ok and not args.dry_run:
            print(f"\n✅ ingest 完成。請用 LLM（ark-agent）填充頁面內容。")


if __name__ == "__main__":
    main()
