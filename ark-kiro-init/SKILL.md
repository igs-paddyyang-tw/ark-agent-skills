---
name: ark-kiro-init
description: |
  產出完整的 .kiro/ workspace 配置（agents、steering、prompts、skills、settings），
  根據使用者指定的角色自動生成。預設為全端工程師 + 系統分析與設計師（SA/SD）。
  支援自訂角色：上網搜尋該角色的最佳實踐並整理成配置。
  使用此 Skill 當使用者提及 建立 .kiro、產生 workspace、初始化 kiro 配置、
  kiro init、kiro-init、設定角色的 .kiro、幫我建 agent 配置、新增角色、
  kiro workspace、建立開發環境、設定 AI 助手角色、
  或任何需要產出 .kiro 目錄結構的場景。
metadata:
  author: paddyyang
  version: "1.1"
  updated: 2026-05-15
---

# ark-kiro-init

根據角色產出完整 `.kiro/` workspace 配置。

## 觸發條件

- 「建立 .kiro」、「產生 workspace」、「初始化 kiro 配置」
- 「設定 {角色} 的 .kiro」、「幫我建 agent 配置」
- 「新增角色」、「kiro workspace」、「workspace generator」
- 「建立開發環境」、「設定 AI 助手」

---

## 互動流程

```
1. 確認角色 → 使用者指定 or 預設（全端 + SA/SD）
2. 確認目標目錄 → 預設當前工作目錄
3. 若為自訂角色 → 上網搜尋最佳實踐
4. 產出配置 → 依模板填充所有檔案
5. 摘要回報 → 列出產出清單 + context 佔比估算
```

### 角色判斷

| 情境 | 動作 |
|------|------|
| 未指定角色 | 使用預設：全端工程師 + SA/SD（從 `references/defaults/` 載入） |
| 指定 admin | 產出 admin 專用 SOUL.md（服務管理、不接業務） |
| 指定已知角色 | 從 `references/role-templates.md` 查對應模板 |
| 指定未知角色 | 上網搜尋 → 整理 → 產出 |

---

## 產出結構

```
{target}/
├── .kiro/                             # Kiro workspace 配置
│   ├── agents/{role}.json
│   ├── prompts/{prompt-1}.md
│   ├── prompts/{prompt-2}.md
│   ├── settings/mcp.json
│   ├── skills/{skill-name}/SKILL.md
│   └── steering/
│       ├── AGENTS.md               # 全域行為準則（怎麼做事，永遠載入）
│       ├── KIRO.md                 # Kiro CLI 行為指南（fileMatch: *.py）
│       ├── MEMORY.md               # 專案記憶（目前在哪）
│       ├── SOUL.md                 # 角色定義（你是誰）
│       ├── USER.md                 # 使用者百科（關於你的筆記本）
│       └── TEAM.md                 # 團隊運作規範（通訊規則 + MCP 工具）
├── docs/.gitkeep                      # 工作文件
├── output/.gitkeep                    # 任務產出
└── knowledge/                         # 私有知識庫（Schema v3.0）
    ├── schema.md                      # 規則定義
    ├── index.md                       # 索引目錄（必須同步）
    ├── log.md                         # 操作日誌（append-only）
    ├── raw/.gitkeep                   # 唯讀原始資料
    └── wiki/
        └── overview.md                # 知識庫概覽
```

> **注意：** `product.md`、`tech.md`、`structure.md` 不在 init 預設產出中。
> 這些是專案特定檔案，由使用者依需求手動建立（或後續用 ark-superpowers 產出）。
> 預設只產出 5 個核心 steering 檔案，確保最小可用。

### 知識庫五件套（每個 agent 必有）

| 檔案 | 用途 | 規則 |
|------|------|------|
| `schema.md` | 規則定義 | 定義 frontmatter 欄位、操作規則、適合存放的知識類型 |
| `index.md` | 索引目錄 | 每次修改 wiki 必須同步更新 |
| `log.md` | 操作日誌 | **append-only**，禁止刪除舊記錄 |
| `raw/` | 唯讀原始資料 | LLM 只讀不改，ingest 工具處理 |
| `wiki/overview.md` | 知識庫概覽 | 含 frontmatter（title/type/tags/created/updated/status） |

### schema.md 產出規則

根據角色自動填充「適合存放的知識」段落：
- **Admin** → 服務管理 SOP、crash 處理、版本發布、跨團隊隔離
- Leader → 需求分析筆記、派工策略、驗收標準
- AI Dev → LLM API 踩坑、Prompt pattern、RAG 策略
- Coder → 框架 pattern、DB 設計、測試策略
- QA → Bug pattern、測試技巧、CI/CD 整合
- 自訂角色 → 根據搜尋結果推斷

---

## 各檔案產出規則

### 1. agents/{role}.json

依 Kiro 官方 Agent Configuration 格式：

```json
{
  "name": "{role-id}",
  "description": "{一句話描述}",
  "prompt": "file://.kiro/steering/SOUL.md",
  "model": "claude-sonnet-4",
  "tools": ["*"],
  "allowedTools": ["*"],
  "resources": [
    "file://.kiro/steering/**/*.md",
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

### 2. steering/AGENTS.md（全域行為準則）

定義「怎麼做事」— 放在根目錄或 steering/ 下，Kiro 永遠自動載入（不需在 resources 引用）。

```markdown
# {Role} 共用規範

> All tools are trusted. 每完成一個段落更新 MEMORY.md。

## 工具使用規則
- fs_write 必填：command + path（絕對路徑）+ 對應內容欄位
- 不確定路徑先用 fs_read 查目錄結構
- 複雜任務逐一寫檔，每完成一個確認後再寫下一個

