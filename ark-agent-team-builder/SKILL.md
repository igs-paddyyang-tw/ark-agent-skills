---
name: ark-agent-team-init
description: |
  產出多 Agent 團隊骨架（team.yaml + scheduler.yaml + 目錄結構 + prompts），
  支援 2-12 人團隊，預設 4 人（admin + leader + dev + qa）。
  只管團隊架構，不管 AI 配置（.kiro/ 由 ark-kiro-init 產出）。
  使用此 Skill 當使用者提及 建立團隊、team init、agent teams、
  多 agent 配置、團隊骨架、ark-team-agent init、
  或任何需要從零建立多 Agent 協作環境的場景。
metadata:
  author: paddyyang
  version: "1.1"
  updated: 2026-05-15
---

# ark-agent-team-init

產出多 Agent 團隊骨架，一句話啟動團隊協作。

## 觸發條件

- 「建立團隊」、「team init」、「agent teams」
- 「多 agent 配置」、「團隊骨架」
- 「ark-team-agent init」、「建立 N 人團隊」

---

## 互動流程

```
1. 確認團隊規模 → 預設 5 人（admin + leader + ai-dev + coder + qa）
2. 確認角色組合 → 從 presets 選或自訂
3. 確認互動模式 → 純私聊 @mention（預設）或 Group Topics
4. 確認排程需求 → 預設開啟（hourly + daily-summary + daily-qa）
5. 產出全部檔案（含 prompts/ 每 agent ≥ 2 個模板）
6. 執行 validate_team.py 驗證結構完整性
7. 提示下一步：「用 /ark-kiro-init 為每個 agent 配置 .kiro/」
```

### 快速模式

使用者直接說「建立 4 人團隊」→ 跳過所有確認，直接用預設值產出。

### 互動模式選擇

| 模式 | 設定 | 適用 |
|------|------|------|
| **純私聊 @mention**（預設） | `channel.bot_token_env` 有值、無 `group_id` | 小團隊、個人助理 |
| **Group Topics** | `channel.bot_token_env` + `group_id` | 大團隊、多人協作 |

純私聊模式下：
- 使用者用 `@{agent-short-name}` 指定對話對象
- 無 @mention 時 Bot 回覆可用 agent 清單
- `/start` 顯示歡迎訊息 + 用法範例
- reply 經 admin 的 `private_chat` 送回使用者

---

## 產出結構

```
{project}/
├── team.yaml                          # 團隊配置（5 instances）
├── scheduler.yaml                     # 排程定義（≥ 2 jobs）
├── .env.example                       # 環境變數範本
├── .gitignore                         # Git 忽略
├── README.md                          # 專案說明（團隊組成 + 啟動方式）
├── pyproject.toml                     # 套件定義（name + dependencies）
├── requirements.txt                   # 依賴清單（ark-team-agent + 業務依賴）
├── tasks/                             # 任務板
│   ├── board.json                     # 空 board（[]）
│   └── items/                         # 任務項目目錄
└── agents/                            # 各 agent 工作目錄（不含 admin）
    ├── AGENTS.md                      # 團隊共用行為準則（所有 agent 複製此檔）
    ├── {leader}-agent/
    │   ├── docs/.gitkeep
    │   ├── output/.gitkeep
    │   └── knowledge/
    │       ├── schema.md
    │       ├── index.md
    │       ├── log.md
    │       ├── raw/.gitkeep
    │       └── wiki/
    │           └── overview.md
    ├── {worker1}-agent/
    │   ├── docs/.gitkeep
    │   ├── output/.gitkeep
    │   └── knowledge/（同上五件套）
    └── {worker2}-agent/
        ├── docs/.gitkeep
        ├── output/.gitkeep
        └── knowledge/（同上五件套）
```

> **注意：** admin 不在 `agents/` 下。admin 的 `working_directory: .`，
> 其 `.kiro/` 就是根目錄的 `.kiro/`（由 `ark-kiro-init` 產出）。
>
> 以下由其他 Skill 在後續 Phase 產出（本 Skill 不負責）：
> - `.kiro/`（根目錄 admin workspace）→ `ark-kiro-init`（Phase A2）
> - `skills/`（共用 Skills 倉庫）→ `ark-kiro-init`（Phase A2）
> - `docs/spec.md` → `ark-superpowers`（Phase A3）
> - `knowledge/`（團隊級知識庫）→ `ark-wiki-engine`（Phase A4）
> - `src/{pkg}/` + `mcp_setup.py` → `ark-mcp-builder`（Phase B1）
> - `start.py` → `ark-team-runtime`（Phase B3）
> - `tests/` → `ark-test-runner`（Phase D1）
### Agent 目錄三件套（必要）

