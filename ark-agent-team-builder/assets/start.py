"""{PROJECT_NAME} 團隊啟動入口 —— 框架在 ark_team_agent 套件裡。

設定集中在 team.yaml（+ scheduler.yaml 選用 + .env 機密）。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from ark_team_agent.team import run_team

if __name__ == "__main__":
    try:
        asyncio.run(run_team(Path("team.yaml")))
    except KeyboardInterrupt:
        print("\n平台已停止。")
