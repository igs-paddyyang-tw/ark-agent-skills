"""Agent CLI — 透過 kiro-cli 執行對話（支援多 Agent）。

Agent 清單定義在此，session 管理由 session.py 負責。
"""
from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

# ── 可用 Agent 清單 ──
AVAILABLE_AGENTS = {
    "admin": {
        "dir": "agents/admin-agent",
        "name": "Admin Agent",
        "emoji": "👑",
        "desc": "管家 + 智能分流（預設）",
    },
    "pm": {
        "dir": "agents/pm-agent",
        "name": "PM Agent",
        "emoji": "📋",
        "desc": "專案經理 + 派工",
    },
    "ai-dev": {
        "dir": "agents/ai-dev-agent",
        "name": "AI Dev Agent",
        "emoji": "🧠",
        "desc": "AI 工程師 + Prompt 設計",
    },
    "coder": {
        "dir": "agents/coder-agent",
        "name": "Coder Agent",
        "emoji": "💻",
        "desc": "全端開發 + 程式碼實作",
    },
    "qa": {
        "dir": "agents/qa-agent",
        "name": "QA Agent",
        "emoji": "🧪",
        "desc": "品質保證 + 測試",
    },
    "data": {
        "dir": "agents/data-agent",
        "name": "Data Agent",
        "emoji": "📊",
        "desc": "數據分析（內部）",
    },
    "market": {
        "dir": "agents/market-agent",
        "name": "Market Agent",
        "emoji": "🗺️",
        "desc": "市場研究（外部）",
    },
    "report": {
        "dir": "agents/report-agent",
        "name": "Report Agent",
        "emoji": "📝",
        "desc": "報告產出（彙整）",
    },
}


def is_cli_available() -> bool:
    """檢查 kiro-cli 是否已安裝。"""
    return shutil.which("kiro-cli") is not None


async def agent_cli_chat(
    message: str,
    *,
    agent_id: str = "admin",
    timeout: int = 60,
) -> str | None:
    """透過 kiro-cli 執行對話。

    Args:
        message: 使用者訊息
        agent_id: 指定 Agent（決定 working_dir → .kiro/）
        timeout: 超時秒數
    """
    if not is_cli_available():
        return None

    info = AVAILABLE_AGENTS.get(agent_id, AVAILABLE_AGENTS["admin"])
    working_dir = Path(info["dir"])

    # 確認 .kiro/ 存在
    if not (working_dir / ".kiro" / "steering" / "SOUL.md").exists():
        working_dir = Path(".")

    try:
        proc = await asyncio.create_subprocess_exec(
            "kiro-cli", "chat",
            "--trust-all-tools",
            "--legacy-ui",
            "--message", message,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )

        if proc.returncode != 0:
            return None

        output = stdout.decode("utf-8").strip()
        output = _clean_output(output)
        return output if output else None

    except asyncio.TimeoutError:
        proc.kill()
        return None
    except Exception:
        return None


def _clean_output(text: str) -> str:
    """移除 ANSI escape codes。"""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    lines = [line for line in text.split("\n") if line.strip()]
    return "\n".join(lines)
