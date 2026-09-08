---
name: ark-webapp-generator
description: |
  產出完整的「webbot」應用骨架 —— 一個 lifespan 一次啟動四層：
  FastAPI Server + Web Chat UI、BaseSkill 插件系統、WorkflowEngine + ScheduleEngine
  排程、Telegram Bot channel。三種可選規模：純 web / +排程 / +TG（三合一）。
  可獨立運作，支援 /skill_id 指令、workflow YAML、APScheduler 排程、TG 私聊路由。
  使用此 Skill 當使用者提及建立專案、產出 Web 應用、gen web app、ark webapp、
  webbot、web + bot、web 加 telegram、加入排程、排程引擎、工作流引擎、
  每日報表自動化、Telegram Bot 開發、加入 TG bot、
  或任何需要從零建構 FastAPI + Skill + 排程 + TG 的獨立應用場景。
  不適用於：① ark_bot_agent / ark_team_agent 的**消費端**（那用 ark-agent-bot-builder /
  ark-agent-team-builder，套件已內建 web/TG/排程）；② 純 TG 推播請用 ark-telegram-sender。
metadata:
  schema_version: 1
  status: active
  category: scaffolder
  depends_on: [ark-telegram-sender]
  outputs:
    - format: code
      audience: ai
  author: paddyyang
  version: "2.0"
  updated: 2026-09-08
---

# ark-webapp-generator

產出完整「webbot」應用骨架：**Web + Skill 插件 + 排程 + Telegram**，一個 lifespan 全啟動。

> **三合一紀錄**（v2.0，2026-09-08）：本 skill 併入原 `ark-telegram-bot`（TG 層）
> 與 `ark-scheduler-generator`（Workflow/Schedule 層）。三者本就設計成一個 webbot
> （webapp 的 lifespan 依序啟動 SkillRegistry → WorkflowEngine → ScheduleEngine →
> Telegram Bot），合併是正名。TG 慣例見 `references/telegram-integration.md`，
> 排程 schema 見 `references/{workflow,schedule}-yaml-schema.md`。
>
> 🔴 **定位**：本 skill 產出**獨立 FastAPI 應用**（自帶 web/排程/TG）。
> 若你要的是 `ark_bot_agent` / `ark_team_agent` 的消費端（那些套件已內建這些能力），
> 請用 `ark-agent-bot-builder` / `ark-agent-team-builder`。

## 規模選擇