| 目錄 | 用途 |
|------|------|
| `docs/` | Agent 工作文件（spec、設計、筆記） |
| `output/` | 任務產出（交付物） |
| `knowledge/` | 私有知識庫（Schema v3.0，五件套） |

### 知識庫五件套（每個 agent 必有）

| 檔案 | 用途 | 規則 |
|------|------|------|
| `schema.md` | 規則定義 | 定義 frontmatter 欄位、操作規則 |
| `index.md` | 索引目錄 | 每次修改 wiki 必須同步更新 |
| `log.md` | 操作日誌 | **append-only**，禁止刪除舊記錄 |
| `raw/` | 唯讀原始資料 | LLM 只讀不改，ingest 工具處理 |
| `wiki/overview.md` | 知識庫概覽 | 含 frontmatter（title/type/tags/created） |

---

## 產出規則

### 1. team.yaml

```yaml
defaults:
  backend: kiro-cli
  model: auto

cost_guard:
  daily_limit_usd: 30.0
  warn_at_percentage: 80
  timezone: Asia/Taipei

hang_detector:
  enabled: true
  timeout_minutes: 60
  escalation_minutes: 180

channel:
  bot_token_env: TELEGRAM_BOT_TOKEN
  # group_id: -100xxxxxxxxxx        # 有值 = Group Topics 模式；無值 = 純私聊 @mention 模式
  # general_topic_id: 1

access:
  mode: locked
  allowed_users:
    - 123456789                      # 使用者 Telegram ID

instances:
  # Admin — 服務管理（獨立目錄，不接業務）
  {admin-name}-agent:
    working_directory: {admin-name}-agent
    description: "👑 {描述}"
    private_chat: 123456789          # 使用者 ID（reply 出口）
    role: admin

  # Leader — 業務入口
  {leader-name}-agent:
    working_directory: {leader-name}-agent
    description: "{emoji} {描述}"
    role: leader

  # Workers
  {worker-name}-agent:
    working_directory: {worker-name}-agent
    description: "{emoji} {描述}"
    role: worker

health_port: 13030                   # 第二個團隊用 23030 避免衝突
```

**填充規則：**
- `description` 從 `references/role-presets.md` 查對應 emoji + 描述
- admin 的 `working_directory` **必須是 `.`**（根目錄 = admin 的工作目錄）
- admin 的 `.kiro/` 就是根目錄的 `.kiro/`（不在 agents/ 下）
- admin 的 `private_chat` = 使用者 Telegram ID（reply 回覆出口）
- 非 admin 的 `working_directory` 格式為 `agents/{name}-agent`
- 純私聊模式：不設 `group_id`，使用者用 @mention 指定 agent
- Group Topics 模式：設 `group_id`，每個 agent 綁定一個 Topic
- Telegram 區塊預設純私聊模式（group_id 註解）

### 2. scheduler.yaml

```yaml
timezone: Asia/Taipei

jobs:
  - name: hourly-progress
    target: {leader}-agent
    prompt: "⏰ 確認團隊狀態，query_team_status 後依計劃派工或追蹤。更新 memory.md。"
    cron: "10 9-21 * * *"

  - name: daily-summary
    target: {leader}-agent
    prompt: "📋 今日摘要：整理成果 + 明日計劃，reply 回報。"
    cron: "daily:21:00"
```

**條件式 job：**

| 條件 | 加入 job |
|------|---------|
| 有 qa agent | `daily-qa-review`（cron: daily:12:30） |
| 有 admin agent | `daily-changelog`（cron: daily:21:30，target: admin） |
| 團隊 ≥ 5 人 | `wiki-maintenance`（cron: 0 12,18 * * *） |
| 有 analyst | `weekly-data-report`（cron: 0 10 * * 1） |

### 3. .env.example

```
TELEGRAM_BOT_TOKEN=your-token-here
# GEMINI_API_KEY=your-key-here
# DATABASE_URL=postgresql://user:pass@localhost/db
```

### 4. .gitignore

```
.env
state/
*.pid
__pycache__/
*.pyc
```

---

## 角色預設組合

從 `references/role-presets.md` 載入。快速參考：

| 預設 | 角色（含 admin） |
|------|-----------------|
| 最小（3人） | admin + leader + dev |
| 標準（4人） | admin + leader + dev + qa |
| AI 團隊（5人） | admin + leader(pm) + ai-dev + coder + qa |
| 全端（5人） | admin + leader + frontend + backend + devops |
| 遊戲（6人） | admin + leader + gamedev + frontend + backend + qa |
| 完整（7人） | admin + leader + dev + qa + devops + design + analyst |

> admin 永遠存在（服務管理 + reply 出口），不計入「業務角色」。

### Leader 派工標準化

