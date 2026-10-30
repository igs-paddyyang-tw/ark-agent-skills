# 各檔案產出規則（agents json、AGENTS.md、steering 七份、prompts、skills、mcp.json）

> 2026-10-30 自 SKILL.md 原樣搬出（盤點 O-4：主檔只留流程與決策）。

## 各檔案產出規則

### 1. agents/{role}.json

依 Kiro 官方 Agent Configuration 格式：

```json
{
  "name": "{role-id}",
  "description": "{一句話描述}",
  "prompt": "file://../../.kiro/steering/SOUL.md",
  "model": "auto",
  "tools": ["*"],
  "allowedTools": ["*"],
  "resources": [
    "file://../../.kiro/steering/**/*.md",
    "skill://.kiro/skills/**/SKILL.md",
    {
      "type": "knowledgeBase",
      "source": "file://./knowledge",
      "name": "{RoleName}Knowledge",
      "description": "{角色專屬知識描述}"
    }
  ],
  "mcpServers": {
    "{server-name}": {
      "command": "{cmd}",
      "args": ["{args}"],
      "env": { "{KEY}": "${ENV_VAR}" }
    }
  },
  "hooks": {
    "agentSpawn": [{ "command": "git status" }],
    "postToolUse": [{ "matcher": "fs_write", "command": "echo 'file written'" }]
  },
  "welcomeMessage": "{角色就緒提示}"
}
```

**欄位說明：**

| 欄位 | 必要 | 說明 |
|------|------|------|
| name | ✅ | 角色 ID（檔名去 .json） |
| description | ✅ | 一句話描述 |
| prompt | ✅ | 指向 steering/SOUL.md |
| model | 選填 | 預設 claude-sonnet-4 |
| tools | ✅ | `["*"]` 或明確列出 |
| allowedTools | ✅ | 免確認工具（`["*"]` = trust all） |
| resources | ✅ | `file://` + `skill://` URI |
| mcpServers | 選填 | 角色需要的 MCP Server |
| hooks | 選填 | agentSpawn/postToolUse 等 |
| welcomeMessage | 選填 | 切換到此 agent 時的提示 |

### 2. AGENTS.md（Ark Agent 架構＋共用規範的單一來源，放 workspace 根）

**範本：`assets/AGENTS.md`**（2.6.0 起 build_kiro 在專案根產出，已存在不覆寫；子 agent 工作目錄根放逐字複本）。
內容工具中立、自成一體（Codex 不支援匯入）：

| 節 | 內容 |
|---|---|
| 這個 workspace 是什麼 | 型（team／bot）、入口 agent、編制（以 team.yaml／agents.yaml 為準）、IDE 工具共用目錄與交接方式 |
| Ark Agent 五層架構 | 五層表（位置／誰寫／權限）＋技能 vs 腳本＋紅線；完整定義連 `references/five-layer-architecture.md` |
| 開場與收尾 | 開場讀 BRAIN／MEMORY／最新 daily；收尾寫 daily |
| 回覆、開發流程、記憶、知識庫、Git、反證、禁止事項 | 共用規範（工具中立寫法） |
| 各工具入口 | Kiro／Claude Code／Codex／其他各怎麼讀到本檔；工具專屬寫法（Kiro 的 `fs_write`、`/context add`）只放這裡 |

> 團隊模式的 MCP 工具（`reply`、`send_to_instance`、`delegate_task`…）放 `steering/TEAM.md`（inclusion: manual），AGENTS.md 只留一行指路。
> 要改內容就改範本或專案根那份 —— **不要在 SKILL.md 或 CLAUDE.md 再抄一份**（多處各寫一份必然漂移）。

### 3. steering/MEMORY.md（記憶導覽）

定義「記憶住在哪 + 目前在哪」—— 每次對話自動載入，所以**只放指路與判準級精華，不放事件流水**。
骨架即 `assets/steering/MEMORY-template.md`（build_kiro 直接用它產生）：

```markdown
# 🧭 {Project} — 記憶導覽
> 記憶導覽，不是事件流水；規則見 AGENTS.md「記憶怎麼用」。

## 🧭 記憶住在哪          ← BRAIN / MEMORY / memory.md / daily / archive 五列表
## 📌 專案快照            ← 常青段（狀態／定版結構／技術決策）
## 📌 近期里程碑          ← 一行索引：- **YYYY-MM-DD** {判準級結論} → memory/archive/YYYY-MM.md
## 待辦
```

