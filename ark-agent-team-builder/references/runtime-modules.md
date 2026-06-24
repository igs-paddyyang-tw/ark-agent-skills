# Runtime 模組規格（v2.0 — 對齊 ark-team-agent v0.14）

> 本文件描述 Skill 產出的精簡版 runtime 規格，並標註與成熟套件的差異。

## 設計原則

- asyncio 原生（subprocess + HTTP API）
- 手寫 stdio JSON-RPC MCP Server（不用 mcp SDK）
- Windows + Linux 相容
- 精簡版 ~1000 行（7 模組）；成熟版 ~6000 行（37 模組）

---

## 模組規格（精簡版 — Skill 產出）

### daemon.py（~200 行）

```python
class CoreDaemon:
    def __init__(self, config_path: str): ...
    async def run(self): ...
    async def start_instance(self, name, cfg): ...
    async def stop_instance(self, name): ...
    async def shutdown(self): ...
    async def _health_check(self): ...
```

職責：讀取 team.yaml → 啟動 kiro-cli → 健康監控 → 優雅關閉

### backend.py（~150 行）

```python
class KiroBackend:
    def build_command(self, cfg) -> list[str]: ...
    def write_steering(self, cfg, instances): ...
    def write_mcp_config(self, cfg): ...
    def write_team_context(self, cfg, instances): ...
```

職責：組裝 CLI 指令 + 寫入 .kiro/steering/ + 注入 MCP

### config.py（~100 行）

```python
@dataclass
class InstanceConfig:
    working_directory: str
    description: str
    role: str  # admin | leader | worker
    model: str = "auto"
    skip_resume: bool = False

@dataclass
class TeamConfig:
    instances: dict[str, InstanceConfig]
    health_port: int = 13030
    model: str = "auto"

def load_config(path: str) -> TeamConfig: ...
```

### process.py（~80 行）

```python
class AgentProcess:
    async def start(self): ...
    async def kill(self): ...
    def is_alive(self) -> bool: ...
    async def send(self, text: str): ...
```

### mcp_server.py（~300 行）

stdio JSON-RPC 2.0 MCP Server，精簡版 10 工具：

| 工具 | 參數 | 用途 |
|------|------|------|
| reply | text, kind | 回覆使用者 |
| send_to_instance | instance, msg | 跨 agent 通訊 |
| delegate_task | instance, task | 委派任務 |
| query_team_status | — | 查詢團隊狀態 |
| create_task | title, assignee, ... | 建立任務 |
| update_task | task_id, status, note | 更新任務 |
| log_to_leader | text | 私下回報 leader |
| list_tasks | status | 列出任務板 |
| record_spend | amount_usd, note | 記錄成本 |
| broadcast_all | message | 廣播全員 |

### api.py（~100 行）

FastAPI HTTP server：

```
GET  /health            → {"status": "ok", "instances": {...}}
POST /send/{name}       → 發送訊息
GET  /status            → 全部 instance 狀態
POST /reply             → Agent 回覆（轉發到 TG）
```

### scheduler.py（~80 行）

基於 APScheduler 的排程引擎，支援：
- 標準 5-field cron：`10 9-21 * * *`
- 簡寫：`daily:21:00`、`hourly:10`

---

## 成熟版額外模組（ark-team-agent v0.14）

以下模組在精簡版中不存在，屬於「遷移升級」後才獲得的能力：

### 對話智能層

| 模組 | 行數 | 職責 |
|------|------|------|
| telegram.py | ~500 | 完整 TG Bot（session + 路由 + 分段 + reaction） |
| planner.py | ~200 | 意圖路由（ConversationPlanner） |
| session.py | ~150 | Session 管理（Turn-based） |
| chat_router.py | ~100 | @mention 路由解析 |
| memory.py | ~100 | 使用者偏好記憶 |

### 訊息持久化層