## 回報格式
✅ 工作成果：{做了什麼}
📚 學習結果：{如有新知識}
⚠️ 阻礙：{如有}
📋 下一步：{建議}

## 目錄規範
（引用 structure.md 的核心規則）

## 學習 SOP
1. web_search × 2-3 次（不同角度）
2. web_fetch 深讀 1-2 篇
3. 整理 → knowledge/wiki/*.md
4. 更新 MEMORY.md
5. 回覆重點摘要
```

### 3. steering/MEMORY.md（專案記憶）

定義「目前在哪」— Kiro 每次對話自動載入，跨對話保持上下文。

```markdown
# 🧠 {Project} 專案記憶

> Kiro 每次對話自動載入。每完成一個段落必須更新。
> 歸檔規則：> 2 週的段落移到 knowledge/ 目錄。

## 專案快照
- **版本：** 0.1.0
- **狀態：** 初始化
- **技術棧：** （引用 tech.md）

## 待辦
### 高優先
- [ ] （使用者填入）

### 低優先
- [ ] （使用者填入）

## 近期進度
（Kiro 自動累積，格式：## YYYY-MM-DD — 一句話標題）
```

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

## 自訂角色搜尋流程

當角色不在已知清單時：

1. **搜尋技術棧**：`{role} tech stack tools 2024`
2. **搜尋最佳實踐**：`{role} best practices guidelines`
3. **搜尋目錄結構**：`{role} project structure convention`
4. **搜尋品質指標**：`{role} KPI metrics quality`

將搜尋結果整理為：
- 核心職責（3-5 條）→ Mission 段
- 技術棧 → tech.md
- 領域規範 → {domain}.md
- 常用工具 → mcp.json
- 品質指標 → Metrics 段

產出前告知使用者搜尋結果摘要，確認後再寫入檔案。

---

## 品質檢查

產出後自動驗證（可用 `scripts/estimate_context.py` 量測 context 佔比）：

- [ ] `agents/{role}.json` 有 name/description/prompt/tools/resources/allowedTools
- [ ] `agents/{role}.json` 有 knowledgeBase resource 指向 knowledge/
- [ ] `steering/AGENTS.md` 有工具規則 + 回報格式 + 學習 SOP + AI 開發流程 + 修改追蹤規範
- [ ] `steering/KIRO.md` 有程式碼規範（Python 專案時）
- [ ] `steering/MEMORY.md` 有專案快照 + 待辦 + 近期進度結構
- [ ] `SOUL.md` 包含八段式全部 8 個段落
- [ ] `USER.md` 有個人特徵 + 溝通風格 + 目標 + 習慣四段
- [ ] `TEAM.md` 有團隊成員 + 通訊規則 + 成員管理規範
- [ ] `prompts/` 至少 2 個模板
- [ ] `settings/mcp.json` JSON 格式正確（如有）
- [ ] resources 引用的檔案全部存在
- [ ] 所有 always steering 總量 ≤ 50KB（≈ 14K tokens ≈ 7% context）
- [ ] `knowledge/` 有五件套：schema.md + index.md + log.md + raw/ + wiki/overview.md
- [ ] `knowledge/schema.md` 有角色客製化「適合存放的知識」段落
- [ ] `docs/` 目錄存在
- [ ] `output/` 目錄存在

---

## 完成回報格式

```
✅ .kiro workspace 已建立

📁 產出清單：
- .kiro/agents/{role}.json
- .kiro/steering/AGENTS.md（全域行為準則）
- .kiro/steering/KIRO.md（程式碼規範）
- .kiro/steering/MEMORY.md（專案記憶）
- .kiro/steering/SOUL.md（{size} KB）
- .kiro/steering/USER.md（使用者百科）
- .kiro/steering/TEAM.md（團隊運作規範）
- .kiro/prompts/{name-1}.md
- .kiro/prompts/{name-2}.md
- .kiro/skills/{name}/SKILL.md
- .kiro/settings/mcp.json
- knowledge/（五件套：schema + index + log + raw/ + wiki/）
- docs/
- output/

📊 Context 佔比估算：~{total_kb} KB ≈ {tokens} tokens ≈ {percent}%

💡 下一步（選用）：
- 建立 product.md（產品概覽）
- 建立 tech.md（技術棧規範）
- 建立 structure.md（目錄結構）
```

---

## 注意事項

- 目標目錄已有 `.kiro/` 時，只補缺少的檔案，不覆寫已存在的
- 目標目錄已有 `knowledge/` 時，只補缺少的五件套，不覆寫已存在的
- steering 總量控制在 50KB 以內（context 佔比 < 6%）
- 預設角色不需要網路，離線可用
- 自訂角色需要網路搜尋，無網路時提示使用者手動提供資訊
- `product.md`、`tech.md`、`structure.md` 不在預設產出中，使用者依需求手動建立
- knowledge/schema.md 的「適合存放的知識」段落根據角色自動客製化

---

## 附帶資源

### assets/steering/（預設模板，直接 copy）

| 檔案 | 說明 |
|------|------|
| `AGENTS.md` | 全域行為準則（含 AI 開發流程 + 知識庫規則） |
| `KIRO.md` | Kiro CLI 行為指南（程式碼規範，fileMatch: *.py） |
| `MEMORY.md` | 專案記憶骨架（快照 + 待辦 + 進度） |
| `USER.md` | 使用者百科骨架（空白待填） |
| `SOUL.md` | 預設角色：全端 + SA/SD（八段式） |
| `TEAM.md` | 團隊運作規範（通訊規則 + MCP 工具 + 協作流程 + 成員管理） |

### references/（按需載入）

| 檔案 | 說明 |
|------|------|
| `role-templates.md` | 已知角色索引（10 種內建角色） |
| `defaults/README.md` | 預設角色說明 |
