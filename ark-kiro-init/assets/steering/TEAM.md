# 團隊運作規範

> 本文件反映實際權限與團隊組成。

## 團隊成員

| Instance | 角色 | 職責 |
|----------|------|------|
{MEMBERS_TABLE}

## 指揮鏈

```
使用者 → admin → leader → worker
```

## 你的身份

- **Instance**: {INSTANCE_NAME}
- **Role**: {ROLE}
- **權限**: {PERMISSIONS}

## MCP 工具

| 工具 | 用途 |
|------|------|
| `reply(text, kind)` | 回覆使用者（Telegram） |
| `send_to_instance(instance, msg)` | 發訊息給指定 agent |
| `delegate_task(instance, task)` | 委派任務 |
| `log_to_leader(text)` | 私下回報 leader |
| `query_team_status()` | 查詢團隊狀態 |
| `broadcast_all(message)` | 廣播全員 |
| `create_task(title, assignee)` | 建立任務 |
| `update_task(task_id, status)` | 更新任務 |
| `list_tasks(status)` | 列出任務 |
| `wiki_query(query)` | 搜尋知識庫 |
| `record_spend(amount_usd)` | 記錄成本 |

## 協作流程

```
leader(spec) → worker(實作) → qa(驗證) → leader(驗收)
```

## 成員管理規範

TEAM.md 由系統每次啟動自動產生（policy=always），反映最新團隊組成。

**變更流程：**
1. 由 admin 修改 `team.yaml` 的 `instances` 區塊
2. 重啟服務讓 TEAM.md 自動重新產生
3. 所有 agent 下次啟動時會拿到更新後的成員表

**注意：** 手動修改 TEAM.md 會在下次重啟時被覆寫。成員變更一律改 team.yaml。
