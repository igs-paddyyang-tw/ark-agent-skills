---
name: ark-agent-bot-builder
description: |
  產出 ark_bot_agent 套件消費端的 Bot workspace 骨架 —— 裝 wheel + 產設定檔，
  不手搭架構（runtime / Web UI / 記憶 / TG polling 全由套件內建）。
  產出：start.py（8 行 run_bot）+ bot.yaml（怎麼跑）+ agents.yaml（有誰）+
  .env 骨架 + 目錄結構（.kiro/steering + knowledge/shared + memory + artifacts）。
  預設單 bot（manager 娜娜 + admin + leader + worker），三模式（chat/agent/team）。
  使用此 Skill 當使用者提及 建立 AI Bot、產出 Bot workspace、ark-agent-bot-builder、
  ark_bot_agent 消費端、快速建 Agent Bot、加入 Telegram Bot、chatbot、bot 骨架、
  或任何需要建立 ark_bot_agent 套件消費端的場景。
  不適用於：① 多 agent 團隊 daemon → ark-agent-team-builder（ark_team_agent）；
  ② 非套件的獨立 FastAPI 應用 → ark-webapp-generator；③ steering 人格 → ark-agent-init。
metadata:
  schema_version: 1
  status: active
  category: scaffolder
  depends_on: [ark-agent-init]
  outputs:
    - format: code
      audience: ai
  author: paddyyang
  version: "3.0"
  updated: 2026-09-08
---

# ark-agent-bot-builder

產出 `ark_bot_agent` 套件消費端的 Bot workspace 骨架：**裝 wheel + 產設定檔**。

> **v3.0 重寫（2026-09-08）**：本 skill 原為「手搭 bot 架構」（參考 ninja-bot 的
> BaseSkill / ConversationPlanner / LLMRouter / Orchestrator，40+ 個 Python 模板）。
> 那套東西**已全部套件化為 `ark_bot_agent`** —— runtime、三模式路由、Web UI、
> 四層搜尋、記憶系統、TG polling、報告管線都在套件裡。
> 現在建 bot 只需：**裝 wheel + 8 行 start.py + 設定檔**。手搭模板已移除。

## 定位（與鄰近 skill 的分工）

| 需求 | 用哪個 |
|------|--------|
| **單 bot**（ark_bot_agent 消費端） | **本 skill** |
| 多 agent 團隊 daemon（ark_team_agent） | `ark-agent-team-builder` |
| 非套件的獨立 FastAPI web 應用 | `ark-webapp-generator` |
| agent 的 steering 人格 + 多 CLI 入口 | `ark-agent-init`（本 skill 產骨架後呼叫它補人格） |

## 觸發條件

- 「建立 AI Bot」、「產出 Bot workspace」、「ark-agent-bot-builder」
- 「ark_bot_agent 消費端」、「快速建 Agent Bot」、「bot 骨架」
- 「加入 Telegram Bot」、「chatbot」、「聊天機器人」

## 輸入參數

| 參數 | 型別 | 必要 | 預設 | 說明 |
|------|------|------|------|------|
| `project_name` | str | ✅ | — | 專案 / bot 名稱 |
| `output_dir` | str | ❌ | `.` | 輸出目錄 |
| `codename` | str | ❌ | 娜娜 | bot 對外代號 |
| `admin_chat_id` | str | ❌ | — | 管理員 TG chat_id |

---

## 產出流程

### 步驟 1：裝套件

```bash
uv venv --python 3.13
# wheel 從 Release 取得：github.com/igs-paddyyang-tw/ark_bot_agent/releases
uv pip install --python .venv/bin/python '<ark_bot_agent-*.whl>[search,skills]'
```

> 🔴 **extras 不可省** —— 只裝 base wheel 會少兩組能力且**不報錯**：
> `[search]`（bm25s/jieba/PyStemmer）缺了四層搜尋靜默降級成 purepy + CJK bigram；
> `[skills]`（apscheduler/jinja2/markdown/feedparser/bs4/openai）缺了 `schedule_engine`
> 只印一行 WARNING 就跳過。
>
> 🔴 換裝後**驗 import 版號，不看 pip 輸出**（MEMORY 記過「回報成功但沒裝進去」）：
> `.venv/bin/python -c "import ark_bot_agent; print(ark_bot_agent.__version__)"`

