---
author: paddyyang
name: ark-scheduler-generator
description: |
  在既有專案上加入 WorkflowEngine 工作流引擎、ScheduleEngine 排程引擎，
  並產出範例 Workflow YAML、排程定義與 agent-browser MCP Server，可獨立運作。
  使用此 Skill 當使用者提及 ark scheduler、加入排程、gen workflow、
  工作流引擎、排程引擎、每日報表自動化、daily slot report、
  或任何需要在既有專案上加入 YAML 工作流與 APScheduler 排程的場景。
---

# ark-scheduler-generator

在既有專案上加入 WorkflowEngine + ScheduleEngine，可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「加入排程」、「排程引擎」、「排程系統」
- 「ark scheduler」、「gen workflow」
- 「工作流引擎」、「Workflow Engine」
- 「每日報表自動化」、「daily slot report」
- 「APScheduler」、「cron 排程」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 既有專案目錄路徑 |
| `notify_chat_id` | `str` | ❌ | — | Telegram 推送目標 chat_id |

## 前置條件

- 專案目錄下存在 `src/skills/base.py` + `src/skills/registry.py`（Skill 插件系統）

## 產出指引

在 `{project_dir}/` 下新增 Workflow 引擎、排程引擎與範例 Workflow 檔案。

---

### 步驟 1：建立目錄結構

```
{project_dir}/
├── src/
│   ├── workflow/           # 工作流引擎（新增）
│   │   ├── __init__.py
│   │   ├── context.py      # RunContext
│   │   └── engine.py       # WorkflowEngine
│   └── scheduler/          # 排程引擎（新增）
│       ├── __init__.py
│       └── engine.py       # ScheduleEngine
├── workflows/              # YAML 工作流定義（新增）
│   └── schedules/          # 排程定義
└── artifacts/
    └── charts/             # 圖表輸出目錄
```

---

### 步驟 2：產出 WorkflowEngine 工作流引擎

遵循 `references/workflow-yaml-schema.md` 中的格式規範。

1. **`src/workflow/context.py`** — `RunContext` dataclass：
   - `run_id`、`workflow_id`、`params`、`status`（PENDING/RUNNING/COMPLETED/FAILED）
   - `outputs`（dict）、`current_step`、`total_steps`
   - `set_step_output()`、`get_output()`、`add_error()`、`to_dict()`

2. **`src/workflow/engine.py`** — `WorkflowEngine` 類別：
   - `__init__(registry: SkillRegistry)` — 注入 SkillRegistry
   - `load(yaml_path) -> dict` — 從 YAML 載入工作流
   - `run(workflow_id, params) -> RunContext` — 執行主迴圈
   - 四種步驟類型：`skill`、`condition`、`loop`、`parallel`
   - Jinja2 模板解析參數（`{{ outputs.fetch.games }}`）
   - `eval()` 條件表達式限制 `{"__builtins__": {}}`

---

### 步驟 3：產出 ScheduleEngine 排程引擎

遵循 `references/schedule-yaml-schema.md` 中的格式規範。

**`src/scheduler/engine.py`** — `ScheduleEngine` 類別：
- `__init__(workflow_engine: WorkflowEngine)`
- `load_schedules(yaml_path) -> list[dict]`
- `start()` — 啟動 APScheduler，僅註冊 `enabled=True` 的排程
- `stop()` — 優雅關閉
- `toggle(schedule_id) -> bool` — 動態啟用/停用
- `${ENV_VAR}` 環境變數在執行時替換

---

### 步驟 4：產出範例 Workflow YAML

所有範例使用 echo Skill 測試功能，確保不依賴外部 Skill。

1. **`workflows/hello.yaml`** — 基礎測試（skill 類型）：
   ```yaml
   id: hello
   name: Hello World 測試工作流
   steps:
     - id: greet
       type: skill
       skill: echo
       params:
         message: "Hello from WorkflowEngine!"
       output: greeting
   ```

