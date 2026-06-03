---
author: paddyyang
name: ark-ai-bot-builder
description: |
  快速產出完整 AI Agent Bot Workspace（1~6 階段漸進式）。
  掛載 Agent CLI（Gemini/Kiro/Claude）為大腦，透過 Telegram 自然語言對話讓 Bot 做事。
  參考 ninja-bot 架構：BaseSkill 插件系統 + ConversationPlanner 意圖路由 +
  LLMRouter fallback chain + AgentOrchestrator 自進化 + MemorySearch 跨 Session 記憶。
  使用此 Skill 當使用者提及 ai-bot-builder、建立 AI Bot、產出 Bot workspace、
  快速建 Agent Bot、或任何需要從零建構 Telegram AI Agent Bot 的場景。
---

# ark-ai-bot-builder — One Pager 執行計畫

> 快速產出 AI Agent Bot Workspace，6 階段漸進式建構，掛載 Agent CLI 用自然語言對話讓 Bot 做事。

## 目標

一鍵產出可運行的 AI Agent Bot 專案，架構源自 ninja-bot 實戰驗證：
- **Telegram Bot** 作為使用者入口
- **Agent CLI**（Gemini/Kiro/Claude）作為 AI 大腦
- **BaseSkill 插件系統** 支援動態擴充
- **自然語言對話** → 意圖路由 → 自動執行任務

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「ark-ai-bot-builder」、「建立 AI Bot」、「產出 Bot workspace」
- 「快速建 Agent Bot」、「ai-workspace」
- 「gen ai bot」、「建立 Telegram Agent」
- 「新 Bot 專案」、「從零建 Bot」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_name` | `str` | ✅ | — | 專案名稱（用於建立根目錄） |
| `output_dir` | `str` | ❌ | `"./output"` | 輸出目錄路徑 |
| `stages` | `str` | ❌ | `"1-6"` | 要產出的階段範圍（如 `"1-3"` 只產基礎） |
| `llm_backend` | `str` | ❌ | `"gemini"` | 預設 LLM 後端（gemini/kiro/claude） |
| `bot_name` | `str` | ❌ | `project_name` | Bot 顯示名稱 |

## 架構概覽（參考 ninja-bot）

```
{project_name}/
├── src/
│   ├── skills/           # BaseSkill 插件系統
│   │   ├── base.py       # BaseSkill / SkillParam / SkillResult
│   │   ├── registry.py   # SkillRegistry（auto_discover + hot_reload）
│   │   ├── tracker.py    # 執行統計 + 自我改進
│   │   └── internal/     # 所有 Skill 放這裡
│   ├── bot/              # Telegram Bot
│   │   ├── main.py       # 入口（create_app）
│   │   ├── handlers.py   # 指令 + 自然語言路由
│   │   └── permissions.py # 權限管理
│   ├── llm/              # LLM 整合
│   │   ├── gemini_adapter.py  # Gemini API
│   │   ├── llm_router.py     # 統一路由 + fallback
│   │   └── gemini_chat.py    # 輕量即時對話
│   ├── conversation/     # 對話系統
│   │   ├── planner.py        # 意圖路由（keyword + LLM）
│   │   ├── session.py        # Session / Turn
│   │   ├── session_manager.py # SQLite 持久化
│   │   ├── memory.py         # 使用者記憶
│   │   └── memory_search.py  # FTS5 跨 Session 搜尋
│   ├── agent/            # Agent 自進化
│   │   ├── orchestrator.py   # 四階段流程（evaluate → generate → execute → deliver）
│   │   └── delivery.py       # 結果交付
│   └── server/           # FastAPI（可選）
│       └── main.py
├── config/
│   ├── telegram.json     # 白名單 + 群組設定
│   └── llm_prompts.yaml  # LLM 系統提詞（外部化）
├── data/                 # 執行期資料
├── .env.example
├── requirements.txt
└── README.md
```

---

## 六階段漸進式產出

### Stage 1：Skill 插件系統（骨架）

**產出檔案：**
- `src/__init__.py`
- `src/skills/__init__.py`
- `src/skills/base.py` — BaseSkill / SkillParam / SkillResult / SkillType
- `src/skills/registry.py` — SkillRegistry（register / invoke / auto_discover / hot_reload）
- `src/skills/internal/__init__.py`
- `src/skills/internal/echo.py` — 回聲測試 Skill

**核心介面（源自 ninja-bot）：**

```python
class BaseSkill(ABC):
    skill_id: str = ""
    skill_type: SkillType = SkillType.PYTHON
    description: str = ""
    version: str = "1.0.0"
    input_schema: type[SkillParam] | None = None

    @abstractmethod
    async def execute(self, params: dict) -> SkillResult: ...

class SkillRegistry:
    def register(self, skill: BaseSkill) -> None: ...
    async def invoke(self, skill_id: str, params: dict) -> SkillResult: ...
    def auto_discover(self, package_name: str) -> int: ...
    def hot_reload(self, skill_id: str) -> bool: ...
