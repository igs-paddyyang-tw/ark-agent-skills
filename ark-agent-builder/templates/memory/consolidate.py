"""蒸餾：daily log → memory.md（手動觸發）。"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
AGENTS_DIR = BASE_DIR / "agents"

_CONSOLIDATE_PROMPT = """\
你是記憶蒸餾員。根據以下 daily log 和現有 memory.md，判斷哪些是「下個月還有用的持久事實」。

規則：
1. 只保留：環境慣例、工具怪癖、人與偏好、進行中的長期事項
2. 不保留：臨時任務進度、一次性操作、已解決的問題
3. 輸出格式跟現有 memory.md 一樣（四個分節）
4. 總長度 ≤ 2000 tokens
5. 如果沒有新增持久事實，回覆「NO_CHANGE」

現有 memory.md：
---
{memory_content}
---

最近 daily log：
---
{daily_content}
---

請輸出更新後的完整 memory.md 內容（含四個分節標題）：
"""


async def consolidate(agent_name: str) -> dict:
    """手動蒸餾：讀 daily log → LLM 判斷 → 更新 memory.md。

    agent_name="_default" 時，讀根目錄 memory/。
    """
    if agent_name == "_default":
        memory_dir = BASE_DIR / "memory"
    else:
        agent_path = AGENTS_DIR / agent_name
        memory_dir = agent_path / "memory"

    memory_file = memory_dir / "memory.md"
    daily_dir = memory_dir / "daily"

    # 讀現有 memory.md
    memory_content = ""
    if memory_file.exists():
        memory_content = memory_file.read_text(encoding="utf-8")

    # 收集最近 7 天 daily log
    daily_content = ""
    today = datetime.now().date()
    for i in range(7):
        date = today - timedelta(days=i)
        daily_file = daily_dir / f"{date.isoformat()}.md"
        if daily_file.exists():
            daily_content += daily_file.read_text(encoding="utf-8") + "\n\n"

    if not daily_content.strip():
        return {"status": "no_data", "message": "No daily logs found in last 7 days"}

    # LLM 蒸餾
    try:
        from src.llm.chat import simple_chat
        prompt = _CONSOLIDATE_PROMPT.format(
            memory_content=memory_content[:2000],
            daily_content=daily_content[:4000],
        )
        result = await simple_chat(
            prompt=prompt,
            system="你是記憶蒸餾員，只輸出 memory.md 內容或 NO_CHANGE。",
        )

        if not result or "NO_CHANGE" in result:
            return {"status": "no_change", "message": "No new persistent facts detected"}

        # 寫入
        old_content = memory_content
        memory_file.write_text(result.strip(), encoding="utf-8")

        # Git commit（best effort）
        try:
            subprocess.run(
                ["git", "add", str(memory_file)],
                cwd=str(BASE_DIR), capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", f"memory: consolidate {agent_name}"],
                cwd=str(BASE_DIR), capture_output=True, timeout=10,
            )
        except Exception:
            pass

        log.info("Consolidated %s: memory.md updated", agent_name)
        return {
            "status": "updated",
            "agent": agent_name,
            "old_size": len(old_content),
            "new_size": len(result),
            "committed": True,
        }

    except Exception as e:
        log.error("Consolidate failed for %s: %s", agent_name, e)
        return {"status": "error", "message": str(e)}