2. **`workflows/echo_loop.yaml`** — loop 類型測試：
   ```yaml
   id: echo_loop
   name: Echo Loop 測試工作流
   steps:
     - id: batch
       type: loop
       items: '["A", "B", "C"]'
       item_var: letter
       step:
         id: echo_item
         type: skill
         skill: echo
         params:
           message: "Echo: {{ letter }}"
         output: echoed
       output: results
   ```

3. **`workflows/echo_condition.yaml`** — condition 類型測試：
   ```yaml
   id: echo_condition
   name: Echo Condition 測試工作流
   params:
     mode: "greet"
   steps:
     - id: check
       type: condition
       condition: "params.get('mode') == 'greet'"
       then:
         id: yes
         type: skill
         skill: echo
         params:
           message: "Hello!"
         output: result
       else:
         id: no
         type: skill
         skill: echo
         params:
           message: "Goodbye!"
         output: result
   ```

4. **`workflows/schedules/morning_report.yaml`** — 排程定義（每日 08:30 觸發 hello）：
   ```yaml
   id: morning_report
   workflow_id: hello
   cron: "30 8 * * 1-5"
   enabled: true
   params:
     message: "早安，每日報表啟動"
   ```

---

### 步驟 5：產出 API 路由

1. **`src/server/api/workflows.py`** — Workflow API：
   - `POST /api/v1/workflows/run` — 觸發工作流
   - `GET /api/v1/workflows` — 列出工作流
   - `GET /api/v1/workflows/{id}/status/{run_id}` — 查詢狀態

2. **`src/server/api/schedules.py`** — Schedule API：
   - `GET /api/v1/schedules` — 列出排程
   - `POST /api/v1/schedules/{id}/toggle` — 啟用/停用

---

### 步驟 6：更新既有檔案

1. **`requirements.txt`** — 新增 `apscheduler>=3.10.0`、`matplotlib>=3.8.0`
2. **`src/server/main.py`** — lifespan 初始化 WorkflowEngine + ScheduleEngine
3. **`src/server/api/router.py`** — 掛載 workflows + schedules 路由

---

### 步驟 7：驗證

確認所有新增檔案已產出且工作流可執行：

```bash
python -c "from src.workflow.engine import WorkflowEngine; print('OK')"
```

---

## 擴充 Skills

產出的排程骨架支援透過獨立 Kiro Skills 擴充功能。
新增 Skill 放入 `src/skills/internal/`，Workflow YAML 中以 `skill: skill_id` 引用。
新增 Workflow YAML 放入 `workflows/`，排程定義放入 `workflows/schedules/`。

### Workflow 基礎工具：template_render

`template_render` 是 Workflow 步驟間的「膠水」Skill，用 Jinja2 將資料塞進模板字串。
它不產出檔案，只回傳渲染後的字串，供下一步使用。

**產出**：`src/skills/python_skills/template_render.py`

```python
class TemplateRenderInput(SkillParam):
    template: str = Field(description="Jinja2 模板字串")
    context: dict = Field(default_factory=dict, description="模板變數")

class TemplateRenderSkill(BaseSkill):
    skill_id = "template_render"
    skill_type = SkillType.PYTHON
    description = "使用 Jinja2 渲染模板字串"
    input_schema = TemplateRenderInput
```

**與 ark-report-template 的區別**：

| | template_render | ark-report-template |
|---|---|---|
| 定位 | Workflow 步驟間的膠水 | 最終報表產出 |
| 輸入 | 模板字串 + context dict | 模板名稱 + data + charts |
| 輸出 | 渲染後的字串（記憶體） | 完整報表檔案（MD/HTML） |
| 重量 | 輕量（3 行核心邏輯） | 重量（模板載入 + 圖表嵌入） |

**實際應用情境**：

| 情境 | Workflow 步驟 | template_render 做什麼 |
|------|-------------|----------------------|
| 通知訊息 | ETL → chart → **template_render** → telegram_notify | 組裝通知文字：「今日新增 {{count}} 款遊戲」 |
| Prompt 組裝 | wiki_query → **template_render** → llm_analyze | 把 Wiki context 塞進 LLM prompt |
| 動態檔名 | **template_render** → file_export | 產生 `report_{{date}}_{{region}}.csv` |
| 排程摘要 | workflow 完成 → **template_render** → memory 寫入 | 格式化執行結果存入記憶 |