| 規模 | 產出 | 觸發 |
|------|------|------|
| **純 web** | FastAPI + Web Chat UI + Skill 系統（步驟 1-7） | 「建立 web 專案」「gen web app」 |
| **+排程** | 加 WorkflowEngine + ScheduleEngine + workflow YAML | 「加入排程」「工作流引擎」 |
| **+TG（完整 webbot）** | 再加 Telegram adapter channel | 「webbot」「web 加 telegram」 |

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「建立專案」、「建立 Web 專案」、「gen web app」、「ark webapp」、「Workshop 專案」
- 「webbot」、「web + bot」、「web 加 telegram」、「產出 Web 應用」、「Web Chat」
- 「FastAPI + Skill 系統」
- 「加入排程」、「排程引擎」、「工作流引擎」、「Workflow Engine」、「每日報表自動化」、「APScheduler」
- 「Telegram Bot 開發」、「加入 TG bot」、「Bot channel」（獨立應用場景）

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_name` | `str` | ✅ | — | 專案名稱（用於建立根目錄） |
| `output_dir` | `str` | ❌ | `"./output"` | 輸出目錄路徑 |
| `scale` | `str` | ❌ | `"web"` | `web` / `web+schedule` / `webbot`（含 TG） |

## 產出指引

在 `{output_dir}/{project_name}/` 下產出完整專案檔案。
完整檔案清單見 `references/file-manifest.md`。

---

### 步驟 1：建立目錄結構

使用 `pathlib.Path` 建立所有必要目錄：

```
{output_dir}/{project_name}/
├── src/
│   ├── skills/
│   │   ├── internal/
│   │   ├── external/
│   │   └── marketplace/
│   └── server/
│       ├── core/
│       ├── api/
│       ├── models/
│       ├── templates/
│       └── static/
│           ├── css/
│           └── js/
└── tests/
```

---

### 步驟 2：產出 Skill 插件系統

遵循 `references/base-skill-spec.md` 中的 BaseSkill + SkillParam 介面規範。

產出以下檔案：

1. **`src/__init__.py`** — 頂層套件初始化
2. **`src/skills/__init__.py`** — 匯出 `BaseSkill`、`SkillResult`、`SkillRegistry`、`SkillType`、`SkillParam`
3. **`src/skills/base.py`** — 完整實作（SkillType、SkillParam、SkillResult、BaseSkill）
4. **`src/skills/registry.py`** — SkillRegistry（register / get / list_skills / invoke / auto_discover）
5. **`src/skills/internal/__init__.py`** — internal skills 套件初始化
6. **`src/skills/external/__init__.py`** — 外部整合 Skills 預留目錄
7. **`src/skills/marketplace/__init__.py`** — 社群可插拔 Skills 預留目錄

重要規範：
- `validate_params()` 無 `input_schema` 時回傳 `True`（向後相容）
- `auto_discover()` 只掃描直接子模組，不遞迴
- `invoke()` 中 `validate_params` 失敗回傳 `SkillResult(success=False, error="Invalid params for skill: {skill_id}")`
- Skill 執行例外由 `invoke()` 兜底捕獲

---

### 步驟 3：產出 FastAPI Server

1. **`src/server/__init__.py`** — server 套件初始化
2. **`src/server/main.py`** — FastAPI App 入口：
   - 使用 `lifespan` 初始化 `SkillRegistry`，啟動時 `auto_discover("src.skills.internal")`
   - 掛載 Jinja2 模板引擎、靜態檔案、API Router
   - 首頁路由使用新版 `TemplateResponse(request, "index.html")`（見踩坑紀錄）
3. **`src/server/core/config.py`** — Settings（python-dotenv）
4. **`src/server/core/errors.py`** — 自訂例外（AibiError、NotFoundError、ValidationError）
5. **`src/server/api/router.py`** — API Router 彙整（health、skills、chat）
6. **`src/server/api/health.py`** — `GET /api/v1/health`
7. **`src/server/api/skills.py`** — `GET /api/v1/skills` + `POST /api/v1/skills/invoke`
8. **`src/server/api/chat.py`** — `POST /api/v1/chat`（指令 → 呼叫 Skill，一般訊息 → Gemini FC 判斷 Skill / Gemini chat，無 API Key 時 echo）
9. **`src/server/models/slot_mechanics.py`** — SlotMechanics Pydantic 模型
10. **`src/server/models/vibe_score.py`** — VibeScore Pydantic 模型

---

### 步驟 4：產出 Web Chat UI

採用風格自動建議機制，搭配 `assets/style.css` 作為基礎樣式模板。

> **風格自動建議**（`theme: auto` 預設）：
> - 內部工具 / 開發者工具 / AI Chat → dark（暗黑科技風格）
> - 客戶面向 / 行銷 / 公開服務 → light（現代亮色風格）
> - 使用者可明確指定 `theme: "dark"` 或 `theme: "light"` 覆蓋

1. **`src/server/templates/base.html`** — Jinja2 基底模板：
   - HTML5 結構、meta viewport（響應式）
   - 引入 `static/css/style.css?v={版本號}`（cache busting）
2. **`src/server/templates/index.html`** — Web Chat UI 頁面：
   - 暗黑科技風格 header（dark 模式；light 模式改為白底深色文字）
   - 對話氣泡顯示區域（使用者藍色靠右、系統半透明深色靠左 + bot avatar）
   - 終端機風格輸入框 + EXECUTE 按鈕
   - 引入 `static/js/app.js?v={版本號}`
3. **`src/server/static/css/style.css`** — 依 theme 產出對應樣式：
   - CSS 變數 slate 色系 + cyan 強調色
   - 頂部漸層光條、對話氣泡、PROCESSING 打字指示器
   - 響應式佈局
4. **`src/server/static/js/app.js`** — 通用前端邏輯：
   - `fetch` 送出訊息到 `POST /api/v1/chat`
   - 通用渲染：物件 → JSON 格式化，字串 → 純文字換行
   - 有 Gemini API Key 時：一般訊息走 Gemini FC（判斷 Skill）/ Gemini chat
   - 無 Gemini API Key 時：一般訊息走 echo
   - EXECUTE 按鈕啟用/停用狀態切換
   - 自動捲動到最新訊息

注意：具體 Skill 的前端渲染（如遊戲卡片、數值規格卡片）由各 Skill 自行提供整合指引，
不在 webapp-generator 的產出範圍內。

---

### 步驟 5：產出最小範例 Skill（echo）

產出 `src/skills/internal/echo.py`：

```python
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

