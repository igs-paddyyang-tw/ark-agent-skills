# Workshop 缺陷報告與補充注意事項

> 執行日期：2026-06-17
> 執行環境：Ubuntu 22.04 / Python 3.12.3 / kiro-cli 2.7.1

---

## 一、Builder Skill 缺少的程式碼

### 1. `ark_team_core` 核心模組未產出（Critical）

**問題**：`build_team.py` 的 `CORE_SOURCE` 指向 `projects/game-analytics-team/src/ark_team_core/`，若該路徑不存在（Workshop 學員環境必然不存在），fallback `_write_minimal_core()` 只產出 `__init__.py`，缺少以下 5 個必要模組：

| 缺少檔案 | 職責 | 行數 |
|----------|------|------|
| `config.py` | 讀取 team.yaml → TeamConfig / InstanceConfig dataclass | ~50 |
| `process.py` | 管理 kiro-cli 子程序啟停 | ~65 |
| `daemon.py` | CoreDaemon 主控（啟動/監控/關閉所有 agent） | ~60 |
| `mcp_registry.py` | MCP Tool 註冊表（ToolDefinition + McpRegistry） | ~25 |
| `scheduler.py` | 簡易 cron 排程器（讀 scheduler.yaml） | ~90 |

**影響**：`start.py` 直接 `from ark_team_core import CoreDaemon` 會 ImportError，團隊完全無法啟動。

**修正建議**：
- 方案 A（推薦）：在 `_write_minimal_core()` 中補上全部 5 個模組的產出邏輯
- 方案 B：將 ark_team_core 打包為獨立 pip 套件，`requirements.txt` 加入 `ark-team-core>=0.1.0`
- 方案 C：在 build_team.py 旁放一個 `ark_team_core/` 目錄作為 bundled source

### 2. TelegramAdapter 存取 `channel` 的方式不正確（Medium）

**問題**：`telegram_adapter.py` 第 31 行：
```python
self._bot_token = os.environ.get(self.config.channel.bot_token_env, "")
```

`self.config.channel` 是 `dict`（因為 TeamConfig 定義為 `channel: dict`），但用了屬性存取 `.bot_token_env`，導致 `AttributeError: 'dict' object has no attribute 'bot_token_env'`。

**修正**：
```python
_token_env = self.config.channel.get("bot_token_env", "TELEGRAM_BOT_TOKEN") if isinstance(self.config.channel, dict) else getattr(self.config.channel, "bot_token_env", "TELEGRAM_BOT_TOKEN")
self._bot_token = os.environ.get(_token_env, "")
```

**影響**：Telegram Adapter 無法啟動，Bot 無法接收訊息（但 HTTP API 仍正常）。

---

## 二、教學包需要補充的注意事項

### QUICKSTART.md 補充

#### 1. Python venv 必要性

Linux/Mac 系統（Ubuntu 22.04+）預設啟用 PEP 668（externally managed），直接 `pip install` 會被拒絕。教學包應明確指出：