```

**驗證：** `pytest tests/test_skills.py` — register / invoke / auto_discover 正常

---

### Stage 2：LLM 整合層（Agent CLI 大腦）

**產出檔案：**
- `src/llm/__init__.py`
- `src/llm/gemini_adapter.py` — Gemini API 封裝（generate + available 檢查）
- `src/llm/gemini_chat.py` — 輕量即時對話（單輪 API 呼叫）
- `src/llm/llm_router.py` — 統一路由 + fallback chain
- `src/skills/internal/llm_cli.py` — Agent CLI Skill（多後端 + 多模式）

**LLMRouter fallback chain（源自 ninja-bot）：**

```
Gemini API → Gemini CLI → Kiro CLI → Claude CLI → 靜態回應
```

**llm_cli Skill 模式：**

| 模式 | 說明 | 用途 |
|------|------|------|
| `chat` | 一般對話 | 自然語言回答 |
| `codegen` | 程式碼產出 | 產出 .py 檔案 |
| `evaluate` | 意圖判斷 | Planner 呼叫，回傳 JSON |
| `skill_gen` | Skill 產出 | 自進化用，產出完整 BaseSkill |

**CLI subprocess 重點（踩坑經驗）：**
- Windows 使用 `create_subprocess_shell`（.cmd 相容）
- 有 stdout 就視為成功（CLI stderr 警告不誤判）
- cwd 設為 `AI_BOT_WORKSPACE` 確保路徑正確
- timeout 預設 60s（agent 模式 120s）

**驗證：** `pytest tests/test_llm.py` — generate / fallback 正常

---

### Stage 3：對話系統（意圖路由 + 記憶）

**產出檔案：**
- `src/conversation/__init__.py`
- `src/conversation/session.py` — Session / Turn / SessionState dataclass
- `src/conversation/session_manager.py` — SQLite 持久化 + TTL 過期
- `src/conversation/planner.py` — ConversationPlanner（三層降級）
- `src/conversation/memory.py` — MemoryStore（per-user MD）
- `src/conversation/memory_search.py` — FTS5 跨 Session 全文搜尋

**ConversationPlanner 三層降級（源自 ninja-bot）：**

```
1. keyword 快速路由（毫秒級，短路 LLM）
2. LLM 意圖解析（llm_cli evaluate 模式）
3. keyword fallback（離線兜底）
```

**PlanAction 路由結果：**

| Action | 說明 | 目標 |
|--------|------|------|
| EXECUTE | 參數充足 | → SkillRegistry.invoke() |
| ANSWER | 一般問答 | → LLMRouter.generate() |
| CLARIFY | 缺參數 | → 追問使用者 |
| RESET | 重置 | → Session 清除 |

**MemorySearch 跨 Session 記憶（源自 ninja-bot）：**
- SQLite FTS5 索引所有對話
- LLM 回答前自動召回相關歷史
- 格式化為 `[歷史回憶]` 注入 system prompt

**驗證：** `pytest tests/test_conversation.py` — planner / session / memory 正常

---

### Stage 4：Telegram Bot（入口 + 指令）

**產出檔案：**
- `src/bot/__init__.py`
- `src/bot/main.py` — create_app + graceful shutdown
- `src/bot/handlers.py` — 指令 handlers + handle_message 主流程
- `src/bot/permissions.py` — 白名單權限（支援巢狀 JSON）
- `config/telegram.json` — 白名單設定

**handle_message 主流程（源自 ninja-bot）：**

```python
async def handle_message(update, context):
    # 群組：@mention 才回話，否則只記錄到 FTS5
    # 私訊：白名單檢查
    # 1. Session 管理
    # 2. Agent CLI 模式 → 直接走 CLI（跳過 Planner）
    # 3. API 模式 → Planner 意圖解析
    # 4. 根據 PlanAction 分派：RESET / EXECUTE / ANSWER / CLARIFY
    # 5. 記憶召回注入 + 使用者建模
