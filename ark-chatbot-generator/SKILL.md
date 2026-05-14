---
name: ark-chatbot-generator
description: |
  在既有 Web 專案上加入 Telegram Bot + LLM 對話能力 + Kiro CLI Agent 整合 + 呼叫 Skill 執行，可獨立運作。
  產出 Bot 模組（Gateway → Router → Planner → Execute → Respond）、
  KiroAdapter（獨立 Agent 後端）、GeminiAdapter LLM 整合、LLMRouter 統一路由、Session 對話管理。
  LLM 後端支援三層：Kiro CLI（獨立路徑）+ Gemini（預設主要）→ Ollama（備援）→ 靜態回應。
  業務 Skills 由獨立 Kiro Skill 產出，放入 internal/ 即可被 Bot 自然語言觸發。
  使用此 Skill 當使用者提及 ark chatbot、加入 Bot、Telegram Bot、
  gen bot chat、加入自然語言互動、Gemini Function Calling、Kiro MCP、
  或任何需要在既有專案上加入 Bot + LLM 整合的場景。
---

# ark-chatbot-generator

在既有 Web 專案上加入 Telegram Bot + LLM 對話能力 + Kiro CLI Agent 整合 + 呼叫 Skill 執行，可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「ark chatbot」、「加入 Bot」、「加入 Telegram Bot」
- 「gen bot chat」、「加入自然語言互動」
- 「Gemini Function Calling」、「加入 FC」
- 「Kiro MCP」、「kiro-cli」、「ask_kiro」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 既有專案目錄路徑 |
| `gemini_model` | `str` | ❌ | `"gemini-2.5-flash"` | 預設 Gemini 模型 |
| `llm_backend` | `str` | ❌ | `"gemini"` | LLM 後端優先順序（`"gemini"` / `"kiro"` / `"ollama"`） |

## 前置條件

- 專案目錄下存在 `src/skills/base.py` + `src/skills/registry.py`（Skill 插件系統）
- Kiro CLI 功能需要 `kiro-cli` 已安裝且已登入（可選，不影響其他功能）

## 產出指引

在 `{project_dir}/` 下新增 Bot 模組、LLM 整合（含 Kiro CLI Agent）、對話管理。
詳細架構見 `references/pipeline-spec.md`、`references/gemini-fc-guide.md`、`references/kiro-mcp-spec.md`。

---

### 步驟 1：建立目錄結構

```
{project_dir}/
├── src/
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── main.py           # Bot 入口（create_app + 指令註冊）
│   │   ├── handlers.py       # 訊息處理主流程 + 所有指令 handler
│   │   └── kiro_handlers.py  # Kiro CLI 操作 + Skill CodeGen 指令
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── adapter.py        # LLMAdapter（Gemini 主 + Ollama 備援）
│   │   ├── gemini_adapter.py # GeminiAdapter（FC 專用）
│   │   ├── kiro_adapter.py   # KiroAdapter（Kiro CLI Agent 後端）
│   │   ├── llm_router.py     # LLMRouter（統一路由 + fallback chain）
│   │   └── prompts.py        # Prompt 版本管理 + A/B 測試
│   ├── conversation/
│   │   ├── __init__.py
│   │   ├── session.py        # Session / Turn dataclass
│   │   ├── session_manager.py # SessionManager（生命週期 + SQLite 持久化）
│   │   ├── planner.py        # ConversationPlanner（LLM 意圖解析 + 五層參數填充）
│   │   ├── memory.py         # MemoryStore + MemoryExtractor（LLM 隱式提取）
│   │   └── progress.py       # ProgressReporter + TelegramProgressReporter
│   └── skills/
│       ├── base.py            # BaseSkill / SkillParam / SkillResult
│       ├── registry.py        # SkillRegistry（auto_discover）
│       ├── python_skills/     # Python Skills（echo, db_query, ...）
│       ├── llm_skills/        # LLM Skills（parse_intent, llm_qa, ...）
│       ├── wiki_skills/       # Wiki Skills（wiki_query, wiki_ingest, ...）
│       └── internal/          # 業務 Skills（auto_discover 掃描此目錄）
├── data/
│   ├── memory/                # 使用者記憶（per-user .md 檔案）
│   └── sessions.db            # Session 持久化 SQLite
├── prompts/                   # Prompt 模板（含 _meta.yaml 版本管理）
│   ├── intent_parse/
│   ├── param_extract/
│   └── memory_extract/
```

---

### 步驟 2：產出 Bot 模組

