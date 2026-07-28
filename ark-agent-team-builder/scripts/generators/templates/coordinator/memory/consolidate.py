"""Memory Consolidate — 蒸餾 daily log → memory.md 持久事實。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from coordinator.db.models import get_async_db, fetch_all

log = logging.getLogger("memory.consolidate")

MAX_MEMORY_CHARS = 2000


async def consolidate(
    agent_name: str,
    agents_dir: Path | None = None,
    days: int = 14,
) -> str:
    """蒸餾 daily → memory.md（附加最近摘要）。

    Args:
        agent_name: Agent 名稱
        agents_dir: agents 根目錄
        days: 蒸餾最近幾天

    Returns:
        蒸餾結果（新 memory.md 內容）
    """
    if agents_dir is None:
        agents_dir = Path("agents")

    memory_dir = agents_dir / agent_name / "memory"
    memory_file = memory_dir / "memory.md"
    memory_dir.mkdir(parents=True, exist_ok=True)

    existing = ""
    if memory_file.exists():
        existing = memory_file.read_text(encoding="utf-8")

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = await get_async_db()
    try:
        rows = await fetch_all(
            conn,
            "SELECT date, title, body FROM memory_entries WHERE agent=? AND date>=? ORDER BY date",
            (agent_name, cutoff),
        )
    finally:
        await conn.close()

    if not rows:
        log.info("No recent entries for %s, skip consolidate", agent_name)
        return existing

    summary_lines = [f"- [{r['date']}] {r['title'][:50]}" for r in rows[-5:]]
    fallback = "\n".join(summary_lines)
    new_memory = _merge_memory(existing, fallback)
    memory_file.write_text(new_memory, encoding="utf-8")
    log.info("Consolidated %s: %d chars", agent_name, len(new_memory))
    return new_memory


def _merge_memory(existing: str, new_content: str) -> str:
    """合併既有 memory 與新蒸餾內容，保持在上限內。"""
    if not existing.strip():
        header = "# 持久事實\n\n> 上限 2000 tokens。蒸餾自 daily log。\n\n"
        return (header + new_content.strip())[:MAX_MEMORY_CHARS]

    merged = existing.rstrip() + "\n\n## 最新蒸餾\n\n" + new_content.strip()

    if len(merged) > MAX_MEMORY_CHARS:
        merged = merged[-MAX_MEMORY_CHARS:]
        first_newline = merged.find("\n")
        if first_newline > 0:
            merged = merged[first_newline + 1:]

    return merged
