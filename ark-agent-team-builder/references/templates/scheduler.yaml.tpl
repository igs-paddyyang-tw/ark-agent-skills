# scheduler.yaml 模板（3.3.0 起：有事才叫 LLM —— 見 references/schedule-cost.md）
# 必產 job：progress-check、weekly-summary（皆經 scripts/sched_gate.py 閘門，規則在 config/gated_jobs.json）
# 條件 job：qa-review（有 qa）、wiki-maintenance（≥5人）、weekly-data-report（有 analyst）
# 🔴 不要再用「每小時 query_team_status」：閒置時每次都是一個完整 LLM 回合，只換來一句「沒事」

timezone: Asia/Taipei

jobs:
  - name: progress-check            # 任務板有未完成任務才喚醒 {leader_instance}（7 天保底一次）
    type: command
    command: [".venv/bin/python", "scripts/sched_gate.py", "progress-check"]
    cron: "10 9 * * 1-5"

  - name: weekly-summary            # 本週有人寫 daily 才摘要
    type: command
    command: [".venv/bin/python", "scripts/sched_gate.py", "weekly-summary"]
    cron: "0 21 * * 5"

  - name: memory-distill            # 只喚醒有新 daily 的 agent（取代 broadcast_all）
    type: command
    command: [".venv/bin/python", "scripts/sched_gate.py", "memory-distill"]
    cron: "20 3 * * 0"

  - name: preflight                 # 機械健檢，零 LLM
    target: _builtin:preflight
    cron: "50 8 * * 1-5"

# 條件式 job（依角色自動加入；閘門規則見 config/gated_jobs.json 範本）：
#
# - name: qa-review                 # 近 7 天 src／tests 有 commit 才叫 qa-agent
#   type: command
#   command: [".venv/bin/python", "scripts/sched_gate.py", "qa-review"]
#   cron: "30 12 * * 3"
#
# - name: wiki-maintenance          # knowledge/raw 有新檔才叫
#   type: command
#   command: [".venv/bin/python", "scripts/sched_gate.py", "wiki-maintenance"]
#   cron: "0 18 * * 5"
#
# - name: weekly-data-report        # 內容產出，固定叫 LLM（和團隊忙不忙無關）
#   target: analyst-agent
#   prompt: "📈 週報：本週數據摘要 + 趨勢分析。"
#   cron: "0 10 * * 1"
