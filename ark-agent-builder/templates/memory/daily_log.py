"""情節記憶：任務結束後自動追加 daily log（固定模板，不用 LLM）。"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


async def write_daily_log(
    agent_name: str,
    task_id: str,
    conversation: str,
    agents_dir: Path | None = None,
) -> Path:
    """寫入 daily log，回傳寫入的檔案路徑。

    使用固定模板，不呼叫 LLM（省 API call + 格式 100% 可控）。

    Args:
        agent_name: Agent 名稱（如 _default、coder-agent）
        task_id: 任務識別碼（如 msg-584）
        conversation: "User: ...\nAgent: ..." 格式的對話摘要
        agents_dir: agents 根目錄，預設為專案內的 agents/
    """
    # 決定寫入路徑
    if agent_name == "_default":
        memory_dir = Path(__file__).resolve().parents[2] / "memory" / "daily"
    else:
        if agents_dir is None:
            agents_dir = Path(__file__).resolve().parents[2] / "agents"
        memory_dir = agents_dir / agent_name / "memory" / "daily"

    memory_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    daily_file = memory_dir / f"{today}.md"
    now_time = datetime.now().strftime("%H:%M")

    # 解析 conversation
    lines = conversation.split("\n", 1)
    user_msg = lines[0].replace("User: ", "").strip() if lines else ""
    agent_msg = lines[1].replace("Agent: ", "").strip() if len(lines) > 1 else ""

    # 截斷
    user_msg = user_msg[:150]
    agent_msg = agent_msg[:200]

    # 固定模板
    entry = (
        f"## {now_time} [{agent_name}] {task_id}\n"
        f"- Q: {user_msg}\n"
        f"- A: {agent_msg}\n"
    )

    # Append 到 daily 檔案
    with open(daily_file, "a", encoding="utf-8") as f:
        if daily_file.stat().st_size == 0:
            f.write(f"# {today} Daily Log\n\n")
        f.write(entry + "\n")

    log.info("Daily log written: %s (%d chars)", daily_file.name, len(entry))

    # 增量索引到 FTS5（讓 recall 能搜到）
    try:
        from src.memory.indexer import get_connection, _index_file, SOURCE_DAILY
        conn = get_connection()
        _index_file(conn, daily_file, agent_name, SOURCE_DAILY)
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("FTS5 index failed: %s", e)

    return daily_file