依賴注入模式：`init_components()` 在 `server/main.py` lifespan 中呼叫，
將 SessionManager、ConversationPlanner、MemoryStore 等元件注入 handlers。

#### 2a. `src/bot/handlers.py` — 訊息處理 + 指令 handler

**依賴注入**：使用模組層級全域變數 + `init_components()` 函式：

```python
_session_manager: SessionManager | None = None
_planner: ConversationPlanner | None = None
_memory_store: MemoryStore | None = None
_memory_extractor: MemoryExtractor | None = None
_workflow_engine: Any = None
_llm_adapter: Any = None
_skill_registry: Any = None

def init_components(
    session_manager, planner, memory_extractor, memory_store,
    workflow_engine=None, llm_adapter=None, skill_registry=None,
) -> None:
    """初始化共用元件（由 server/main.py lifespan 呼叫）。"""
    global _session_manager, _planner, ...
```

**handle_message 主流程**（自然語言訊息）：

```python
async def handle_message(update, context):
    # 0. 檢查 Kiro 寫入模式（pending_write）
    # 1. SessionManager.get_or_create(user_id) 取得 Session
    # 2. session.add_turn("user", text)
    # 3. ConversationPlanner.parse_intent(session) → LLM 意圖解析
    # 4. ConversationPlanner.plan(session, intent, memory) → ExecutionPlan
    # 5. 根據 PlanAction 分派：
    #    - CLARIFY → 發送釐清問題 + InlineKeyboard 選項
    #    - EXECUTE → 建立 TelegramProgressReporter → 執行工作流
    #    - ANSWER  → LLM 生成回答（含 Wiki context + 使用者記憶注入）
    #    - RESET   → 重置 Session
    #    - REMEMBER → 寫入記憶
    # 6. MemoryExtractor.extract() → InlineKeyboard 確認
```

**指令 handler**（10 個）：

| 指令 | Handler | 說明 |
|------|---------|------|
| `/start` | `cmd_start` | 歡迎訊息 |
| `/help` | `cmd_help` | 指令列表（含 Kiro 指令） |
| `/status` | `cmd_status` | 系統健康狀態（呼叫 health API） |
| `/skills` | `cmd_skills` | 列出已註冊 Skills |
| `/workflows` | `cmd_workflows` | 列出可用工作流 |
| `/run <id>` | `cmd_run` | 觸發工作流 |
| `/ask <問題>` | `cmd_ask` | 知識問答 |
| `/wiki <查詢>` | `cmd_wiki` | Wiki 查詢 |
| `/schedule` | `cmd_schedule` | 排程管理 |
| `/memory` | `cmd_memory` | 記憶管理 |

**handle_callback**：處理 InlineKeyboard 回調（參數選擇、記憶確認、Kiro 操作）。

#### 2b. `src/bot/kiro_handlers.py` — Kiro CLI 操作 + Skill CodeGen

詳見 `references/kiro-mcp-spec.md`。使用 `init_kiro()` 模組層級注入：

```python
_kiro: KiroAdapter | None = None

def init_kiro(kiro: KiroAdapter | None) -> None:
    """初始化 KiroAdapter（由 bot/main.py 呼叫）。"""
    global _kiro
    _kiro = kiro
```

**Kiro 指令**（13 個）：

| 指令 | Handler | 說明 |
|------|---------|------|
| `/ask_kiro <問題>` | `cmd_ask_kiro` | Kiro CLI 提問 |
| `/resume_kiro <問題>` | `cmd_resume_kiro` | 繼續 Kiro 對話 |
| `/kiro_sessions` | `cmd_kiro_sessions` | 列出 Kiro Session |
| `/read <路徑>` | `cmd_read` | 讀取檔案 |
| `/write <路徑>` | `cmd_write` | 寫入檔案（下一則訊息為內容） |
| `/ls [路徑]` | `cmd_ls` | 列出目錄 |
| `/rm <路徑>` | `cmd_rm` | 刪除檔案（InlineKeyboard 確認） |
| `/analyze <路徑> <指令>` | `cmd_analyze` | Kiro 分析檔案 |
| `/kiro_version` | `cmd_kiro_version` | Kiro CLI 版本 |
| `/kiro_doctor` | `cmd_kiro_doctor` | 系統診斷 |
| `/gen_skill <kiro> <id> [描述]` | `cmd_gen_skill` | 產出 Runtime Skill |
| `/list_kiro_skills` | `cmd_list_kiro_skills` | 列出可產出的 Kiro Skills |
| `/skill_status <id>` | `cmd_skill_status` | 檢查 Skill 狀態 |