```bash
cd my-team
python3 -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

**建議**：在 QUICKSTART.md Step 3 的「安裝依賴」段落改為含 venv 的完整指令。

#### 2. `start-team.sh` 使用錯誤的啟動指令

`start-team.sh` 內容為：
```bash
python3 -m ark_team_agent team start
```

但實際模組名為 `ark_team_core`，且沒有 CLI entry point。正確啟動方式是：
```bash
python3 start.py
```

**建議**：修正 `start-team.sh` 或在 build_team.py 中產出正確版本。

#### 3. 取得 User ID 的時機

QUICKSTART.md 只寫了「取得 Group ID」，但純私聊模式下需要取得個人 `user_id` 填入 `team.yaml` 的 `allowed_users`。流程應為：

1. 先對 Bot 私訊一則任意訊息
2. 呼叫 `getUpdates` API
3. 從 `result[0].message.from.id` 取得 user_id
4. 填入 team.yaml 的 `allowed_users` 和 admin-agent 的 `private_chat`

**建議**：新增「純私聊模式設定」子章節，明確說明。

#### 4. 環境變數 `ARK_TEAM_AGENT_HOME` 未說明

`start-team.sh` 引用此變數但未在 `.env.example` 或文件中說明。若學員在非專案目錄下執行 script 會找不到 `team.yaml`。

**建議**：`.env.example` 加入說明或移除此依賴。

#### 5. `--help` flag 的陷阱

`build_team.py` 沒有 argparse，任何參數都被當作 project name。`--help` 會產出一個名為 `--help` 的目錄。

**建議**：加入基本的 argparse 或至少在開頭檢查 `--help`/`-h`。

#### 6. `cost_guard` 提示不足

team.yaml 預設 `daily_limit_usd: 30.0`，但沒有說明 kiro-cli 的費用如何計算。Workshop 學員如果不知道模型消耗，可能會超出預期。

**建議**：在 QUICKSTART.md 末尾「常見問題」新增費用估算說明，例如：
- 4 agent 空跑（只啟動無任務）：~$0/hr
- 輕度派工（10 次對話/天）：~$2-5/天
- 重度派工（持續開發）：~$15-30/天

---

## 三、修正清單（Priority 排序）

| # | 嚴重度 | 項目 | 修正位置 |
|---|--------|------|----------|
| 1 | 🔴 Critical | ark_team_core 5 模組未產出 | `build_team.py` `_write_minimal_core()` |
| 2 | 🟡 Medium | TelegramAdapter dict 存取 bug | `telegram_adapter.py` template |
| 3 | 🟡 Medium | start-team.sh 指令錯誤 | `build_team.py` `_write_start_team_sh()` |
| 4 | 🟢 Low | venv 步驟缺失 | QUICKSTART.md Step 3 |
| 5 | 🟢 Low | 純私聊模式 user_id 流程 | QUICKSTART.md Step 3 |
| 6 | 🟢 Low | build_team.py 無 --help | `build_team.py` |

---

## 四、本次手動修復記錄

以下是本次 Workshop 執行中手動補上的檔案，可作為修正 `_write_minimal_core()` 的參考：

- `my-team/src/ark_team_core/config.py` — 51 行
- `my-team/src/ark_team_core/process.py` — 64 行
- `my-team/src/ark_team_core/daemon.py` — 56 行
- `my-team/src/ark_team_core/mcp_registry.py` — 23 行
- `my-team/src/ark_team_core/scheduler.py` — 88 行

總計 282 行，符合原始規格「< 1000 行」的設計目標。

---

## 五、Session 管理與上下文壓縮建議

### 變更：`skip_resume` 預設改為 `false`

所有 agent 的 `skip_resume` 已從 `true` 改為 `false`，效果：
- 每個 agent 啟動時會自動恢復上一次 session（保留對話歷史與任務上下文）
- agent 重啟後不會「失憶」，能繼續未完成的任務
- 適合長時間運作的團隊（跨日任務、迭代開發）

### 上下文壓縮（Context Compaction）建議

kiro-cli 的 context window 有限（依模型 128K-200K tokens），長 session 必然觸發自動壓縮。以下是建議的壓縮觸發百分比：

| Agent 角色 | 建議觸發點 | 理由 |
|------------|-----------|------|
| admin-agent | **85%** | 主要做監控/簡短指令，歷史可大量丟棄 |
| pm-agent (leader) | **70%** | 需保留任務拆解、派工記錄、驗收標準，壓縮要早觸發以保留關鍵決策 |
| dev-agent (worker) | **75%** | 需保留當前任務的程式碼上下文，但舊的完成任務可壓縮 |
| qa-agent (worker) | **75%** | 需保留測試結果與 bug 記錄，舊通過的測試可壓縮 |

### 為什麼 Leader 要最早觸發（70%）？

Leader (pm-agent) 的上下文最珍貴：
- 包含團隊派工的完整決策鏈（誰做什麼、為什麼這樣分配）
- 包含需求澄清的對話歷史
- 包含驗收標準定義

如果等到 85% 才壓縮，可能已經來不及保留關鍵資訊。70% 觸發讓系統有更多空間做摘要式保留。

### 壓縮策略

建議在各 agent 的 `.kiro/steering/KIRO.md` 中加入：

```markdown
## Context Management

- 上下文使用超過 {百分比} 時自動觸發壓縮
- 壓縮時保留：當前未完成任務、最近 5 輪對話、關鍵決策記錄
- 壓縮時丟棄：已完成任務的詳細對話、重複的系統訊息、舊的 tool 輸出
- 壓縮後產出摘要寫入 MEMORY.md 做持久化
```

### team.yaml 建議新增欄位

```yaml
defaults:
  backend: kiro-cli
  model: auto
  skip_resume: false
  context_compaction:
    pm-agent: 70      # leader 最早觸發
    dev-agent: 75     # worker 標準
    qa-agent: 75      # worker 標準
    admin-agent: 85   # admin 最晚觸發
