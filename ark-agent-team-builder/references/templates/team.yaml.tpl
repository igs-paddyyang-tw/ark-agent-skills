# team.yaml 模板
# 佔位符：{instances_block}, {channel_block}
# 註：kiro_files / access / knowledge_search_order 是真實部署都需要的區塊
#     （2026-09-11 建 market-team-agent 時發現原範本缺這幾塊，補上）。

defaults:
  backend: kiro-cli
  model: auto

# 知識庫查詢櫃順序（自有櫃 + shared）。移除或留一個 shared 皆可。
knowledge_search_order: [shared]

# 🔴 skill 自動鋪設：policy=skip 交 sync 管（否則每次啟動推翻角色矩陣）；
#    team_md=always → 成員表以 team.yaml 為唯一真相每次同步（設 once 會凍結幽靈成員）。
kiro_files:
  skills:
    policy: skip
  steering:
    team_md: always

{channel_block}

# 存取控制（設定不是機密；token 才放 .env）
access:
  mode: group                        # group=群組全放行；private 仍需白名單
  allowed_users:
    - 000000000                      # 換成實際 TG user_id

cost_guard:
  daily_limit_usd: 30.0
  warn_at_percentage: 80
  timezone: Asia/Taipei

hang_detector:
  enabled: true
  timeout_minutes: 180               # 1.2.16 起 hang 只對 RUNNING 生效，可用 180
  escalation_minutes: 360

instances:
{instances_block}

health_port: 13030
