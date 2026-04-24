---
name: ark-webapp-generator
description: |
  產出完整 Web 專案骨架，包含 FastAPI Server、Web Chat UI、BaseSkill 插件系統
  與 1 個最小範例 Skill（echo）。可獨立運作，支援 /skill_id 指令呼叫與 Skill 管理。
  後續可透過獨立 Kiro Skill 擴充業務功能。使用此 Skill 當使用者提及建立專案、
  產出 Web 應用、gen web app、ark webapp、
  或任何需要從零開始建構 FastAPI + Skill 系統的場景。
---

# ark-webapp-generator

產出完整 Web 專案骨架，包含 Skill 插件系統與 Web Chat UI，可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「建立專案」、「建立 Web 專案」
- 「gen web app」、「ark webapp」
- 「產出 Web 應用」、「Web Chat」
- 「FastAPI + Skill 系統」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_name` | `str` | ✅ | — | 專案名稱（用於建立根目錄） |
| `output_dir` | `str` | ❌ | `"./output"` | 輸出目錄路徑 |

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

採用暗黑科技風格，搭配 `assets/style.css` 作為基礎樣式模板。

1. **`src/server/templates/base.html`** — Jinja2 基底模板：
   - HTML5 結構、meta viewport（響應式）
   - 引入 `static/css/style.css?v={版本號}`（cache busting）
2. **`src/server/templates/index.html`** — Web Chat UI 頁面：
   - 暗黑科技風格 header（可自訂 SVG icon 機器人頭像 + 綠色狀態燈）
   - 對話氣泡顯示區域（使用者藍色靠右、系統半透明深色靠左 + bot avatar）
   - 終端機風格輸入框 + EXECUTE 按鈕
   - 引入 `static/js/app.js?v={版本號}`
3. **`src/server/static/css/style.css`** — 暗黑科技風格樣式：
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
