---
title: "MCP 工具使用指南"
type: concept
tags: [mcp, tools, communication, guide]
created: {{TODAY}}
updated: {{TODAY}}
status: mature
---

# MCP 工具使用指南

## 工具總覽

你（Agent）可透過 MCP 工具與系統互動。以下是使用規則：

## 回覆使用者

| 情境 | 呼叫方式 |
|------|---------|
| 最終結論 | `reply(text="結論", kind="primary")` |
| 補充資訊 | `reply(text="補充", kind="followup")` |

**規則：**
- 最後一則 reply 必須是 `primary`
- 字數 ≤ 150（TG 回覆）
- 不貼 raw stdout / stack trace

## 跨 Agent 通訊

| 我想要... | 用哪個 |
|-----------|--------|
| 請另一個 agent 幫忙 | `send_to_instance(instance="target-agent", msg="請求")` |
| 正式派工（含格式） | `delegate_task(instance="worker-agent", task="📋 任務...")` |
| 通知所有人 | `broadcast_all(message="公告")` |
| 私下回報 leader | `log_to_leader(text="錯誤詳情")` |

**通訊禮儀：**
- worker 不能直接 reply 使用者，要先 send 給 leader 整合
- 錯誤詳情用 log_to_leader，不要暴露給使用者
- delegate_task 請用標準派工格式

## 任務管理

| 動作 | 工具 |
|------|------|
| 建立新任務 | `create_task(title="...", assignee="worker-agent", priority="high")` |
| 更新進度 | `update_task(task_id="TASK-001", status="in_progress", note="已開始")` |
| 查看任務板 | `list_tasks(status="all")` |

**status 值：** todo / in_progress / done / blocked

## 團隊狀態

```
query_team_status()
→ {"ok": true, "instances": {"pm-agent": "running", "coder-agent": "crashed"}}
```

用於：每小時巡檢、確認 agent 是否在線。

## 成本記錄

```
record_spend(amount_usd=0.5, note="Gemini API call for summarization")
```

- 每次 LLM API 呼叫後記錄
- 超過 daily_limit 時 admin 會暫停高消費 agent

## 知識庫操作

| 動作 | 工具 |
|------|------|
| 搜尋知識 | `wiki_query(query="Redis 故障", scope="all")` |
| 匯入新知識 | `wiki_ingest(source_path="knowledge/raw/notes.md", scope="private")` |

**scope 說明：**
- `shared`：團隊公共知識庫
- `private`：個人知識庫
- `all`：搜尋所有範圍

## 檔案傳送

| 動作 | 工具 |
|------|------|
| 傳檔案 | `reply_file(file_path="/abs/path/report.pdf", caption="日報")` |
| 傳圖片 | `reply_task_image(image_path="/abs/path/chart.png", caption="KPI 圖表")` |

**注意：** 路徑必須是絕對路徑。
