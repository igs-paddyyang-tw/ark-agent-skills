"""Wiki Indexer — 建立 / 重建搜尋 metadata。"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger("wiki.indexer")

INDEX_DIR = Path("data/.wiki_index")
METADATA_FILE = INDEX_DIR / "metadata.json"

# 知識庫目錄
KNOWLEDGE_DIR = Path("knowledge")
AGENTS_DIR = Path("agents")


def build_metadata() -> list[dict]:
    """掃描所有 wiki 目錄，建立 metadata 列表。

    Returns:
        [{path, title, tags, scope, agent, body_preview}]
    """
    entries: list[dict] = []

    # 1. shared wiki
    shared_wiki = KNOWLEDGE_DIR / "shared" / "wiki"
    if shared_wiki.exists():
        entries.extend(_scan_dir(shared_wiki, scope="shared", agent="_shared"))

    # 2. agent private wiki
    if AGENTS_DIR.exists():
        for agent_dir in sorted(AGENTS_DIR.iterdir()):
            if agent_dir.is_dir() and agent_dir.name.endswith("-agent"):
                wiki_dir = agent_dir / "knowledge" / "wiki"
                if wiki_dir.exists():
                    entries.extend(_scan_dir(wiki_dir, scope="private", agent=agent_dir.name))

    # 3. project scope
    if KNOWLEDGE_DIR.exists():
        for d in sorted(KNOWLEDGE_DIR.iterdir()):
            if d.is_dir() and d.name not in ("shared", ".index") and not d.name.startswith("."):
                wiki_dir = d / "wiki"
                if wiki_dir.exists():
                    entries.extend(_scan_dir(wiki_dir, scope=d.name, agent="_project"))

    return entries


def rebuild_index() -> int:
    """重建索引並存檔。回傳頁面數。"""
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    entries = build_metadata()
    METADATA_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Wiki index rebuilt: %d pages", len(entries))
    return len(entries)


def load_metadata() -> list[dict]:
    """載入 metadata（不存在則現場建立）。"""
    if not METADATA_FILE.exists():
        rebuild_index()
    if not METADATA_FILE.exists():
        return []
    return json.loads(METADATA_FILE.read_text(encoding="utf-8"))


def _scan_dir(wiki_dir: Path, scope: str, agent: str) -> list[dict]:
    """掃描單一 wiki 目錄。"""
    entries: list[dict] = []
    for md in wiki_dir.rglob("*.md"):
        if md.name in (".gitkeep", "index.md", "log.md", "schema.md"):
            continue
        content = md.read_text(encoding="utf-8")
        title = _extract_title(content)
        tags = _extract_tags(content)
        # body preview（前 500 字，去 frontmatter）
        body = _strip_frontmatter(content)[:500]

        entries.append({
            "path": str(md.relative_to(wiki_dir)),
            "abs_path": str(md),
            "title": title,
            "tags": tags,
            "scope": scope,
            "agent": agent,
            "body_preview": body,
        })
    return entries


def _extract_title(content: str) -> str:
    """提取 frontmatter title 或第一個 # 標題。"""
    m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
    if m:
        return m.group(1)
    m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return m.group(1) if m else "Untitled"


def _extract_tags(content: str) -> list[str]:
    """提取 frontmatter tags。"""
    m = re.search(r"^tags:\s*\[(.+?)\]", content, re.MULTILINE)
    if m:
        return [t.strip().strip("'\"") for t in m.group(1).split(",")]
    m = re.search(r"^tags:\s*(.+)$", content, re.MULTILINE)
    if m:
        return [t.strip() for t in m.group(1).split(",")]
    return []


def _strip_frontmatter(content: str) -> str:
    """去除 frontmatter 後回傳內容。"""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            return content[end + 3:].strip()
    return content
