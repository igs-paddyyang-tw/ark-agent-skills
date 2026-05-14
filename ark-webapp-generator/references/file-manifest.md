# ark-webapp-generator 產出檔案清單

> 本文件列出 `ark-webapp-generator`（Phase 1）在目標目錄 `{output_dir}/{project_name}/` 下產出的完整檔案結構。
> 驗證腳本 `scripts/validate_output.py` 依據此清單檢查產出完整性。

---

## 檔案結構總覽

```
{output_dir}/{project_name}/
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
│
├── src/
│   ├── __init__.py
│   │
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseSkill + SkillParam + SkillResult + SkillType
│   │   ├── registry.py                # SkillRegistry
│   │   ├── internal/
│   │   │   ├── __init__.py
│   │   │   └── echo.py                # 最小範例 Skill（EchoParams）
│   │   ├── external/
│   │   │   └── __init__.py
│   │   └── marketplace/
│   │       └── __init__.py
│   │
│   └── server/
│       ├── __init__.py
│       ├── main.py                    # FastAPI App 入口 + lifespan
│       ├── core/
│       │   ├── config.py              # Settings（python-dotenv）
│       │   └── errors.py              # 自訂例外類別
│       ├── api/
│       │   ├── router.py              # API Router 彙整
│       │   ├── health.py              # GET /api/v1/health
│       │   ├── skills.py              # GET /api/v1/skills + POST /api/v1/skills/invoke
│       │   └── chat.py                # POST /api/v1/chat
│       ├── models/
│       │   ├── slot_mechanics.py      # SlotMechanics Pydantic 模型
│       │   └── vibe_score.py          # VibeScore Pydantic 模型
│       ├── templates/
│       │   ├── base.html              # Jinja2 基底模板
│       │   └── index.html             # Web Chat UI
│       └── static/
│           ├── css/
│           │   └── style.css          # 暗黑科技風格樣式
│           └── js/
│               └── app.js             # 通用前端邏輯
│
└── tests/
    ├── conftest.py
    ├── test_health.py
    └── test_skills.py
```

---

## 依分類

### 專案設定檔（4）

| 檔案路徑 | 說明 |
|----------|------|
| `requirements.txt` | Python 依賴 |
| `.env.example` | 環境變數範本 |
| `.gitignore` | Git 忽略規則 |
| `pytest.ini` | pytest 設定 |

### Skill 插件系統（8）

| 檔案路徑 | 說明 |
|----------|------|
| `src/__init__.py` | 頂層套件初始化 |
| `src/skills/__init__.py` | 匯出 BaseSkill、SkillResult、SkillRegistry |
| `src/skills/base.py` | BaseSkill ABC + SkillParam + SkillResult + SkillType |
| `src/skills/registry.py` | SkillRegistry（register / get / list_skills / invoke / auto_discover） |
| `src/skills/internal/__init__.py` | internal skills 套件初始化 |
| `src/skills/internal/echo.py` | 最小範例 Skill（驗證系統運作） |
| `src/skills/external/__init__.py` | 外部整合 Skills 預留目錄 |
| `src/skills/marketplace/__init__.py` | 社群可插拔 Skills 預留目錄 |

### FastAPI Server（10）

| 檔案路徑 | 說明 |
|----------|------|
| `src/server/__init__.py` | server 套件初始化 |
| `src/server/main.py` | FastAPI App 入口 + lifespan |
| `src/server/core/config.py` | Settings（python-dotenv） |
| `src/server/core/errors.py` | 自訂例外 + exception handler |
| `src/server/api/router.py` | API Router 彙整 |
| `src/server/api/health.py` | `GET /api/v1/health` |
| `src/server/api/skills.py` | `GET /api/v1/skills` + `POST /api/v1/skills/invoke` |
| `src/server/api/chat.py` | `POST /api/v1/chat`（通用指令解析） |
| `src/server/models/slot_mechanics.py` | SlotMechanics Pydantic 模型 |
| `src/server/models/vibe_score.py` | VibeScore Pydantic 模型 |

### Web Chat UI（4）

| 檔案路徑 | 說明 |
|----------|------|
| `src/server/templates/base.html` | Jinja2 基底模板 |
| `src/server/templates/index.html` | Web Chat UI 頁面 |
| `src/server/static/css/style.css` | 暗黑科技風格樣式 |
| `src/server/static/js/app.js` | 通用前端邏輯 |

### 測試（3）

| 檔案路徑 | 說明 |
|----------|------|
| `tests/conftest.py` | 共用 fixtures |
| `tests/test_health.py` | 健康檢查測試 |
| `tests/test_skills.py` | SkillRegistry + BaseSkill 測試 |

---

## 檔案總數

| 分類 | 數量 |
|------|------|
| 專案設定檔 | 4 |
| Skill 插件系統 | 8 |
| FastAPI Server | 10 |
| Web Chat UI | 4 |
| 測試檔案 | 3 |
| **合計** | **29** |

---

## 擴充 Skills（由獨立 Kiro Skill 產出）

以下檔案不在 webapp-generator 產出範圍，由各獨立 Kiro Skill 產出後放入對應目錄：

| Kiro Skill | 產出檔案 | 放入位置 |
|------------|---------|---------|
| `ark-fetch-slot-game` | `fetch_slot_game.py` | `src/skills/internal/` |
| `ark-parser-slot-game` | `parser_slot_game.py` + `prompts/parser_slot_game/system.md` | `src/skills/internal/` + `prompts/` |
