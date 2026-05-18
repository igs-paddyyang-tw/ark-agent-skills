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
├── team.yaml
├── scheduler.yaml
├── .env.example
├── .gitignore
├── start-team.bat            ← watchdog（Windows）
├── start-team.sh             ← watchdog（Linux/Mac）
└── agents/
    ├── {admin}-agent/                 # Admin（服務管理）
    │   ├── docs/.gitkeep
    │   ├── output/.gitkeep
    │   └── knowledge/
    │       ├── schema.md
    │       ├── index.md
    │       ├── log.md
    │       ├── raw/.gitkeep
    │       └── wiki/
    │           └── overview.md
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
    │   └── knowledge/
    │       ├── schema.md
    │       ├── index.md
    │       ├── log.md
    │       ├── raw/.gitkeep
    │       └── wiki/
    │           └── overview.md
    └── {worker2}-agent/
        ├── docs/.gitkeep
        ├── output/.gitkeep
        └── knowledge/
            ├── schema.md
            ├── index.md
            ├── log.md
            ├── raw/.gitkeep
            └── wiki/
                └── overview.md
```

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
- admin 的 `private_chat` = 使用者 Telegram ID（reply 回覆出口）
- 純私聊模式：不設 `group_id`，使用者用 @mention 指定 agent
- Group Topics 模式：設 `group_id`，每個 agent 綁定一個 Topic
- Telegram 區塊預設純私聊模式（group_id 註解）
- `working_directory` 相對於 team_home（不加 `agents/` 前綴）

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
- [ ] 恰好 1 個 role: leader
- [ ] instance 命名符合 `^[a-z][a-z0-9-]*-agent$`
- [ ] `scheduler.yaml` 有 timezone + 至少 2 個 jobs
- [ ] 每個 agent 目錄存在三件套：`docs/` + `output/` + `knowledge/`
- [ ] 每個 agent 的 `knowledge/` 有五件套：schema.md + index.md + log.md + raw/ + wiki/overview.md
- [ ] 每個 agent 的 `.kiro/prompts/` 有 ≥ 2 個模板
- [ ] 每個 agent 的 `.kiro/agents/*.json` 有 name/description/prompt/tools/resources
- [ ] leader agent 部署 `ark-project-planning` Skill
- [ ] `.env.example` 存在
- [ ] `.gitignore` 存在
- [ ] `start-team.bat` + `start-team.sh` 存在
- [ ] steering 總量 ≤ 50KB（每個 agent）

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
- .kiro/ 由 /ark-kiro-init 或 /ark-gemini-init 產出（使用者選擇 AI 平台）
- 知識庫由 /ark-wiki-engine 產出
- team.yaml schema 遵循 ark-team-agent v0.11+

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