```

> 注意：此欄位為建議規格，需 ark_team_core 支援後才生效。目前 kiro-cli 的壓縮由框架自動處理，百分比由模型 context window 決定。

---

## 六、5 人 AI 團隊配置

### 角色定義

| # | Instance | Role | 職責範圍 | 上下文壓縮 |
|---|----------|------|----------|-----------|
| 1 | admin-agent | admin | 服務監控、重啟、成本控制、系統健康 | 85% |
| 2 | pm-agent | leader | 需求分析、任務拆解、派工、驗收、進度追蹤 | 70% |
| 3 | ai-dev-agent | worker | AI/ML 架構、Prompt 工程、Agent 設計、LLM 整合 | 75% |
| 4 | coder-agent | worker | 全端開發、API 實作、程式碼產出、重構 | 75% |
| 5 | qa-agent | worker | 測試撰寫、品質保證、Code Review、Bug 回報 | 75% |

### 角色分工（ai-dev vs coder）

| 面向 | ai-dev-agent | coder-agent |
|------|-------------|-------------|
| 核心能力 | AI 系統設計、Prompt 調優、RAG 架構 | 傳統軟體開發、API、資料庫、前端 |
| 輸出物 | Prompt 模板、Agent 流程圖、LLM 整合方案 | 可執行程式碼、API 端點、測試 |
| 工具 | LLM API、向量資料庫、Embedding | 框架（FastAPI/Express）、ORM、Docker |
| 派工範例 | 「設計 RAG pipeline」「優化 system prompt」 | 「建立 REST API」「實作登入功能」 |

### 協作流程

```
使用者 → pm-agent（leader）
              ├─ AI 相關任務 → ai-dev-agent
              ├─ 開發任務 → coder-agent
              ├─ 測試任務 → qa-agent
              └─ 系統問題 → admin-agent
```

### team.yaml 配置

```yaml
instances:
  admin-agent:
    working_directory: "."
    description: "⚙️ Admin — 服務監控、重啟、成本控制"
    private_chat: 937896656
    role: admin
    skip_resume: false

  pm-agent:
    working_directory: agents/pm-agent
    description: "🧠 Leader — 需求分析、派工、驗收"
    role: leader
    skip_resume: false

  ai-dev-agent:
    working_directory: agents/ai-dev-agent
    description: "🤖 AI Dev — AI/ML 架構、Prompt 工程、Agent 設計"
    role: worker
    skip_resume: false

  coder-agent:
    working_directory: agents/coder-agent
    description: "💻 Coder — 全端開發、API 實作、程式碼產出"
    role: worker
    skip_resume: false

  qa-agent:
    working_directory: agents/qa-agent
    description: "🧪 QA — 測試、品質保證、Code Review"
    role: worker
    skip_resume: false
```

### 派工範例

```
@leader 規劃一個 RAG 知識庫系統，需要 AI 架構設計 + 後端 API + 測試
```

Leader 預期拆解：
1. ai-dev-agent → 設計 RAG pipeline 架構、選擇 Embedding 模型、定義 Prompt
2. coder-agent → 實作 FastAPI 端點、向量資料庫整合、前端搜尋 UI
3. qa-agent → 撰寫整合測試、驗證搜尋品質、回報 edge case

---

## 七、build_team.py 修正記錄（2026-06-17）

### 修正內容

| # | 修正 | 檔案 |
|---|------|------|
| 1 | team.yaml 模板改為 5 人（admin + pm + ai-dev + coder + qa） | `build_team.py` L190-220 |
| 2 | `dev-agent` → `coder-agent`，新增 `ai-dev-agent` | `build_team.py` L190-220 |
| 3 | `skip_resume` 預設值改為 `false` | `build_team.py` L190-220 |
| 4 | `_write_minimal_core()` 補上 5 個完整模組產出 | `build_team.py` L865+ |

### 驗證結果

```
✅ 產出 5 人 team.yaml（admin-agent, pm-agent, ai-dev-agent, coder-agent, qa-agent）
✅ ark_team_core/ 產出 6 個 .py（__init__ + config + process + daemon + mcp_registry + scheduler）
✅ import 成功：from ark_team_core import CoreDaemon, AgentProcess, TeamConfig
✅ load_config('team.yaml') 正確解析 5 個 instances
```

### 修正前後對比

```diff
- instances: 4 人（admin + pm + dev + qa）
+ instances: 5 人（admin + pm + ai-dev + coder + qa）

- skip_resume: true（每次啟動都是新 session）
+ skip_resume: false（保留 session，支持長時任務）

- _write_minimal_core(): 只產 __init__.py（殘缺）
+ _write_minimal_core(): 產出完整 5 模組（282 行）
```
