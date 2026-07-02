"""Agent Memory — 對話完成後自動寫入 knowledge/raw/。

每次 Agent 完成任務後：
  1. 寫入任務記錄（user_id + task + result）
  2. 檔案路徑：agents/{agent_id}-agent/knowledge/raw/{timestamp}_user{id}.md
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def save_memory(
    agent_id: str,
    user_id: int,
    task: str,
    result: str,
    *,
    status: str = "completed",
    base_dir: Path | None = None,
) -> Path:
    """Agent 完成任務後寫入 memory。

    Args:
        agent_id: Agent ID（如 "news"）
        user_id: 使用者 Telegram ID
        task: 使用者原始訊息
        result: Agent 回覆內容
        status: completed | failed
        base_dir: 專案根目錄（預設 .）

    Returns:
        寫入的檔案路徑
    """
    base = base_dir or Path(".")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"{timestamp}_user{user_id}.md"
    path = base / f"agents/{agent_id}-agent/knowledge/raw/{filename}"
    path.parent.mkdir(parents=True, exist_ok=True)

    # 截取 task 和 result 避免過長
    task_preview = task[:200]
    result_preview = result[:2000] if result else "(無回覆)"

    content = f"""---
user_id: {user_id}
agent: {agent_id}-agent
task: "{task_preview}"
timestamp: {datetime.now().isoformat()}
status: {status}
---

## 任務

{task_preview}

## 結果

{result_preview}
"""
    path.write_text(content, encoding="utf-8")
    return path