Leader 必須部署 `ark-project-planning` Skill，收到需求時走 6 步流程：
1. 需求釐清（假設 + 釐清問題）
2. 撰寫規格（ark-superpowers 產出）
3. 任務拆解（垂直切片 + 大小標記）
4. 分派任務（統一 📋 格式）
5. 追蹤進度（query_team_status）
6. 驗收交付（對照 DoD）

### 標準派工格式

所有 `delegate_task` 必須使用：
```
📋 任務：{名稱}
📄 規格：specs/{檔名}.md（第 N 節）
🎯 你負責：{具體描述}
📁 範圍：{檔案/目錄}
⏰ 優先級：高/中/低
📎 依賴：{無 / 等待 XXX}
✅ 驗收：{完成條件}
📏 大小：XS / S / M
```

自訂角色命名規則：
- kebab-case（如 `data-engineer`）
- 自動加 `-agent` 後綴
- 禁止特殊字元

---

## MCP Tools 骨架產出

當團隊有業務 MCP Tools 需求時（使用者指定或偵測到 `src/` 目錄），額外產出：

### 產出結構

```
{project}/
├── src/{team_name}/
│   ├── __init__.py
│   ├── tools/
│   │   ├── __init__.py          # TOOL_DEFINITIONS + __all__
│   │   └── base.py              # get_db() + init_tools() 共用基礎
│   └── mcp_setup.py             # register_tools() — 接入 MCP 協議
└── start.py                     # 含 tool_setup=register_tools
```

### src/{team_name}/tools/__init__.py 模板

```python
"""{team_name} MCP Tools."""

TOOL_DEFINITIONS: list[dict] = [
    # 由使用者或後續 Skill 填充
    # {
    #     "name": "tool_name",
    #     "description": "工具描述",
    #     "inputSchema": {"type": "object", "properties": {...}, "required": [...]},
    # },
]

__all__ = ["TOOL_DEFINITIONS"]
```

### src/{team_name}/tools/base.py 模板

```python
"""MCP Tools 共用基礎設施。"""
from __future__ import annotations

_db = None


def get_db():
    """取得資料庫連線（延遲初始化）。"""
    global _db
    if _db is None:
        # 依專案需求初始化（SQLite / BigQuery / PostgreSQL）
        pass
    return _db


def init_tools(config: dict | None = None) -> None:
    """初始化工具依賴（由 daemon 啟動時呼叫）。"""
    pass
```

### src/{team_name}/mcp_setup.py 模板

```python
"""MCP Tools 註冊 — 將業務工具接入 MCP 協議。"""
from __future__ import annotations

from ark_team_core import McpRegistry, ToolDefinition
from .tools import TOOL_DEFINITIONS

HANDLERS: dict[str, callable] = {}


def register_tools(registry: McpRegistry) -> None:
    """將業務工具註冊到 MCP Server。"""
    for defn in TOOL_DEFINITIONS:
        name = defn["name"]
        if name in HANDLERS:
            registry.register(ToolDefinition(
                name=name,
                description=defn["description"],
                input_schema=defn["inputSchema"],
                handler=HANDLERS[name],
            ))
```

### 觸發條件

| 條件 | 動作 |
|------|------|
| 使用者說「含 MCP 工具」或「有業務工具」 | 產出 MCP Tools 骨架 |
| 使用者指定 `project_type: "data-pipeline"` | 自動產出 |
| 預設（無特別指定） | 不產出（純團隊骨架） |

### 品質檢查追加

- [ ] `src/{team_name}/tools/__init__.py` 存在且有 `TOOL_DEFINITIONS`
- [ ] `src/{team_name}/mcp_setup.py` 存在且有 `register_tools()`
- [ ] `start.py` 含 `tool_setup=register_tools`

---

## 冪等性

```
if team.yaml 已存在:
  提示「team.yaml 已存在」
  - 使用者選覆寫 → 重新產出
  - 使用者選跳過 → 只補缺少的目錄

if agents/{name}/ 已存在:
  跳過（不刪除已有內容）
```

---

## 品質檢查

產出後自動驗證（執行 `scripts/validate_team.py`）：

- [ ] `team.yaml` 有 defaults + cost_guard + hang_detector + instances + health_port
- [ ] 每個 instance 有 working_directory + description + role
- [ ] 恰好 1 個 role: admin（working_directory 必須是 `.`）
- [ ] 恰好 1 個 role: leader
- [ ] instance 命名符合 `^[a-z][a-z0-9-]*-agent$`
- [ ] `scheduler.yaml` 有 timezone + 至少 2 個 jobs
- [ ] 每個非 admin agent 目錄存在三件套：`docs/` + `output/` + `knowledge/`
- [ ] 每個 agent 的 `knowledge/` 有五件套：schema.md + index.md + log.md + raw/ + wiki/overview.md
- [ ] `agents/AGENTS.md` 存在（團隊共用行為準則）
- [ ] `tasks/board.json` 存在
- [ ] `README.md` 存在
- [ ] `pyproject.toml` 存在
- [ ] `requirements.txt` 存在
- [ ] `.env.example` 存在
- [ ] `.gitignore` 存在