> 🔴 舊範本的「每完成一個段落必須更新」「> 2 週移到 knowledge/」都已作廢：
> 事件 → `memory/daily/`；歸檔 → `memory/archive/`（套件 `_builtin:memory-consolidate` 自動搬）。

### 高優先
- [ ] （使用者填入）

### 低優先
- [ ] （使用者填入）

## 近期進度
（Kiro 自動累積，格式：## YYYY-MM-DD — 一句話標題）

### 4. steering/USER.md（使用者百科）

定義「關於使用者」— Agent 自動整理並持續更新，跨專案攜帶。

```markdown
# USER.md — 使用者百科

> 由 Agent 自動整理並持續更新。跨專案攜帶，讓 Agent 認出你。

## 個人特徵與偏好
- **稱呼：** 
- **職業：** 
- **開發環境：** 
- **偏好語言：** 
- **技術偏好：** 

## 溝通風格
- **回答風格：** （簡短直接 / 詳細逐步）
- **語氣：** （專業 / 輕鬆）
- **格式要求：** 

## 長期目標與專案背景
- **當前專案：** 
- **學習目標：** 
- **已解決的重大問題：** 

## 行為習慣與約定
- （工作流程約定）
- （回覆格式約定）
```

**更新規則：** Agent 在對話中觀察到使用者偏好時，主動追加到對應段落。不需使用者明確要求。

### 5. steering/SOUL.md（八段式角色定義）

必須包含以下八段，每段都要有實質內容：

```markdown
# {emoji} {RoleName} — {一句話定位}

> 所有回覆使用繁體中文。

## 🧠 Your Identity & Memory
- **Role**：{角色定位}
- **Personality**：{個性風格}
- **Memory**：{記得哪些踩坑經驗}
- **Experience**：{信條}

## 🎯 Your Core Mission
### {一句話使命}
1. {職責 1}
2. {職責 2}（3-5 條）

## 🚨 Critical Rules You Must Follow
{鐵則 + 禁用清單}

## 📋 Your Technical Deliverables
| 產出類型 | 格式 | 存放路徑 |

## 🔄 Your Workflow Process
{SOP 步驟}

## 💭 Your Communication Style
{回覆格式 + 語氣}

## 🎯 Your Success Metrics
| 指標 | 目標 |

## 🧰 MCP Tools
| 工具 | 用途 |

## ⚙️ Tool Settings
- All tools are trusted
```

### 6. steering/tech.md

依角色列出：
- 語言與版本（表格）
- 框架與工具
- Linting / 測試工具
- 效能預算

### 7. steering/{domain}.md

角色特定的領域規範（kebab-case 命名），例如：
- 全端 → `api-contract.md`（REST/gRPC/Event 標準）
- DevOps → `infra-standards.md`（IaC/CI/CD 規範）
- ML → `model-lifecycle.md`（訓練/部署/監控）

### 8. steering/structure.md

- 目錄樹（含註解）
- 命名規範表格
- Commit 訊息格式

### 9. prompts/*.md

每個角色產出 2-3 個常用 prompt，格式：

```markdown
# @{action-name} — {一句話說明}

{使用情境描述}

{{user_input}}

---

## 請提供以下產出：
1. {產出項 1}
2. {產出項 2}
```

### 10. skills/{skill-name}/SKILL.md

角色專屬技能，格式：
- YAML frontmatter（name + description）
- 觸發條件
- 互動流程
- 輸出格式
- 品質要求

**Skills 來源：** 從 `https://github.com/igs-paddyyang-tw/ark-agent-skills` clone 到**專案根目錄的 `skills/`**。

**Clone 流程：**

```bash
# Clone 到專案根目錄（與 agents/ 同層）
git clone https://github.com/igs-paddyyang-tw/ark-agent-skills.git skills/

# 結構：
# {project}/
# ├── skills/              ← 共用 Skills 倉庫（所有 agent 的來源）
# │   ├── ark-superpowers/SKILL.md
# │   ├── ark-wiki-engine/SKILL.md
# │   └── ...
# ├── agents/
# │   └── {name}-agent/.kiro/skills/  ← 從 skills/ 複製子集
# └── .kiro/               ← 根目錄也有 .kiro（管理者/CEO 用）
```