**Workflow YAML 範例**：

```yaml
- id: format_notify
  type: skill
  skill: template_render
  params:
    template: "📊 每日報表完成\n新遊戲：{{ count }} 款\nTop 3：{{ top3 | join(', ') }}"
    context:
      count: "{{ outputs.transform.count }}"
      top3: "{{ outputs.transform.top_providers }}"
  output: notify_text
```

## 整合模式

WorkflowEngine + ScheduleEngine 整合進 webapp 的 `lifespan`：

```python
# src/server/main.py lifespan 中
workflow_engine = WorkflowEngine(registry)
workflow_engine.load_dir(Path("workflows"))

schedule_engine = ScheduleEngine(workflow_engine)
schedule_engine.load_schedules(Path("workflows/schedules"))
schedule_engine.start()
# shutdown 時
schedule_engine.stop()
```

整合後提供 API 端點：
- `GET /api/v1/workflows` — 列出所有工作流
- `POST /api/v1/workflows/run` — 觸發工作流
- `GET /api/v1/schedules` — 列出所有排程
- `POST /api/v1/schedules/{id}/toggle` — 啟用/停用排程

排程使用 `AsyncIOScheduler`，與 FastAPI 共用同一個 event loop。

## 注意事項

- 所有程式碼使用 Python 3.12 語法
- Docstring 使用繁體中文
- 路徑操作一律使用 `pathlib.Path`
- 所有 I/O 操作使用 `async/await`
- `eval()` 僅限條件表達式，已設定 `{"__builtins__": {}}`
- Workflow YAML 的 `id` 欄位為必要且唯一
- 排程 `${ENV_VAR}` 在執行時替換，非載入時

## 踩坑紀錄

### WorkflowEngine 模板解析（2026-04-17）

`_resolve_params` 中 Jinja2 模板渲染後回傳的是字串，但下游 Skill 的 `input_schema` 期望 dict/list。

解決方案：
1. 簡單引用（`{{ outputs.xxx }}`）直接從 `ctx.outputs` 取 Python 物件，不走 Jinja2 渲染
2. 複雜表達式走 Jinja2 渲染後嘗試 `json.loads()` 反序列化
3. `${ENV_VAR}` 格式在 `_resolve_params` 中直接替換為 `os.environ.get()`

```python
# 簡單引用：直接取值
simple_match = re.match(r"\{\{\s*outputs\.(\w+)(?:\.(\w+))?\s*\}\}", template_str)
if simple_match:
    return ctx.outputs.get(key)  # 回傳原始 Python 物件

# 環境變數
if v.startswith("${") and v.endswith("}"):
    resolved[k] = os.environ.get(v[2:-1], "")
```

---

## Workshop 引導（ai-bot-workshop）

本 Skill 對應 Workshop Step 3：加入排程系統。

### 前一步

確認已完成 Step 2（`ark-chatbot-generator`），專案有 `src/bot/`。

### 觸發提詞

```
加入排程系統
```

### 預期產出

- `src/workflow/engine.py` — WorkflowEngine
- `src/scheduler/engine.py` — ScheduleEngine
- `workflows/hello.yaml` — 測試用工作流
- `workflows/schedules/morning_report.yaml` — 排程範例

### 驗證方式

```bash
python -c "from src.workflow.engine import WorkflowEngine; print('OK')"
```

### 下一步

完成後告訴 AI：`封裝 Gemini CLI 為 Skill`（觸發 ark-llm-cli）

### 卡關時

- `No module named 'apscheduler'` → `pip install apscheduler`
- YAML 載入失敗 → 確認 `workflows/` 目錄存在且有 `.yaml` 檔案
- 排程沒觸發 → 確認 `enabled: true` 且 cron 時間正確
