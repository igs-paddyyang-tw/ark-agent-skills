"""情節記憶：任務結束後自動追加 daily log。"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .indexer import index_entry

log = logging.getLogger("memory.daily_log")

# Fallback 模板（無 LLM 摘要）
_FALLBACK_TEMPLATE = (
    "## {time} [{agent}] task:{task_id}\n"
    "- **做了**：{snippet}\n"
    "- tags: task\n"
)


async def write_daily_log(
    agent_name: str,
    task_id: str,
    conversation: str,
    agents_dir: Path | None = None,
) -> str:
    """寫入 daily log（檔案 + DB FTS5）。

    Args:
        agent_name: Agent 名稱（如 coder-agent）
        task_id: 任務識別碼
        conversation: 任務對話摘要
        agents_dir: agents 根目錄

    Returns:
        寫入的 entry 文字
    """
    if agents_dir is None:
        agents_dir = Path("agents")

    memory_dir = agents_dir / agent_name / "memory" / "daily"
    memory_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    daily_file = memory_dir / f"{today}.md"
    now_time = datetime.now().strftime("%H:%M")

    # 直接用 fallback 模板（移除 Gemini 依賴）
    entry = _FALLBACK_TEMPLATE.format(
        time=now_time,
        agent=agent_name,
        task_id=task_id,
        snippet=conversation[:100].replace("\n", " "),
    )

    # Append 到 daily 檔案
    mode = "a"
    with open(daily_file, mode, encoding="utf-8") as f:
        if daily_file.stat().st_size == 0:
            f.write(f"# {today} Daily Log\n\n")
        f.write(entry + "\n\n")

    # 寫入 DB（FTS5 自動索引）
    title_line = entry.splitlines()[0] if entry else f"{now_time} [{agent_name}]"
    await index_entry(
        agent=agent_name,
        source="daily",
        date=today,
        title=title_line,
        body=entry,
        tags="task",
    )

    log.info("Daily log: %s (%d chars)", agent_name, len(entry))
    return entry