class EchoParams(SkillParam):
    """echo 輸入參數。"""
    message: str = "Hello"

class EchoSkill(BaseSkill):
    skill_id = "echo"
    skill_type = SkillType.PYTHON
    description = "回聲測試 — 回傳輸入訊息"
    version = "1.0.0"
    input_schema = EchoParams

    async def execute(self, params: dict) -> SkillResult:
        validated = EchoParams(**params)
        return SkillResult(success=True, data={"echo": validated.message})
```

此 Skill 用於驗證 Skill 系統運作正常（auto_discover → register → invoke）。
業務 Skill 可透過獨立 Kiro Skill 產出後放入 `src/skills/internal/`，auto_discover 自動註冊。

---

### 步驟 6：產出測試

1. **`tests/conftest.py`** — 共用 fixtures（FastAPI TestClient、mock SkillRegistry）
2. **`tests/test_health.py`** — `GET /api/v1/health` 回傳 200 + status 驗證
3. **`tests/test_skills.py`** — SkillRegistry register/get/list/invoke + BaseSkill 子類別測試

---

### 步驟 7：產出專案設定檔 + 驗證

1. **`requirements.txt`** — fastapi、uvicorn、jinja2、httpx、python-dotenv、pydantic、beautifulsoup4、pytest、pytest-asyncio、hypothesis、pytest-cov
2. **`.env.example`** — `HOST`、`PORT`、`DEBUG`
3. **`.gitignore`** — `.venv/`、`__pycache__/`、`.env`、`.pytest_cache/`、`artifacts/`
4. **`pytest.ini`** — `asyncio_mode = auto`、測試路徑 `tests/`
5. **`README.md`** — 專案說明、技術棧、快速開始、API 端點、專案結構

---

## 步驟 8：排程層（scale = web+schedule 或 webbot）

> 完整 schema 見 `references/workflow-yaml-schema.md` 與 `references/schedule-yaml-schema.md`。
> 腳本：`scripts/scaffold_scheduler.py`。

新增目錄與檔案：

```
src/workflow/{context.py, engine.py}      # RunContext + WorkflowEngine（skill/condition/loop/parallel）
src/scheduler/engine.py                   # ScheduleEngine（APScheduler，AsyncIOScheduler 與 FastAPI 共用 loop）
workflows/{hello,echo_loop,echo_condition}.yaml
workflows/schedules/morning_report.yaml   # cron 排程範例
src/server/api/{workflows,schedules}.py   # 觸發/列出/toggle API
```

- `template_render` skill（Workflow 步驟間的 Jinja2 膠水）放 `src/skills/internal/`
- `requirements.txt` 加 `apscheduler>=3.10.0`、`matplotlib>=3.8.0`
- 🔴 Workflow 模板解析：簡單引用（`{{ outputs.x }}`）直接取 Python 物件、
  複雜表達式走 Jinja2 後 `json.loads`、`${ENV_VAR}` 執行時替換（見 references）

## 步驟 9：Telegram 層（scale = webbot）

> 完整 TG API/UX 慣例見 `references/telegram-integration.md`。

- 產 `src/{package_name}/telegram_adapter.py`（polling + 私聊路由 + reply 出口 + rate limit）
- `.env` 加 `TELEGRAM_BOT_TOKEN`；`requirements.txt` 加 `python-telegram-bot[ext]>=21.0`
- lifespan 有 token 才啟動 Bot，無 token 自動跳過（web + 排程仍正常）
- 🔴 **TG 一律 polling，不需開 port**；最終回覆用新訊息而非就地編輯（編輯不發通知）

---

## 擴充 Skills

產出的專案骨架支援透過獨立 Kiro Skills 擴充功能。
新增 Skill 只需將 `.py` 檔案放入 `src/skills/internal/`，`auto_discover` 會自動掃描並註冊。
使用者即可透過 `/skill_id` 指令或 `POST /api/v1/skills/invoke` API 呼叫。

## 整合模式

webapp 的 `lifespan` 支援一次啟動所有服務，只需一個指令：

```bash
uvicorn src.server.main:app --reload --port 8000
```

在 `lifespan` 中依序初始化：
1. `SkillRegistry` — auto_discover 所有 internal Skills
2. `WorkflowEngine` — 載入 `workflows/*.yaml`
3. `ScheduleEngine` — 載入 `workflows/schedules/*.yaml` + 啟動 APScheduler
4. `Telegram Bot` — 背景執行 polling（有 `TELEGRAM_BOT_TOKEN` 時才啟動）

shutdown 時反向關閉：Bot → ScheduleEngine。

無 `TELEGRAM_BOT_TOKEN` 時自動跳過 Bot，Web + Schedule 仍正常運作。

## 注意事項

- 所有程式碼使用 Python 3.12 語法（`str | None` 而非 `Optional[str]`）
- Docstring 使用繁體中文
- 路徑操作一律使用 `pathlib.Path`
- 所有 I/O 操作使用 `async/await`
- Skill 內部捕獲所有例外，不讓例外逃逸

## 踩坑紀錄

### Jinja2 TemplateResponse API 變更（2026-04-16）

修改 CSS/JS 後瀏覽器可能使用快取版本（304 Not Modified）。
HTML 引用靜態檔案時加 `?v={版本號}` 做 cache busting。

---

## Workshop 引導（ai-bot-workshop）

本 Skill 對應 Workshop Step 1：建立 Web 專案骨架。

### 觸發提詞

```
建立 ai-bot Web 專案，專案名稱 my-news-bot
```

或帶自訂首頁：

```
建立 ai-bot Web 專案，首頁使用 quickstart.html
```

### 自訂首頁整合

當使用者指定首頁 HTML 檔案時：
1. 將指定的 HTML 複製到 `src/server/templates/index.html`
2. 保留原有 Chat UI 為 `/chat` 路由
3. 首頁 `/` 顯示使用者指定的 HTML

### 預期產出

產出後專案可直接啟動：

```bash
pip install -r requirements.txt
uvicorn src.server.main:app --reload --port 8000
```

瀏覽器開啟 `http://localhost:8000` 看到首頁。

### 下一步

完成後告訴 AI：`加入排程` 或 `加入 TG bot`（同一 skill 的更大 scale，見上方「規模選擇」）。
若要的是套件消費端（web/TG/排程已內建），改用 `ark-agent-bot-builder`。

### 卡關時

- `ModuleNotFoundError` → 執行 `pip install -r requirements.txt`
- port 被佔用 → 改用 `--port 8001`
- 首頁空白 → 確認 `templates/index.html` 存在
