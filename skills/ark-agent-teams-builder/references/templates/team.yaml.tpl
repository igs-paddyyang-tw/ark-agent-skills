# team.yaml 模板
# 佔位符：{instances_block}, {channel_block}

defaults:
  backend: kiro-cli
  model: auto

cost_guard:
  daily_limit_usd: 30.0
  warn_at_percentage: 80
  timezone: Asia/Taipei

hang_detector:
  enabled: true
  timeout_minutes: 60
  escalation_minutes: 180

{channel_block}

instances:
{instances_block}

health_port: 13030
