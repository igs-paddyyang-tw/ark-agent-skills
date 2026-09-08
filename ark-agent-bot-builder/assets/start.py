"""{PROJECT_NAME} 啟動入口 —— 框架在 ark_bot_agent 套件裡。

設定：agents.yaml（有誰）+ bot.yaml（怎麼跑）+ .env（機密）
診斷：python -m ark_bot_agent paths
"""
from ark_bot_agent import run_bot

# 業務 skill 目錄（選填）；純套件消費端可留空 run_bot()
run_bot(skills=["skills"])