```

**雙模式切換：**

| 模式 | 指令 | 延遲 | 能力 |
|------|------|------|------|
| API | `/llm` | 1-5 秒 | Gemini API 即時對話 |
| Agent CLI | `/agent` | 30-120 秒 | 完整 Agent 能力（codegen / research） |

**基礎指令（10 個）：**
`/start` `/help` `/status` `/skills` `/reset` `/chat` `/mode` `/llm` `/agent` `/cost`

**驗證：** Bot 可啟動（`python -m src.bot.main`）+ 基本對話正常

---

### Stage 5：Agent 自進化（動態產出 Skill）

**產出檔案：**
- `src/agent/__init__.py`
- `src/agent/orchestrator.py` — 四階段流程控制
- `src/agent/delivery.py` — 結果交付（文字/檔案分段）
- `src/skills/tracker.py` — 執行統計 + 失敗偵測

**AgentOrchestrator 四階段（源自 ninja-bot）：**

```
Phase 1: evaluate   → LLM 判斷：直接回答 / invoke 已有 Skill / 產出新 Skill
Phase 2: generate   → llm_cli skill_gen 模式產出 .py
Phase 3: execute    → hot_reload + invoke
Phase 4: deliver    → 回傳結果到 Telegram
```

**SkillTracker 自我改進：**
- 連續失敗 ≥ 3 次 → 標記需要進化
- 失敗率 > 30% → 觸發重新產出
- 統計持久化到 `data/skill_stats.json`

**驗證：** `pytest tests/test_agent.py` — evaluate / generate / hot_reload 正常

---

### Stage 6：進階功能（排程 + Workflow + 完善）

**產出檔案：**
- `src/scheduler/__init__.py`
- `src/scheduler/engine.py` — ScheduleEngine（APScheduler 動態 CRUD）
- `src/workflow/__init__.py`
- `src/workflow/engine.py` — WorkflowEngine（YAML 工作流）
- `src/conversation/user_profiler.py` — LLM 自動萃取使用者偏好
- `src/server/main.py` — FastAPI + lifespan 整合
- `config/llm_prompts.yaml` — LLM 系統提詞（外部化）

**WorkflowEngine YAML 工作流：**

```yaml
id: daily_report
steps:
  - id: fetch
    skill: news_scraper
    params:
      sources: "${NEWS_SOURCES}"
  - id: render
    skill: news_renderer
    params:
      articles: "{{ outputs.fetch.articles }}"
```

**ScheduleEngine 動態 CRUD：**
- `add_schedule()` / `update_schedule()` / `remove_schedule()`
- 靜態（YAML）+ 動態（JSON）排程共存
- `run_now()` 支援手動觸發

**UserProfiler：**
- 每 10 輪對話觸發一次 LLM 建模
- 自動萃取偏好寫入 MemoryStore
- 靜默失敗不影響對話

**驗證：** 全部 `pytest tests/ -q` 通過

---

## 產出設定檔

### `.env.example`

```bash
# ── Telegram Bot ──
TELEGRAM_BOT_TOKEN=your_token

# ── LLM 後端 ──
LLM_BACKEND=gemini          # gemini / kiro / claude
GEMINI_API_KEY=your_key
GEMINI_CLI_CMD=gemini.cmd   # Windows: gemini.cmd / Linux: gemini

# ── Agent 工作目錄 ──
AI_BOT_WORKSPACE=.          # CLI subprocess 的 cwd
```

### `requirements.txt`

```
python-telegram-bot[ext]>=21.0
google-genai>=1.0.0
pydantic>=2.0.0
httpx>=0.27.0
pyyaml>=6.0.0
python-dotenv>=1.0.0
apscheduler>=3.10.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

---

## 驗收條件

| # | 條件 | 驗證方式 |
|---|------|----------|
| 1 | Skill 系統可用 | echo Skill invoke 成功 |
| 2 | LLM 對話可用 | Gemini API 或 CLI 回答正常 |
| 3 | 意圖路由正確 | keyword + LLM 兩層都能路由 |
| 4 | Bot 可啟動 | `python -m src.bot.main` 不報錯 |
| 5 | 自然語言觸發 Skill | 對話「echo hello」→ 呼叫 echo Skill |
| 6 | Agent CLI 模式 | `/agent` 切換後 CLI 回答正常 |
| 7 | 自進化 | 「幫我寫一個 XXX Skill」→ 產出 + hot_reload |
| 8 | 記憶持久化 | 重啟後歷史對話可搜尋 |
| 9 | pytest 全過 | `pytest tests/ -q` exit code 0 |

---

## 使用方式

```bash
# 觸發產出
「ark-ai-bot-builder，專案名稱 my-agent-bot」

# 只產出前 3 階段（Skill + LLM + 對話）
「ark-ai-bot-builder，專案名稱 my-bot，stages 1-3」

# 產出後啟動
cd output/my-agent-bot
cp .env.example .env
# 填入 TELEGRAM_BOT_TOKEN + GEMINI_API_KEY
pip install -r requirements.txt
python -m src.bot.main
```

---

## 與 ninja-bot 的差異

| 項目 | ninja-bot（完整版） | ark-ai-bot-builder（骨架） |
|------|---------------------|---------------------------|
| Skills | 12 個業務 Skill | 2 個基礎（echo + llm_cli） |
| LLM | Hermes + Gemini + CLI | Gemini + CLI（精簡版） |
| 新聞日報 | 完整 pipeline | 不含（用獨立 Skill 擴充） |
| Workflow | 已有多個定義 | 引擎 + 範例模板 |
| 測試 | 101 passed | ~30 基礎測試 |
| 文件 | 完整文件 | README + .env.example |

**設計哲學：** 產出最小可運行骨架，業務邏輯透過獨立 Skill 漸進式擴充。

---

## 注意事項

- Python 3.12 語法（`str | None`、`match`、`type[X]`）
- 所有 I/O 使用 `async/await`
- Docstring 繁體中文
- 路徑操作用 `pathlib.Path`
- Token 從環境變數讀取，不硬編碼
- Skill 內部捕獲所有例外，不逃逸
- Windows / Linux 雙平台相容（CLI subprocess）