---

## 完成回報格式

```
✅ 團隊骨架已建立

📁 產出清單：
- team.yaml（{N} 個 instances）
- scheduler.yaml（{M} 個 jobs）
- .env.example
- .gitignore
- agents/{name1}-agent/（三件套 + 知識庫五件套）
- agents/{name2}-agent/（三件套 + 知識庫五件套）
- ...

📋 下一步：
1. 填寫 .env（Telegram token 等）
2. 執行 /ark-kiro-init 為每個 agent 配置 .kiro/
3. 執行 ark-team-agent team start 啟動團隊
```

---

## 注意事項

- 此 Skill 只產出團隊骨架，不產出 .kiro/ 配置
- .kiro/ 由 /ark-kiro-init 產出（含 steering + agent.json + skills）
- 知識庫由 /ark-wiki-engine 產出
- team.yaml schema 遵循 ark-team-agent v0.11+

### Skills 部署規則

ark-kiro-init 產出 .kiro/ 時，必須部署核心 4 個 Skills 到 `.kiro/skills/`：

| Skill | 用途 | 部署對象 |
|-------|------|---------|
| `ark-superpowers` | 文件產出（spec / design / plan） | 全員 |
| `ark-wiki-engine` | 知識庫管理（ingest / query） | 全員 |
| `ark-skill-creator` | 建立/修改 Skill | 全員 |
| `ark-code-spec-validator` | 驗證 code 與 spec 一致性 | 全員 |

**來源：** 從專案根層 `skills/` 目錄複製（如有），或從 ark-kiro-init 的 references 載入。

**admin 額外 Skills：** admin 可擁有全套 Skills（視需求），worker 只需核心 4 個。

---

## 附帶資源

### scripts/（產出後自動驗證）

| 腳本 | 用途 | 觸發時機 |
|------|------|---------|
| `validate_team.py` | 驗證 team.yaml 結構完整性 | 產出後執行 |
| `scaffold_dirs.py` | 讀 team.yaml → 建立目錄骨架 | 產出時呼叫 |
| `gen_env.py` | 依 team.yaml 動態產出 .env.example | 產出時呼叫 |

### references/（按需載入）

| 文件 | 用途 | 載入時機 |
|------|------|---------|
| `role-presets.md` | 角色預設組合表 | 確認角色時 |
| `naming-rules.md` | 命名規範 | 驗證 instance 名稱時 |
| `communication-presets.md` | P2P 通訊策略預設 | 使用者選「進階通訊」時 |
| `kiro-files-presets.md` | kiro_files policy 預設 | 使用者問 .kiro 配置時 |
| `troubleshooting.md` | 環境問題排查指南 | 啟動失敗時 |
| `templates/team.yaml.tpl` | team.yaml 模板 | 產出時 |
| `templates/scheduler.yaml.tpl` | scheduler.yaml 模板 | 產出時 |
| `templates/docker-compose.yaml.tpl` | Docker 部署模板 | 使用者選「Docker」時 |

### assets/（直接輸出）

| 檔案 | 用途 | 產出條件 |
|------|------|---------|
| `start-team.bat` | Windows watchdog 腳本 | 永遠產出 |
| `start-team.sh` | Linux/Mac watchdog 腳本 | 永遠產出 |
| `gitignore.txt` | .gitignore 範本 | 永遠產出（copy 為 .gitignore） |


---

## Workshop 引導（agent-team-workshop）

本 Skill 對應 Workshop Step 1：建立團隊骨架。

### 觸發提詞

```
建立 5 人 AI 團隊，角色：admin + leader + ai-dev + coder + qa
```

### 預期產出

- `team.yaml`（5 個 instances）
- `scheduler.yaml`（≥ 2 個 jobs）
- `agents/` 目錄（每個 agent 三件套 + 知識庫五件套）
- `.env.example`、`.gitignore`、`README.md`

### 驗證方式

```bash
python scripts/validate_team.py
```

全部 ✅ 即通過。

### 下一步

完成後告訴 AI：`產出團隊啟動程式，包含 CoreDaemon + Telegram + 排程`（觸發 ark-team-runtime）

### 卡關時

- 直接複製 `team.example.yaml` 改名為 `team.yaml`
- 手動建目錄：`mkdir agents\leader-agent\docs agents\leader-agent\output agents\leader-agent\knowledge`