| 模組 | 行數 | 職責 |
|------|------|------|
| message_queue.py | ~150 | 訊息佇列（backpressure） |
| message_store.py | ~100 | SQLite 訊息持久化 |
| message_overflow.py | ~80 | 溢出訊息 DB 保存 |

### 風控與監控層

| 模組 | 行數 | 職責 |
|------|------|------|
| cost_guard.py | ~120 | 成本熔斷（daily limit） |
| failure_memory.py | ~100 | 重複失敗偵測（ECHO pattern） |
| event_log.py | ~150 | 事件溯源（SQLite） |
| watchdog.py | ~80 | 外部看門狗 |
| heartbeat.py | ~60 | 心跳偵測 |

### UX 與反饋層

| 模組 | 行數 | 職責 |
|------|------|------|
| progress.py | ~100 | 進度報告渲染 |
| tool_tracker.py | ~120 | MCP 工具使用追蹤 |
| feedback.py | ~80 | 錯誤分類與終端回饋 |
| reaction_manager.py | ~60 | Telegram 表情反應 |

### 自演化層

| 模組 | 行數 | 職責 |
|------|------|------|
| skill_growth.py | ~100 | 自動偵測新技能時機 |
| skill_extractor.py | ~80 | 從 output 提煉 skill.md |
| daily_summary.py | ~100 | 每日摘要產生 |
| conversation_log.py | ~80 | 對話記錄歸檔 |

### 品質閘門（子套件）

| 模組 | 職責 |
|------|------|
| code_spec_validator/validator.py | 主入口：validate_project |
| code_spec_validator/api_extractor.py | 提取 API 端點 |
| code_spec_validator/spec_parser.py | 解析 spec 文件 |
| code_spec_validator/schema_extractor.py | 提取 Schema |
| code_spec_validator/dependency_extractor.py | 提取依賴圖 |
| code_spec_validator/diff_engine.py | 比對產出 DriftReport |

---

## MCP 工具完整清單（成熟版 14 個）

| # | 工具 | 參數 | 權限 | 精簡版有 |
|---|------|------|------|---------|
| 1 | reply | text, kind | 全員 | ✅ |
| 2 | send_to_instance | instance, msg | 全員 | ✅ |
| 3 | delegate_task | instance, task | admin/leader | ✅ |
| 4 | query_team_status | — | 全員 | ✅ |
| 5 | create_task | title, assignee, priority | admin/leader | ✅ |
| 6 | update_task | task_id, status, note | 全員 | ✅ |
| 7 | log_to_leader | text | worker | ✅ |
| 8 | list_tasks | status | 全員 | ✅ |
| 9 | record_spend | amount_usd, note | 全員 | ✅ |
| 10 | broadcast_all | message | admin/leader | ✅ |
| 11 | wiki_query | query, scope | 全員 | ❌ |
| 12 | wiki_ingest | source_path, scope | 全員 | ❌ |
| 13 | reply_file | file_path, caption | 全員 | ❌ |
| 14 | reply_task_image | image_path, caption | 全員 | ❌ |

---

## Config 結構（成熟版 12 dataclass）

| Dataclass | 精簡版 | 成熟版新增欄位 |
|-----------|--------|---------------|
| TeamConfig | ✅ | name, examples, team_md, kiro_files, startup, restart_policy |
| InstanceConfig | ✅ | topic_id, private_chat, model_failover, auto_start, tags |
| CostGuardConfig | ✅ | per_instance_limits |
| HangDetectorConfig | ✅ | active_start_hour, active_end_hour |
| SchedulerConfig | ❌ | 獨立排程配置 |
| ScheduledJobConfig | ❌ | reply_to, enabled |
| StartupConfig | ❌ | concurrency, stagger_delay_ms |
| RestartPolicy | ❌ | max_retries, backoff, reset_after |
| P2PConfig | ❌ | max_rounds, round_timeout |
| KiroFilesPolicy | ❌ | team_md, steering, mcp |
| CommunicationConfig | ❌ | rate_limit, max_message_length |
| ChannelConfig | ❌ | topics, forum 設定 |