所有 handler 先檢查 `KiroAdapter.is_available()`，不可用時回覆提示。
長文字回應自動分段（4000 字元上限）。

#### 2c. `src/bot/main.py` — Bot 入口

```python
def create_app():
    """建立 Telegram Bot Application。"""
    app = ApplicationBuilder().token(token).build()

    # 初始化 KiroAdapter（靜默失敗）
    _init_kiro_adapter()

    # 既有指令（10 個）
    app.add_handler(CommandHandler("start", cmd_start))
    # ... /help, /status, /skills, /workflows, /run, /ask, /wiki, /schedule, /memory

    # Kiro CLI 指令（11 個）
    app.add_handler(CommandHandler("ask_kiro", cmd_ask_kiro))
    # ... /resume_kiro, /kiro_sessions, /read, /write, /ls, /rm, /analyze,
    #     /kiro_version, /kiro_doctor, /cancel

    # Skill CodeGen 指令（3 個）
    app.add_handler(CommandHandler("gen_skill", cmd_gen_skill))
    app.add_handler(CommandHandler("list_kiro_skills", cmd_list_kiro_skills))
    app.add_handler(CommandHandler("skill_status", cmd_skill_status))

    # Callback + 自然語言 fallback
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
```

- `_init_kiro_adapter()` 靜默失敗，不影響 Bot 啟動
- 無 `TELEGRAM_BOT_TOKEN` 時 `create_app()` 拋出 ValueError，由呼叫端處理

---

### 步驟 3：產出 LLM 整合層

#### 3a. 產出 GeminiAdapter

產出 `src/llm/gemini_adapter.py`（不動既有 `adapter.py`）：

- `MODEL_TIERS`：`FAST="gemini-2.5-flash"`、`BALANCE="gemini-2.5-flash"`、`HEAVY="gemini-2.5-pro"`
- `generate(prompt, system, tier, temperature) -> dict`：一般文字生成
- `function_call(user_message, tools) -> dict`：Function Calling，回傳 `{"action": "call", "skill_id", "params"}` 或 `{"action": "reply", "text"}`
- `skills_to_tools(registry) -> list[dict]`：從 `to_tool_definition()` 自動產生 tool definitions，並清理 Gemini 不支援的 schema 欄位（`anyOf`、`title`、`additionalProperties`、`default`）
- 錯誤處理：API 失敗 → 記錄日誌 → 降級靜態回應

#### 3b. 產出 KiroAdapter

產出 `src/llm/kiro_adapter.py`，詳見 `references/kiro-mcp-spec.md`：

- 封裝 kiro-cli 所有操作（subprocess 非同步執行）
- `is_available()` — 檢查 kiro-cli 是否可用（結果快取）
- `ask(question)` — 向 Kiro CLI 提問（`kiro-cli chat --no-interactive`）
- `resume_chat(question, session_id)` — 繼續對話
- `file_read/write/list/delete` — 檔案操作（直接 pathlib，不經 kiro-cli）
- `analyze_file(path, instruction)` — 讓 Kiro 分析檔案
- `version/doctor/whoami` — 系統資訊
- `generate(prompt, system)` — LLM 相容介面，供 LLMRouter 呼叫
- 環境變數：`KIRO_CLI_CMD`、`KIRO_WORKSPACE`、`KIRO_CHAT_TIMEOUT`、`KIRO_FILE_TIMEOUT`

**注意**：KiroAdapter 延遲高（30-120 秒），不適合意圖分類或參數提取，
僅在使用者明確要求（`/ask_kiro`）或 `LLM_BACKEND=kiro` 時用於一般對話。

#### 3c. 產出 LLMRouter

產出 `src/llm/llm_router.py`，詳見 `references/kiro-mcp-spec.md`：

- 統一路由所有 LLM 呼叫，根據 `LLM_BACKEND` 環境變數決定優先順序
- `generate(prompt, system, tier)` — 自動 fallback 的文字生成
- `function_call(user_message, tools)` — FC 僅走 Gemini（Kiro/Ollama 不支援 FC）
- Fallback chain 建構邏輯：
  - `LLM_BACKEND=gemini`（預設）：Gemini → Ollama → 靜態
  - `LLM_BACKEND=kiro`：Kiro → Gemini → Ollama → 靜態
  - `LLM_BACKEND=ollama`：Ollama → Gemini → 靜態
