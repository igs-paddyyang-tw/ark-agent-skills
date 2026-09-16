---
name: daily-report
description: 整理今日完成任務、產出摘要與明日計劃
layer: ops
roles: [leader, worker]
tools_required: [query_team_status, list_tasks, reply]
inputs: []
outputs:
  format: md
  contract: md-report
example: true
---

## 任務

請產出今日工作日報：

1. 整理今日完成的任務（`query_team_status` + `list_tasks`）
2. 整合各 worker 的產出摘要
3. 列出明日計劃
4. 用 `reply` 回報日報摘要（≤ 200 字）

## 輸出樣板

```
# {{agent_name}} 日報 · {date}
## 今日完成
- {task}（{產出路徑，落 {{artifacts_dir}}}）
## 明日計劃
- {task}
```

## 範例

### 輸入
（每日 18:00 觸發，無額外輸入）

### 期望輸出
# report-agent 日報 · 2026-09-16
## 今日完成
- RTP 驗證報告（artifacts/reports/rtp-2026-09-16.md）
## 明日計劃
- 壓測基準對比
