"""{PROJECT_NAME} 啟動入口 —— 框架在 ark_bot_agent 套件裡。

設定：agents.yaml（有誰）+ bot.yaml（怎麼跑）+ .env（機密）
診斷：python -m ark_bot_agent paths
"""
from ark_bot_agent import run_bot

# 🔴 沒有業務 skill 時就用 run_bot()，**不要**寫成 run_bot(skills=["skills"])
#    —— 指向空的 skills/ 會讓啟動橫幅永遠印「⚠️ 注入了 skills 但一個都沒載到」，
#    而常駐假警報會讓人習慣性忽略整個橫幅。
#    等 skills/<name>/SKILL.md 真的存在了，再改成 run_bot(skills=["skills"])。
# 通用能力走 .kiro/skills/（IDE 層），不經這裡注入。
run_bot()