- Kiro 指令（`/ask_kiro` 等）不經過 LLMRouter，直接走 KiroAdapter

---

### 步驟 4：產出對話管理

#### 4a. `src/conversation/session.py`

```python
from enum import Enum

class SessionState(Enum):
    IDLE = "idle"
    CLARIFYING = "clarifying"
    EXECUTING = "executing"

@dataclass
class Turn:
    turn_id: str
    role: str              # "user" | "assistant" | "system"
    content: str
    timestamp: datetime
    metadata: dict

@dataclass
class Session:
    session_id: str
    user_id: str
    turns: list[Turn]
    state: SessionState = SessionState.IDLE
    context: dict          # 跨輪次共享的上下文（如已選參數）
    clarify_count: int = 0
    max_clarify: int = 3
    created_at: datetime
    updated_at: datetime

    def add_turn(self, role: str, content: str, **metadata) -> Turn: ...
    def get_recent_turns(self, n: int = 10) -> list[Turn]: ...
```

#### 4b. `src/conversation/session_manager.py`

```python
class SessionManager:
    """Session 生命週期管理 + SQLite 持久化 + 使用頻率統計。"""

    def __init__(self, db_path: str = "data/sessions.db", ttl: int = 3600):
        self._sessions: dict[str, Session] = {}
        self.db_path = db_path
        self.ttl = ttl

    def get_or_create(self, user_id: str) -> Session: ...
    def reset_session(self, user_id: str) -> None: ...
    async def complete_session(self, user_id: str) -> None:
        """完成 Session → 非同步寫入 SQLite。"""
```

記憶體內 dict 儲存活躍 Session，完成/過期後非同步寫入 SQLite。

#### 4c. `src/conversation/planner.py`

```python
class PlanAction(Enum):
    EXECUTE = "execute"      # 參數充足 → 執行工作流
    CLARIFY = "clarify"      # 缺參數 → 詢問（InlineKeyboard）
    ANSWER = "answer"        # RAG 問答（LLM + Wiki context）
    RESET = "reset"          # 取消重來
    REMEMBER = "remember"    # 偵測偏好 → 確認 → 寫 memory

@dataclass
class ExecutionPlan:
    action: PlanAction
    workflow_id: str = ""
    params: dict = None
    clarify_question: str = ""
    clarify_options: list[str] = None
    answer_context: str = ""
    memory_key: str = ""
    memory_value: str = ""

class ConversationPlanner:
    """LLM 驅動的對話規劃器。"""

    def __init__(self, llm_adapter=None, memory_store=None): ...

    async def parse_intent(self, session: Session) -> dict:
        """LLM 意圖解析（帶入最近 5 輪對話歷史 + 使用者記憶）。
        降級：LLM 不可用時使用關鍵字比對。"""

    async def plan(self, session, intent, memory=None) -> ExecutionPlan:
        """五層參數填充：
        (1) 當前訊息提取 → (2) Session 上下文 → (3) 使用者記憶 →
        (4) YAML 預設值 → (5) 系統預設值
        充足 → EXECUTE，不足 → CLARIFY"""

    async def extract_params(self, session, missing_params) -> dict:
        """LLM 參數提取，降級為正則表達式。"""
```

#### 4d. `src/conversation/memory.py`

```python
class MemoryStore:
    """使用者記憶讀寫（per-user Markdown 檔案）。"""

    ALLOWED_FIELDS: set[str]  # 14 個白名單欄位

    def read(self, user_id: str) -> dict: ...
    def write(self, user_id: str, key: str, value: str) -> bool: ...

class MemoryExtractor:
    """LLM 隱式記憶提取：從對話中自動偵測使用者偏好。"""

    async def extract(self, session: Session, user_id: str) -> dict:
        """回傳 {key: value} 待確認的偏好。"""
```

#### 4e. `src/conversation/progress.py`

```python
class ProgressReporter:
    """收集並分發工作流進度事件。"""
    def step_start(self, step_id, index, total): ...
    def step_done(self, step_id, index, total, duration_ms): ...
    def complete(self, total_duration_ms): ...

class TelegramProgressReporter:
    """透過 edit_message_text 即時更新 Telegram 訊息。"""

    def __init__(self, bot, chat_id, message_id): ...

    async def handle_event(self, event: ProgressEvent) -> None:
        """處理進度事件，500ms 節流，LLM token 串流預覽。"""
```

- `TelegramProgressReporter` 在 `handle_message` 的 EXECUTE 分支中建立
- 透過 `edit_message_text` 即時更新步驟狀態
- 500ms 節流避免 Telegram API 速率限制

