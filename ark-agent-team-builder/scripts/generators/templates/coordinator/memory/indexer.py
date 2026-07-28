"""Memory Indexer — FTS5 索引管理。"""
from __future__ import annotations

import logging
from pathlib import Path

from coordinator.db.models import get_async_db, fetch_all, insert, now_iso

log = logging.getLogger("memory.indexer")


async def index_entry(
    agent: str,
    source: str,
    date: str,
    title: str,
    body: str,
    tags: str = "",
) -> int:
    """寫入一筆 memory_entries（FTS5 觸發器自動同步索引）。

    Returns:
        新增的 row id
    """
    conn = await get_async_db()
    try:
        cursor = await conn.execute(
            """INSERT INTO memory_entries (agent, source, date, title, body, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent, source, date, title, body, tags, now_iso()),
        )
        await conn.commit()
        row_id = cursor.lastrowid or 0
        log.debug("Indexed memory entry: agent=%s date=%s id=%d", agent, date, row_id)
        return row_id
    finally:
        await conn.close()


async def rebuild_memory_index(agents_dir: Path | None = None) -> int:
    """重建 FTS5 索引：掃描 agents/*/memory/daily/*.md → 寫入 DB。

    Args:
        agents_dir: agents 根目錄

    Returns:
        索引筆數
    """
    if agents_dir is None:
        agents_dir = Path("agents")

    if not agents_dir.exists():
        return 0

    conn = await get_async_db()
    try:
        # 取得已索引的 (agent, date) 組合
        existing = await fetch_all(
            conn,
            "SELECT DISTINCT agent, date FROM memory_entries WHERE source='daily'",
        )
        existing_set = {(r["agent"], r["date"]) for r in existing}

        count = 0
        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir() or not agent_dir.name.endswith("-agent"):
                continue
            agent_name = agent_dir.name
            daily_dir = agent_dir / "memory" / "daily"
            if not daily_dir.exists():
                continue

            for md_file in sorted(daily_dir.glob("*.md")):
                date_str = md_file.stem  # YYYY-MM-DD
                if (agent_name, date_str) in existing_set:
                    continue

                content = md_file.read_text(encoding="utf-8")
                if not content.strip():
                    continue

                # 解析 sections
                sections = _parse_daily_sections(content)
                for section in sections:
                    await conn.execute(
                        """INSERT INTO memory_entries
                           (agent, source, date, title, body, tags, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (agent_name, "daily", date_str,
                         section["title"], section["body"],
                         section.get("tags", ""), now_iso()),
                    )
                    count += 1

        await conn.commit()
        log.info("Memory index rebuilt: %d new entries", count)
        return count
    finally:
        await conn.close()


def _parse_daily_sections(content: str) -> list[dict]:
    """將 daily log markdown 拆分為多筆 section。

    格式：
    ## HH:MM [agent] task:xxx
    - 做了：...
    - tags: a, b
    """
    sections: list[dict] = []
    current_title = ""
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            # 儲存前一段
            if current_title and current_lines:
                body = "\n".join(current_lines).strip()
                tags = _extract_tags(body)
                sections.append({
                    "title": current_title,
                    "body": body,
                    "tags": tags,
                })
            current_title = line[3:].strip()
            current_lines = []
        elif line.startswith("# "):
            # 頂層標題（日期標題），跳過
            continue
        else:
            current_lines.append(line)

    # 最後一段
    if current_title and current_lines:
        body = "\n".join(current_lines).strip()
        tags = _extract_tags(body)
        sections.append({
            "title": current_title,
            "body": body,
            "tags": tags,
        })

    # 如果沒有 ## 標題，整篇當一筆
    if not sections and content.strip():
        sections.append({
            "title": "(no title)",
            "body": content.strip()[:2000],
            "tags": "",
        })

    return sections


def _extract_tags(body: str) -> str:
    """從 body 中提取 tags 行。"""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- tags:") or stripped.startswith("tags:"):
            return stripped.split(":", 1)[1].strip()
    return ""
