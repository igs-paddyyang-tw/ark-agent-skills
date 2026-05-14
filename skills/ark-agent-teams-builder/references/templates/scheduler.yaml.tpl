# scheduler.yaml 模板
# 必產 job：hourly-progress, daily-summary（target: leader）
# 條件 job：daily-qa-review（有 qa）、wiki-maintenance（≥5人）、weekly-data-report（有 analyst）

timezone: Asia/Taipei

jobs:
  - name: hourly-progress
    target: {leader_instance}
    prompt: "⏰ 確認團隊狀態，query_team_status 後依計劃派工或追蹤。更新 memory.md。"
    cron: "10 9-21 * * *"

  - name: daily-summary
    target: {leader_instance}
    prompt: "📋 今日摘要：整理成果 + 明日計劃，reply 回報。"
    cron: "daily:21:00"

# 條件式 job（依角色自動加入）：
#
# - name: daily-qa-review
#   target: qa-agent
#   prompt: "🔍 每日品質檢查：比對 specs 與測試結果，產出評估建議。"
#   cron: "daily:12:30"
#
# - name: wiki-maintenance
#   target: {leader_instance}
#   prompt: "📚 Wiki 巡檢：掃全隊 knowledge/learning.md，超標派整理。"
#   cron: "0 12,18 * * *"
#
# - name: weekly-data-report
#   target: analyst-agent
#   prompt: "📈 週報：本週數據摘要 + 趨勢分析。"
#   cron: "0 10 * * 1"