**根目錄 .kiro/ 建立規則：**

根目錄的 `.kiro/` **是 `working_directory: "."` 那個 instance 的 workspace**（manager 或 admin，依 team.yaml）：
- 該 instance 的 Kiro CLI 啟動時 cwd = 根目錄，自動載入根目錄 `.kiro/`
- 🔴 **不預設是 admin** —— `dir: "."` 可以是 qa-manager / bot-manager 等 manager 角色，
  用 `--profile <role>` 讓根目錄 SOUL 由該角色渲染（見上方 `--profile` 段）。
- 專案根 `AGENTS.md` 是所有 agent 共用規範的**來源**（子 agent 工作目錄根各有一份複本；落點見頂部單一權威）
  - 🔴 **SSOT：`AGENTS.md` 要改就改專案根那份，再重新分配到各 agent。**
    子 agent 的是**複本**，直接改子 agent 的會造成多份漂移。
- `skills/` 放全套 Skills（admin 擁有全部能力）
- `settings/mcp.json` 的 role 必須是 `admin`
- 非 admin agent 的 .kiro/ 在 `agents/{name}-agent/.kiro/`（不在根目錄）

**分配流程：**

```
1. git clone ark-agent-skills → {project}/skills/（共用倉庫）
2. 建立根目錄 .kiro/（管理者 workspace，skills/ 放全套）
3. 對每個 agent：
   a. 掃描 skills/ 下所有 SKILL.md 的 name + description
   b. 根據角色匹配適合的 Skills
   c. 複製到 agents/{name}-agent/.kiro/skills/{skill-name}/
```

**角色 → Skills 對應表：**

| 角色類型 | 建議 Skills | 說明 |
|---------|------------|------|
| Admin / CEO（根目錄 .kiro） | 全部 | 管理者擁有全套能力 |
| 全員必備（base_skills）| ark-grill-me, ark-superpowers, ark-spec-executor, ark-code-spec-validator, ark-wiki-engine, ark-prompt-spec-validator, ark-md-report, ark-html-report | 需求→文件→執行→驗證(code+prompt)→知識→報告（迴圈工程核心 + 產出）。權威清單見 `references/role-skills-map.md` 的 `base_skills:` |
| Leader / PM | ark-superpowers（plan／coauthor 模式）, ark-grill-me | 規劃+共筆+設計圖 |
| AI Dev | ark-skill-creator, ark-mcp-builder, ark-pipeline-recipes | Skill 開發+MCP+LLM |
| Coder / 全端 | ark-skill-creator, ark-quality-gates, ark-webapp-generator, ark-db-query | 開發+審查+全端 |
| QA / 測試 | ark-quality-gates | 品質保證 |
| DevOps | ark-docker-deploy, ark-env-doctor, ark-webapp-generator | 部署運維（排程已併入 webapp-generator） |
| 數據分析 | ark-db-query, ark-pipeline-recipes, ark-retention-analysis | 數據工程 |
| 市場研究 | ark-web-scraper, ark-pipeline-recipes | 資訊收集 |
| 報告產出 | ark-html-report, ark-html-dashboard, ark-pipeline-recipes | 視覺化 + 報表 |

**匹配邏輯：**

1. 根目錄 .kiro/skills/ → 全套（admin 全能力覆蓋）
2. 每個 agent 先分配「全員必備 base_skills」（見 references/role-skills-map.md）
3. 根據角色類型分配對應 Skills
4. 如角色跨多類型（如「全端 + DevOps」），合併兩組
5. 自訂角色 → 根據 SOUL.md 的 Core Mission 關鍵字匹配 Skill description
6. 每個 agent 最多 12 個 Skills（避免 context 過大）

**離線模式：** 如無法存取 GitHub，提示使用者手動 clone 或從本地已有的 `skills/` 複製。

### 11. settings/mcp.json（全域 MCP，選填）

當 MCP Server 需要跨多個 agent 共用時，放在 settings/mcp.json。
Agent 專屬的 MCP 直接寫在 agents/{role}.json 的 `mcpServers` 欄位。

```json
{
  "mcpServers": {
    "{server-name}": {
      "command": "{cmd}",
      "args": ["{args}"],
      "env": { "{KEY}": "${ENV_VAR}" }
    }
  }
}
```

---
