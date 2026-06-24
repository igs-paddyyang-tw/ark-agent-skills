# MCP Tools 完整規格（v0.14）

> 14 個 MCP 工具的參數、回傳值、權限與使用情境。

---

## 權限模型

| 角色 | 可用工具 |
|------|---------|
| admin | 全部 14 個 |
| leader | 全部（除 admin-only 標註） |
| worker | reply, send_to_instance, query_team_status, log_to_leader, list_tasks, update_task, record_spend, wiki_query, wiki_ingest, reply_file, reply_task_image |

---

## 工具清單

### 1. reply

回覆使用者（Telegram 唯一出口）。

```json
{
  "name": "reply",
  "inputSchema": {
    "type": "object",
    "properties": {
      "text": {"type": "string", "description": "回覆內容（≤ 4096 字元）"},
      "kind": {"type": "string", "enum": ["primary", "followup"], "default": "primary"}
    },
    "required": ["text"]
  }
}
```

| kind | 行為 |
|------|------|
| primary | 最終結論，送到 TG |
| followup | 補充資訊，加 ↪️ 前綴 |

### 2. send_to_instance

發訊息給指定 agent。

```json
{
  "name": "send_to_instance",
  "inputSchema": {
    "type": "object",
    "properties": {
      "instance": {"type": "string", "description": "目標 agent 名稱"},
      "msg": {"type": "string", "description": "訊息內容"}
    },
    "required": ["instance", "msg"]
  }
}
```

### 3. delegate_task

委派任務（加格式前綴）。限 admin / leader。

```json
{
  "name": "delegate_task",
  "inputSchema": {
    "type": "object",
    "properties": {
      "instance": {"type": "string"},
      "task": {"type": "string", "description": "任務描述（建議用標準派工格式）"}
    },
    "required": ["instance", "task"]
  }
}
```

### 4. query_team_status

查詢全隊狀態，回傳每個 instance 的 running/stopped/crashed。

```json
{
  "name": "query_team_status",
  "inputSchema": {"type": "object", "properties": {}}
}
```

回傳範例：
```json
{"ok": true, "instances": {"pm-agent": "running", "coder-agent": "running"}}
```

### 5. create_task

建立任務到 board.json。限 admin / leader。

```json
{
  "name": "create_task",
  "inputSchema": {
    "type": "object",
    "properties": {
      "title": {"type": "string"},
      "assignee": {"type": "string"},
      "priority": {"type": "string", "enum": ["high", "medium", "low"]},
      "description": {"type": "string"}
    },
    "required": ["title", "assignee"]
  }
}
```

### 6. update_task

更新任務狀態。

```json
{
  "name": "update_task",
  "inputSchema": {
    "type": "object",
    "properties": {
      "task_id": {"type": "string"},
      "status": {"type": "string", "enum": ["todo", "in_progress", "done", "blocked"]},
      "note": {"type": "string"}
    },
    "required": ["task_id", "status"]
  }
}
```

### 7. log_to_leader

私下回報 leader（使用者看不到）。

```json
{
  "name": "log_to_leader",
  "inputSchema": {
    "type": "object",
    "properties": {
      "text": {"type": "string", "description": "回報內容"}
    },
    "required": ["text"]
  }
}
```

### 8. list_tasks

列出任務板。

```json
{
  "name": "list_tasks",
  "inputSchema": {
    "type": "object",
    "properties": {
      "status": {"type": "string", "enum": ["all", "todo", "in_progress", "done", "blocked"]}
    }
  }
}
```

### 9. record_spend

記錄 API 成本消費。

```json
{
  "name": "record_spend",
  "inputSchema": {
    "type": "object",
    "properties": {
      "amount_usd": {"type": "number"},
      "note": {"type": "string"}
    },
    "required": ["amount_usd"]
  }
}
```

### 10. broadcast_all

廣播訊息給所有 agent。限 admin / leader。

```json
{
  "name": "broadcast_all",
  "inputSchema": {
    "type": "object",
    "properties": {
      "message": {"type": "string"}
    },
    "required": ["message"]
  }
}
```

### 11. wiki_query

搜尋知識庫（keyword 全文搜尋）。

```json
{
  "name": "wiki_query",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "搜尋關鍵字"},
      "scope": {"type": "string", "enum": ["shared", "private", "all"], "default": "all"}
    },
    "required": ["query"]
  }
}
```

### 12. wiki_ingest

匯入知識到知識庫。

```json
{
  "name": "wiki_ingest",
  "inputSchema": {
    "type": "object",
    "properties": {
      "source_path": {"type": "string", "description": "來源檔案路徑（raw/ 下）"},
      "scope": {"type": "string", "enum": ["shared", "private"], "default": "private"}
    },
    "required": ["source_path"]
  }
}
```

### 13. reply_file

傳送檔案給使用者（Telegram）。

```json
{
  "name": "reply_file",
  "inputSchema": {
    "type": "object",
    "properties": {
      "file_path": {"type": "string", "description": "檔案絕對路徑"},
      "caption": {"type": "string", "description": "檔案說明"}
    },
    "required": ["file_path"]
  }
}
```

### 14. reply_task_image

傳送圖片給使用者（Telegram）。

```json
{
  "name": "reply_task_image",
  "inputSchema": {
    "type": "object",
    "properties": {
      "image_path": {"type": "string", "description": "圖片絕對路徑"},
      "caption": {"type": "string", "description": "圖片說明"}
    },
    "required": ["image_path"]
  }
}
```

---

## 使用情境對照

| 我想要... | 用哪個工具 |
|-----------|-----------|
| 回答使用者問題 | `reply(text, "primary")` |
| 補充說明 | `reply(text, "followup")` |
| 請另一個 agent 幫忙 | `send_to_instance(target, msg)` |
| 正式派工給 worker | `delegate_task(worker, task)` |
| 看看大家在幹嘛 | `query_team_status()` |
| 建立新任務追蹤 | `create_task(title, assignee)` |
| 回報錯誤（不讓使用者看到） | `log_to_leader(text)` |
| 通知所有人 | `broadcast_all(message)` |
| 記錄 API 花費 | `record_spend(amount, note)` |
| 搜尋過去的知識 | `wiki_query(keyword)` |
| 整理新知識到庫 | `wiki_ingest(path)` |
| 傳檔案給使用者 | `reply_file(path, caption)` |
| 傳圖片給使用者 | `reply_task_image(path, caption)` |