---

### 步驟 5：產出意圖分類 Skill（llm_parse_intent）

本地 LLM 優先的意圖分類，是 Router 層的核心依賴。

#### 必要性

- 本地優先架構：使用 Ollama 本地 LLM 進行意圖分類，不依賴外部 API
- Gemini FC 為備援：有 Gemini Key 時可用 FC 輔助，但核心路由不依賴雲端
- 離線可用：無外網環境仍可正常路由（keyword fallback 兜底）

#### 三層降級策略

```
本地 LLM（Ollama qwen3）→ Gemini FC（雲端備援）→ keyword fallback（離線兜底）
```

#### 產出 `src/skills/llm_skills/parse_intent.py`

```python
class ParseIntentSkill(BaseSkill):
    skill_id = "llm_parse_intent"
    skill_type = SkillType.LLM
    description = "使用 LLM 進行意圖分類 + 參數抽取（本地優先）"

    def __init__(self, llm: LLMAdapter | None = None) -> None:
        self._llm = llm or LLMAdapter(timeout=5.0)
```

#### 意圖清單（12 種）

| 意圖 | 說明 | 路由目標 |
|------|------|----------|
| query_kpi | 查詢 KPI 數據 | db_query / data_transform |
| query_revenue | 查詢營收 | db_query |
| query_general | 一般數據查詢 | db_query |
| rag_chat | 知識問答 | wiki_query + llm_qa |
| wiki_query | Wiki 知識查詢 | wiki_query |
| run_workflow | 執行工作流 | WorkflowEngine |
| schedule_manage | 排程管理 | ScheduleEngine |
| generate_report | 產出報表 | report_template |
| generate_doc | 產出文件 | file_export |
| memory_manage | 記憶管理 | MemoryStore |
| system_status | 系統狀態 | health API |
| unknown | 無法分類 | echo / Gemini chat |

#### keyword fallback

LLM 不可用時自動降級為關鍵字匹配：

```python
def _keyword_fallback(self, text: str) -> dict:
    mappings = [
        (["kpi", "指標", "dau"], "query_kpi"),
        (["營收", "revenue"], "query_revenue"),
        (["wiki", "知識"], "wiki_query"),
        (["排程", "schedule"], "schedule_manage"),
        (["報表", "report"], "generate_report"),
        ...
    ]
    # 匹配到 → confidence 0.6，未匹配 → rag_chat confidence 0.3
```

---

### 步驟 6：更新專案設定檔

#### 6a. 更新 `.env.example`

```bash
# ── Telegram Bot ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ALLOWED_USER_IDS=123456789,987654321

# ── LLM 後端設定 ─────────────────────────────────────────
# 一般對話的 LLM 後端優先順序
# gemini = Gemini 為主、Ollama 備援（推薦，低延遲）
# kiro   = Kiro CLI 為主（高延遲但最強，完整 agent 能力）
# ollama = Ollama 為主、Gemini 備援（離線環境）
LLM_BACKEND=gemini

# ── Gemini ───────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# ── Ollama（備援，預設關閉） ──────────────────────────────
OLLAMA_ENABLED=false

# ── Kiro CLI（獨立功能，不受 LLM_BACKEND 影響） ──────────
# kiro-cli 執行路徑（需在 PATH 中，或指定完整路徑）
KIRO_CLI_CMD=kiro-cli
# Kiro 預設工作目錄（Bot 操作檔案的根目錄）
KIRO_WORKSPACE=/your/workspace/path
# Kiro 對話超時（秒）— kiro-cli chat 可能需要較長時間
KIRO_CHAT_TIMEOUT=120
# 檔案操作超時（秒）
KIRO_FILE_TIMEOUT=30
```

#### 6b. 更新 `requirements.txt`

```
google-genai>=1.0.0
python-telegram-bot[ext]>=21.0
mcp>=1.2.0
```

---

### 步驟 7：驗證

確認所有新增檔案已產出且 Bot 可啟動：

```bash
python -m src.bot.main
```

---

## 擴充 Skills

產出的 Bot 骨架支援透過獨立 Kiro Skills 擴充功能。
新增 Skill 放入 `src/skills/internal/`，auto_discover 自動註冊，Bot 可透過自然語言或 `/invoke` 指令觸發。

## 整合模式

Bot 可獨立執行（`python -m src.bot.main`），也可整合進 webapp 的 `lifespan` 背景執行：

