# 系統架構

## 總覽

```mermaid
graph TB
    U[使用者] -->|Telegram / Web| TG[TelegramAdapter]
    TG -->|@mention 路由| CR[ChatRouter]
    CR -->|意圖判斷| PL[Planner]
    PL -->|轉發| D[Daemon]
    D -->|讀取| C[team.yaml]
    D -->|啟動 N 個| K[kiro-cli instances]
    D -->|啟動| API[api.py :13030]
    D -->|啟動| SCH[scheduler.py]

    K -->|stdio| MCP[team_mcp.py]
    MCP -->|HTTP| API
    SCH -->|HTTP /send| API
    API -->|stdin| K
    API -->|reply| TG
```

## 資料流

```
啟動：
  start.py / ark-team-agent team start
    → TeamManager.start()
    → Daemon.start_all()
      → config.load_config("team.yaml")
      → for each instance:
          backend.write_steering()     # 產出 .kiro/ 配置
          backend.write_mcp_config()   # 注入 MCP server
          backend.build_command()      # 組裝 kiro-cli 指令
          process.start(cmd, cwd)      # 啟動 subprocess
      → api.start(port=13030)          # FastAPI server
      → scheduler.start()              # APScheduler

Telegram 訊息處理：
  使用者 → TelegramAdapter._on_message
    → ChatRouter.route（@mention 解析）
    → SessionManager.get_or_create（上下文追蹤）
    → ConversationPlanner.plan（意圖路由）
    → Daemon.send_message（轉發到目標 Agent stdin）
    → Agent 處理 → MCP reply() → API → TelegramAdapter._flush_buffer

Agent 間通訊：
  Agent A 呼叫 MCP tool "send_to_instance"
    → team_mcp.py 收到 JSON-RPC request
    → HTTP POST http://localhost:13030/send/{target}
    → api.py 收到 → 寫入 target instance 的 stdin
    → target kiro-cli 處理並回覆

排程觸發：
  scheduler.py cron 到點
    → HTTP POST http://localhost:13030/send/{target}
    → 同上流程
```

## 與 ark-team-agent 的差異

| 維度 | ark-team-agent（成熟套件 v0.14） | Skill 產出（精簡版） |
|------|----------------------------------|---------------------|
| 安裝 | `pip install ark-team-agent` | 不需安裝，產出即用 |
| 啟動 | `ark-team-agent team start` | `python start.py` |
| 程式碼位置 | site-packages/ | 專案內 src/ |
| 模組數 | 37+（含 code_spec_validator 子套件） | 7 核心模組 |
| 依賴 | 9 runtime deps | 7 runtime deps |
| Telegram | 深度整合（session + router + reaction） | 基礎 @mention 路由 |
| MCP 工具 | 14 個 + rate limiter | 10 個 |
| Config | 12 dataclass | 3 dataclass |
| 角色層級 | admin / manager / leader / worker | admin / leader / worker |
| 風控 | cost_guard + failure_memory + event_log | 無 |
| 知識演化 | skill_growth + skill_extractor + wiki tools | 靜態知識庫 |
| 訊息持久 | 3 層佇列（queue + store + overflow） | 單層 queue |
| 行數 | ~6000 行 | ~1000 行 |
| 更新 | `pip install --upgrade` | 手動或重新產出 |

## 遷移路徑

```
Stage 0: Skill 產出（精簡版，7 模組）
  │
  ├── Stage 1: + Telegram 深度整合（session / router / planner）
  ├── Stage 2: + 監控風控（cost_guard / failure_memory / event_log）
  ├── Stage 3: + 知識演化（wiki_query / skill_growth / daily_summary）
  ├── Stage 4: 轉為 pip 套件（cli.py + setuptools entry_points）
  └── Stage 5: + Web 觀測面板（WebSocket + JSON logging + watchdog）
```

詳見 `references/migration-guide.md`。

## 擴充路徑（透過其他 Skill）

```
基礎系統（ark-agent-team-builder 產出）
  │
  ├── 加 .kiro/ 配置 → /ark-kiro-init
  ├── 加啟動程式 → /ark-team-runtime（已內建於 build_team.py）
  ├── 加工作流排程 → /ark-scheduler-generator
  ├── 加知識庫引擎 → /ark-wiki-engine
  ├── 加 Bot 聊天能力 → /ark-chatbot-generator
  ├── 加 Web Dashboard → /ark-html-dashboard
  └── 加 Docker 部署 → /ark-docker-deploy
```