### 步驟 2：產目錄結構

```
{project}/
├── start.py                 # 8 行 run_bot（assets/start.py）
├── bot.yaml                 # 怎麼跑（assets/bot.yaml）
├── agents.yaml              # 有誰（assets/agents.yaml）← 專案根哨兵
├── .env                     # 機密（assets/env.example → .env）
├── requirements.txt         # 只列 wheel
├── .kiro/steering/          # 人格（由 ark-agent-init 產）
├── knowledge/
│   ├── shared/{wiki,raw}/    # 🔴 Wiki 引擎讀這層（少一層 shared 會靜默失效）
│   │   └── {schema,index,log}.md
│   └── raw/memory-archive/   # MEMORY 歸檔落點（路徑寫死不可搬）
├── memory/                   # 🔴 套件記憶落點（daily/recent.md/memory.md）
│   └── daily/
├── artifacts/reports/        # 🔴 產出目錄（取代舊 output/）
├── agents/<name>-agent/      # 各 agent：.kiro + knowledge + memory + artifacts
└── skills/                   # 業務 skill（選填，run_bot(skills=[...]) 掛載）
```

> 三個骨架缺口（`knowledge/shared/`、`memory/`、`artifacts/`）詳見
> `ark-agent-init/references/architecture-drift-feedback.md`。

### 步驟 3：填設定檔（三檔分工，不合併）

| 檔 | 職責 | 骨架 |
|----|------|------|
| `agents.yaml` | 有誰（default/manager/admin/leader/worker） | `assets/agents.yaml` |
| `bot.yaml` | 怎麼跑（server/modes/llm/backend/report/features/access） | `assets/bot.yaml` |
| `.env` | 機密（`TELEGRAM_BOT_TOKEN` / `GEMINI_API_KEY`） | `assets/env.example` |

替換佔位符：`{PROJECT_NAME}` / `{CODENAME}` / `{BOT_NAME}` / `{ADMIN_CHAT_ID}`。
`bot.yaml` 整份可不存在（走預設）；留著是為了顯式可見。

### 步驟 4：補 steering 人格

呼叫 `ark-agent-init` 為 manager（根目錄）與各 agent 產 `.kiro/steering`
（SOUL 人格 + AGENTS 規範 + 多 CLI 入口）。本 skill 只產「架構骨架」，人格交給它。

### 步驟 5：啟動驗證

```bash
.venv/bin/python start.py            # Tier 分級啟動
python -m ark_bot_agent paths        # 診斷解析結果
curl -s localhost:8888/health        # ark_bot_agent → /health
```

Tier 0（Skills+Wiki）永遠可用；Tier 1（TG）需 token；Tier 2（Gemini）需 key；Tier 3（kiro-cli）。

---

## 三模式（套件內建，設定即用）

| 模式 | 引擎 | 費用 | 設定 |
|------|------|------|------|
| 💬 chat | Gemini ReAct | 有 API 費用 | `bot.yaml` modes.chat |
| 👤 agent | kiro-cli | 零費用 | modes.default_agent |
| ⚔️ team | kiro-cli + 三階段工作流 | 零費用 | modes.team_leader + leader.group_members |

## 注意事項

- Python 3.13、`pathlib.Path`、async I/O、繁中 docstring
- **不要手搭** runtime / Web UI / 記憶 / TG —— 套件都有；手搭 = 兩套並存必漂移
- 業務 skill 放 `skills/`，`run_bot(skills=["skills"])` 掛載；純消費端可 `run_bot()`
- 換裝驗 import 版號；設定改完用 `paths` 診斷確認套件讀得到

## 附帶資源

| 路徑 | 說明 |
|------|------|
| `assets/start.py` | 8 行 run_bot 入口 |
| `assets/bot.yaml` | bot 設定骨架 |
| `assets/agents.yaml` | agent 定義骨架（新 schema） |
| `assets/env.example` | .env 骨架 |
| `assets/requirements.txt` | 只列 wheel |
| `scripts/build_agent.py` | 骨架產生腳本（產目錄+複製 assets+替換佔位符） |
| `scripts/validate_agent.py` | 產出驗證 |