```python
# src/server/main.py lifespan 中
from src.bot.handlers import init_components
from src.bot.kiro_handlers import init_kiro
from src.llm.kiro_adapter import KiroAdapter

# 初始化對話系統元件
init_components(
    session_manager=session_manager,
    planner=planner,
    memory_extractor=memory_extractor,
    memory_store=memory_store,
    workflow_engine=workflow_engine,
    llm_adapter=llm_adapter,
    skill_registry=registry,
)

# 初始化 KiroAdapter
init_kiro(KiroAdapter())

# 啟動 Bot polling
bot_app = create_app()
await bot_app.initialize()
await bot_app.start()
await bot_app.updater.start_polling(drop_pending_updates=True)
```

整合時 Bot 與 Web 共用同一個 `SkillRegistry`、`SessionManager`、`MemoryStore`，
新增 Skill 兩邊同時生效。
無 `TELEGRAM_BOT_TOKEN` 時自動跳過，不影響 Web 服務。

## 注意事項

- 所有程式碼使用 Python 3.12 語法
- Docstring 使用繁體中文
- 路徑操作一律使用 `pathlib.Path`
- 所有 I/O 操作使用 `async/await`
- Skill 內部捕獲所有例外，不讓例外逃逸
- GeminiAdapter 獨立為 `gemini_adapter.py`，不覆蓋既有 `adapter.py`

### Web & Bot Chat 統一流程

產出 chatbot 時需同步更新 Web Chat 的 `src/server/api/chat.py`，使 Web 和 Bot 走相同流程：

1. `/skill_id` 指令 → 直接呼叫 Skill
2. Kiro 指令（`/ask_kiro` 等）→ 直接走 KiroAdapter（僅 Bot 端）
3. 一般訊息 → LLMRouter 路由（根據 `LLM_BACKEND` 決定後端）
4. 意圖分類 → 本地 LLM（Ollama）→ Gemini FC 備援 → keyword fallback
5. 都不可用 → keyword fallback → echo

## 踩坑紀錄

### GeminiAdapter 延遲初始化（2026-04-16）

`GeminiAdapter` 不能在模組層級實例化（`handlers.py` 的全域變數），因為此時 `load_dotenv()` 尚未執行，`GEMINI_API_KEY` 會是空字串。

- ❌ 錯誤：`gemini = GeminiAdapter()`（模組層級）
- ✅ 正確：延遲初始化函式 `_get_gemini()`，在第一次呼叫時才建立實例

### Gemini 模型可用性（2026-04-16）

`gemini-2.0-flash-lite` 部分 API 方案不支援（403 Forbidden）。
統一使用 `gemini-2.5-flash` 作為預設模型（FAST / BALANCE 都用）。

### Gemini Function Calling Schema 清理（2026-04-16）

Pydantic `model_json_schema()` 產出的 JSON Schema 包含 Gemini API 不支援的欄位（`anyOf`、`title`、`additionalProperties`、`default`、`$defs`），會導致 400 Bad Request。
`skills_to_tools()` 必須在傳送前清理這些欄位：
- `anyOf [str, null]` → 簡化為 `{"type": "string"}`
- 移除 `title`、`default`、`additionalProperties`

### httpx 日誌抑制（2026-04-17）

Telegram Bot polling 會大量輸出 `INFO:httpx:HTTP Request: POST .../getUpdates "HTTP/1.1 200 OK"`，淹沒有用的日誌。
在 `bot/main.py` 加入：

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
```

### KiroAdapter 可用性檢查（2026-04-24）

`KiroAdapter.is_available()` 結果快取，僅第一次呼叫時執行 `kiro-cli version`。
所有 Kiro 指令 handler 在執行前先檢查可用性，不可用時回覆提示訊息而非拋出例外。

- kiro-cli 未安裝 → `FileNotFoundError` → `_available = False`
- kiro-cli 未登入 → `returncode != 0` → `_available = False`
- kiro-cli 正常 → `_available = True`，記錄版本號

### KiroAdapter 不適合當 LLM fallback（2026-04-24）

kiro-cli chat 一次呼叫 30-120 秒（內部做多輪工具呼叫），不適合用於：
- 意圖分類（需要 <1 秒回應）
- 參數提取（需要快速回應）
- 一般閒聊（使用者期待秒級回應）

正確定位：獨立 Agent 後端，使用者明確要求時才走。
`LLM_BACKEND=kiro` 時一般對話也走 Kiro，但使用者需接受高延遲。
