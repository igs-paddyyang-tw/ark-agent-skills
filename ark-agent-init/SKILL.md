---
name: ark-agent-init
description: |
  產出完整的 agent workspace 配置（steering、agents、prompts、skills、settings、
  knowledge、memory），根據使用者指定的角色自動生成。預設為全端工程師 +
  系統分析與設計師（SA/SD）。支援自訂角色：上網搜尋該角色的最佳實踐並整理成配置。
  同時產出多 AI CLI 的入口檔（.kiro/steering、CLAUDE.md、AGENTS.md），
  以單一真相來源（SSOT）連結，讓 Kiro CLI / Claude Code / Codex 等共用同一份人格與規範。
  使用此 Skill 當使用者提及 建立 agent 配置、初始化 agent、agent init、agent-init、
  建立 .kiro、產生 workspace、初始化 kiro 配置、kiro init、kiro-init、
  設定角色的 .kiro、幫我建 agent 配置、新增角色、workspace generator、
  建立開發環境、設定 AI 助手角色、多 CLI 入口、CLAUDE.md 連結、
  或任何需要產出 agent workspace 目錄結構的場景。
  也是 ark-agent-bot-builder／ark-agent-team-builder 的**下一步**：骨架產完後由本 skill 補人格。
  不適用於：bot 骨架請用 ark-agent-bot-builder；team daemon 骨架請用 ark-agent-team-builder。
metadata:
  schema_version: "1.2"
  status: active
  category: scaffolder
  form: instruction
  domain: general
  outputs:
    - format: code
      audience: ai
  author: paddyyang
  version: "2.6.2"
  updated: 2026-10-29
---

# ark-agent-init

根據角色產出完整 agent workspace 配置（`.kiro/` + 多 CLI 入口檔）。

> 🔴 **AGENTS.md 放哪（單一權威 —— 其他段落與 references 只引用這句，不自述）**：一律放 **workspace 根**。專案根一份＝**SSOT**；每個子 agent 的工作目錄根一份＝**複本**（與 ark_team_agent daemon 的落點一致）；`.kiro/steering/` **永遠不放** AGENTS.md（唯一例外：指向同層根那份的 symlink）。稽核：`python scripts/audit_agents_layout.py <project>`。

## 🎯 核心目標：打造「個人化成長五層」

本 skill 的產物不只是一堆設定檔 —— 它在為每個 agent **裝上五層能力**（v2.3.0 起由三引擎擴充；權威定義與目錄對照見 `references/five-layer-architecture.md`），讓 agent 既「個人化」又「會成長」。這是本 skill 一切輸出的設計意圖，實戰設定細節見下方與 `references/`。

| 層 | 落點 | 作用 | 本 skill 怎麼配 |
|------|------|------|----------------|
| 🧠 **大腦 BRAIN** | `.kiro/steering/`（`SOUL` 人格 · `BRAIN` 判準 · `CODE` · `USER` 畫像）＋ workspace 根 `AGENTS.md` 規範，always-on 常駐注入 | **個人化的根** —— 換一組 steering = 換一個 agent（決定它是誰、怎麼判斷、紅線在哪） | 依角色選模板渲染 SOUL；`--profile` 讓根目錄 manager 由指定角色渲染（§--profile） |
| 📝 **記憶 Memory** | `memory/`（四層：`BRAIN.md` 判準 → `MEMORY.md` 導覽 → `memory.md` 蒸餾 → `daily/`+`archive/` 流水） | **成長的時間軸** —— 記得經歷過什麼、踩過什麼坑 | 產 `memory/daily`+`archive` 骨架與 `memory.md` 四分節；蒸餾走 `memory-distill` 排程（見 `references/memory-architecture.md`，門檻 ark_team_agent ≥ 1.11.0） |
| 📚 **知識 Knowledge** | `knowledge/`（`raw` → ingest → `wiki` 四層搜尋；五類來源櫃） | **成長的能力庫** —— 查得到領域知識，問一次之後都在 | 依 `team.yaml` `knowledge_sources` 產五櫃骨架 + 自動補 `knowledge_search_order`（見 `references/knowledge-sources-map.md`） |
| 🖐️ **技能 Skill** | `.kiro/skills/<name>/`（上游 ark-agent-skills 複本）+ 套件內建 | **手腳** —— 跨專案共用的基本必要能力（怎麼做一件標準的事） | 依 `role-skills-map.md` 複製子集；更新走 `sync_skills`／`ark-skills-align` `mirror_sync`；修改只能提案回上游 |
| 🔌 **腳本 Script** | `scripts/`、bot 的根 `skills/` 業務模組、`mcp.json` 外部工具 | **外接工具** —— 綁本專案資料／主機／帳號的附屬客製能力 | 產 `scripts/` 骨架；被第二個專案需要 → 去寫死值後升格成技能回貢 |

> **一句話**：大腦給 agent「個性」、記憶給它「經歷」、知識庫給它「專業」、技能給它「手腳」、腳本給它「外接工具」。這也是 `assets/steering/BRAIN.md`「五層資源」準則的上層視角 —— BRAIN 範本管「agent 執行時怎麼用這五層」，本段管「建置時怎麼把它們裝起來」。
>
> **技能 vs 腳本**：換一個專案還用得上 → 技能；綁本專案資料、主機、帳號 → 腳本。skill 目錄底下的 `scripts/` 屬技能層。

> ✅ **BRAIN.md 由 build_kiro 產（2.5.0 起）**：`BRAIN.md` ＝ **五層判準**（共用，`assets/steering/BRAIN.md`）＋ **本角色知識背景**（`assets/steering/brain-roles/<role>.md`，選法同 ark_team_agent daemon：team.yaml `template` → instance 名 → role 對應），私有知識庫路徑依 instance 渲染；已存在不覆寫（policy once）。bot 型由 ark-agent-bot-builder 委派同一個函式產。
> 背景：bot 套件注入 BRAIN.md 卻不產它（nana-bot 手抄範本、帶 leader 私有路徑上線），team daemon 產的只有角色知識沒有判準 —— 同名兩種內容，2.5.0 統一成一份。

> **更名紀錄**：本 skill 原名 `ark-kiro-init`（v1.x），於 v2.0（2026-09-07）
> 更名為 `ark-agent-init` —— 因為它產出的不只是 Kiro 的 `.kiro/`，
> 而是「一份 agent workspace 給多個 AI CLI 共用」。舊觸發詞（kiro init / kiro-init）
> 保留向後相容。

## 觸發條件

- 「建立 agent 配置」、「初始化 agent」、「agent init」、「agent-init」
- 「建立 .kiro」、「產生 workspace」、「初始化 kiro 配置」（舊詞，相容保留）
- 「設定 {角色} 的 .kiro」、「幫我建 agent 配置」
- 「新增角色」、「kiro workspace」、「workspace generator」
- 「建立開發環境」、「設定 AI 助手」
- 「為 {name}-agent 配置 .kiro/」、「配置 agent 角色」
- 「多 CLI 入口」、「CLAUDE.md 連結」、「讓 Claude Code / Codex 共用 steering」

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
| 指定專業領域角色 | 查對應**角色包**：🎮 遊戲研發 → `role-templates-gamedev.md`；🌐 Web 工具開發 → `role-templates-webtool.md`；📈 AI/BI 分析 → `role-templates-aibi.md`（通用/跨類角色如 architect/fullstack-coder/qa 各包共用；aibi 資產一次性收在 `references/aibi/`）|
| 指定未知角色 | 上網搜尋 → 整理 → 產出 |

### `--profile <role>`：根目錄由指定 manager 角色渲染（v2.1）

```bash
python build_kiro.py team.yaml <out> --profile qa-manager
```

- **作用**：根目錄（`working_directory: "."`）的 manager SOUL 改由 `ark-agent-role-profile`
  渲染指定角色（含 `profile-sha256` 戳記），**不再預設 admin 人格**。
- **只影響根目錄 instance**；其餘 worker / leader 走原模板。
- **向後相容**：不給 `--profile` 時行為完全不變（根目錄走原本依 role 選模板的路徑）。
- **失敗處理**：角色不存在／render 腳本缺 → 印警告後退回內建模板，不中斷。
- **角色來源**：`ark-agent-role-profile/assets/roles/<role>.yaml`（如 `qa-manager`、`bot-manager`），
  也接受直接給 yaml 路徑。

> 🔴 **「根目錄即 manager」是一等公民**：`dir: "."` 的 instance 不一定是 admin。
> 用 `--profile` 讓它由對應的 manager 角色渲染（QA 團隊 → qa-manager、通用 bot → bot-manager）。

### daemon 自動生成 vs 手寫的邊界（建置時務必分清）

| 檔案 | 誰產 | 手寫會怎樣 |
|---|---|---|
| `.kiro/settings/mcp.json`、`steering/TEAM.md` | **daemon 依 team.yaml 生成** | **會被覆寫**（依 policy）—— 別手改，改 team.yaml |
| 各 workspace 根的 `AGENTS.md` | daemon 首次啟動產（policy `once`）；build_kiro 也給子 agent 產複本 | **不會**被覆寫 —— 可補工作區筆記；團隊規範改專案根那份再分配 |
| `SOUL.md`、`MEMORY.md`、`USER.md`、`CODE.md` | **手建**（或 `--profile` 渲染 SOUL） | daemon 不生，要自己建 |
| `BRAIN.md` | **build_kiro 產**（判準＋角色段；team daemon 也會產但只有角色段 —— 先跑 build_kiro） | policy once，手改會保留 |

> 踩過的坑：手寫根層 mcp.json／TEAM.md 被 daemon 覆寫，以為設定沒生效。

---

## 產出結構

```
{target}/
├── AGENTS.md                          # 🔴 全隊共用規範 SSOT —— 只在專案根一份
│                                      #   （根目錄 instance 直接載入這份；steering/ 不再產 AGENTS.md）
├── .kiro/                             # 根目錄 workspace = team-spec 的 entry instance
│   │                                  #   🔴 不預設是 admin —— 可為 manager（用 --profile <role> 渲染）
│   ├── agents/{entry}.json            #   entry 角色定義（prompt→file://../../.kiro/steering/SOUL.md）
│   ├── prompts/{prompt-1}.md
│   ├── settings/mcp.json              #   entry MCP 設定
│   ├── skills/                        #   🔴 從 skills/ 複製子集（非 symlink —— symlink 跨機斷鏈）
│   │                                  #      靠 sync_skills.py 同步更新，gitignore 排除
│   └── steering/
│       ├── CODE.md                    #   程式碼規範（fileMatch）
│       ├── BRAIN.md                   #   🧠 五層判準＋本角色知識背景（build_kiro 產，once）
│       ├── MEMORY.md                  #   entry 記憶
│       ├── SOUL.md                    #   人格（--profile 給定則由 role-profile 渲染，含 sha 戳記）
│       ├── USER.md                    #   使用者百科
│       └── TEAM.md                    #   團隊運作規範（inclusion: manual；daemon 覆寫）
│                                      #   🔴 steering/ 無 AGENTS.md（用專案根那份）
│
├── skills/                            # 共用 Skills 倉庫（git clone ark-agent-skills）
│   └── ...（全部 Skills）
│
├── agents/                            # 各 agent 工作目錄
│   └── {name}-agent/
│       ├── AGENTS.md                  #   複本（wd 根；根那份是 SSOT）—— 見頂部單一權威
│       ├── .kiro/
│       │   ├── agents/{role}.json     #   prompt→file://../../.kiro/steering/SOUL.md（基準是 .kiro/agents/，回自己 workspace 根）
│       │   ├── prompts/{prompt}.md
│       │   ├── settings/mcp.json
│       │   ├── skills/{skill}/        #   從 skills/ 複製子集（非 symlink；sync 更新）
│       │   └── steering/
│       │       ├── CODE.md            #   🔴 steering/ 無 AGENTS.md
│       │       ├── BRAIN.md           #   🧠 五層判準＋本角色知識背景（build_kiro 產，once）
│       │       ├── MEMORY.md
│       │       ├── SOUL.md            #   角色專屬
│       │       ├── USER.md
│       │       └── TEAM.md            #   daemon 產生
│       └── memory/{daily,archive}/    #   agent 私有記憶（歸檔在 memory/archive/）
│
├── knowledge/                         # 團隊知識庫（依產出來源分櫃）
│   ├── shared/                        #   🔴 全隊共用 —— wiki 引擎與 bot 啟動讀這層
│   │   ├── {schema,index,log}.md      #      少一層 shared/ 會靜默失效（記過四次）
│   │   └── {wiki,raw}/
│   └── {instance}/                    #   各 instance 私有知識（agent.json 指 ./knowledge/{instance}）
│       ├── {schema,index,log}.md
│       └── {wiki,raw}/
│
├── memory/                            # 團隊記憶
│   ├── daily/                         #   每日對話（bot 寫）
│   └── archive/                       #   🔴 MEMORY 歸檔（1.8.1 起；非 knowledge/raw/memory-archive）
│
├── artifacts/{reports,sim,perf,triage}/ # 🔴 產出落點（非 output/）
├── docs/                              # 團隊文件
├── team.yaml                          # 團隊配置
├── scheduler.yaml                     # 排程
├── start.py                           # 啟動腳本
└── .env                               # 環境變數
```

> 🔴 **skills 是複本不是 symlink**：symlink 跨機／跨 OS 會斷鏈，改用「複製 + `sync_skills.py`
> 同步版本更新」，並 gitignore 排除 `.kiro/skills/`（靠 sync 重建，不進版控）。

> **注意：** `product.md`、`tech.md`、`structure.md` 不在 init 預設產出中。
> 這些是專案特定檔案，由使用者依需求手動建立（或後續用 ark-superpowers 產出）。
> 預設只產出 5 個核心 steering 檔案，確保最小可用。

---

## 🔗 多 AI CLI 入口（v2.0 新增）

不同的 AI CLI 各自預設讀**不同檔名**的入口檔。若你的專案會被多個 CLI 使用
（例如同時用 Kiro CLI 開發、用 Claude Code / Codex 協作），要讓它們**共用同一份
人格與規範**，避免三份檔案各自漂移。做法是**單一真相來源（SSOT）+ 連結**。

> 🧭 **兩個維度，別混**（與 `ark-agent-cli` 的分工）：
> - **入口維度（本 skill）**：agent 專案該產哪些 CLI 的**設定入口檔**（給 CLI *讀*人格）。
> - **呼叫維度（`ark-agent-cli`）**：執行期該把哪個 CLI 當 **backend 呼叫**（*用* CLI 做事）。
>
> 同一工具可能同時是兩者（kiro / claude / gemini / codex 四個交集），
> 也可能只是入口維度（Cursor / Copilot 只讀設定，**不是**可程式呼叫的 backend）。

### 各 CLI 預設讀哪個檔案

| AI CLI | 預設入口檔（repo root，除非另註） | 載入時機 | 可當 agent-cli backend？ |
|--------|-----------------------------------|----------|:---:|
| **Kiro CLI** | `.kiro/steering/*.md`（`AGENTS.md`/`SOUL.md`/`MEMORY.md`…，依 `inclusion` 決定） | 每次對話自動載入 always 檔 | ✅ `kiro` |
| **Claude Code** | `CLAUDE.md`（不原生讀 AGENTS.md；支援 `@路徑` 匯入，最多 4 層、相對於匯入它的檔案） | 每次 session 開頭 | ✅ `claude` |
| **Codex CLI**（OpenAI） | `AGENTS.md`（專案根往下每層一份：`AGENTS.override.md` → `AGENTS.md` → fallback 檔名；**無匯入語法**；合計上限 32 KiB） | 每次 session 開頭 | ✅ `codex` |
| **Gemini CLI** | `GEMINI.md`（可用 `context.fileName` 改讀 `AGENTS.md`） | 每次 session 開頭 | ✅ `gemini` |
| **Cursor** | `.cursor/rules/`（或舊版 `.cursorrules`） | 依規則檔 | ❌ IDE 外掛 |
| **GitHub Copilot** | `.github/copilot-instructions.md` | 依設定 | ❌ IDE 外掛 |

> 💡 **`AGENTS.md` 已是事實上的跨工具通用標準** —— Codex / Cursor / Gemini / 多數
> coding agent 都會讀 repo root 的 `AGENTS.md`。Claude Code 是主要例外（讀 `CLAUDE.md`）。

> 🔗 **接力關係**：本 skill 產的入口檔是 CLI **讀**人格的來源；若要在**執行期程式化
> 呼叫**這些 CLI（kiro/claude/gemini/codex，如 bot/team 的 LLM backend），用
> `ark-agent-cli`（統一 `ArkAgentCli.call(backend, prompt)` → `CliResult`）。
> 兩者是「配置 → 執行」的接力：init 產設定檔、agent-cli 呼叫讀了那些設定檔的 CLI。


### SSOT 策略（2.6.0：匯入取代 symlink）

以 **`AGENTS.md`（workspace 根）為 Ark Agent 架構與規範的單一來源**，各工具這樣讀到它：

| 工具 | 做法 | 為什麼 |
|---|---|---|
| **Codex** | 直接讀 `AGENTS.md`，**不建 `CODEX.md`** | Codex 原生讀 AGENTS.md；同層有 AGENTS.md 時 fallback 檔名讀不到 → CODEX.md 無效。無匯入語法 → AGENTS.md 要**自成一體**（架構說明直接寫進去），渲染後 < 32 KiB（build_kiro 測試守） |
| **Claude Code** | `CLAUDE.md` 第一行 `@AGENTS.md`（再匯入 BRAIN／MEMORY），下方只寫 Claude 專屬；範本 `assets/CLAUDE.md` | 官方建議的寫法；比 symlink 好：Windows 不需特權、Claude 專屬內容有地方放。🔴 不在 CLAUDE.md 重寫 AGENTS 規則（實例：nana-bot 的 CLAUDE.md 摘要與 AGENTS.md 漂移成互相矛盾） |
| **Kiro** | `.kiro/steering/` 自動載入；需要時放**指回根的 symlink** `.kiro/steering/AGENTS.md → ../../AGENTS.md` | 實體複本會兩份並存漂移（`audit_agents_layout.py` 認得指回根的 symlink） |
| **Gemini 等** | 設定 `context.fileName` 改讀 `AGENTS.md` | — |

```bash
# build_kiro 已產：專案根 AGENTS.md（assets/AGENTS.md 渲染）＋ CLAUDE.md（assets/CLAUDE.md）—— 已存在不覆寫
# 選配：讓 Kiro 透過 steering 也讀到同一份
ln -sf ../../AGENTS.md .kiro/steering/AGENTS.md
```

> 🔴 **判準**：一份事實寫多處，其中一處一定會被忘記更新。入口檔只做「指向同一份」，
> 不做「各自摘要」；工具專屬差異集中在 AGENTS.md「各工具入口」節與 CLAUDE.md 專屬段。

### Kiro 的分層對應（本 skill 的特殊性）

Kiro 的 steering 是**多檔 + `inclusion` 分層**，比單一 `AGENTS.md` 表達力強：

| Kiro steering 檔 | `inclusion` | 對應到單一入口檔時 |
|------------------|-------------|---------------------|
| `AGENTS.md` | always | → 併入 root `AGENTS.md` / `CLAUDE.md` 的「通用規範」段 |
| `SOUL.md` | always | → 併入「角色人格」段 |
| `TEAM.md` | **manual** | → **不併入** always 入口檔（團隊派工規範，只在團隊場景載入） |
| `MEMORY.md` | always | → **記憶導覽 + 判準級里程碑**（可獨立，不一定塞進 CLAUDE.md；事件流水不放這裡） |

> 💡 產出多 CLI 入口時，**只把 always 層併進 `CLAUDE.md`/`AGENTS.md`**；
> `inclusion: manual` 的 `TEAM.md` 不要併 —— 否則非團隊的 CLI session 會吃到
> 用不到的派工規範 context。

---

### 知識庫五件套（每個 agent 必有）

| 檔案 | 用途 | 規則 |
|------|------|------|
| `schema.md` | 規則定義 | 定義 frontmatter 欄位、操作規則、適合存放的知識類型 |
| `index.md` | 索引目錄 | 每次修改 wiki 必須同步更新 |
| `log.md` | 操作日誌 | **append-only**，禁止刪除舊記錄 |
| `raw/` | 唯讀原始資料 | LLM 只讀不改，ingest 工具處理 |
| `wiki/overview.md` | 知識庫概覽 | 含 frontmatter（title/type/tags/created/updated/status） |

> 🔴 **團隊級 knowledge 要建 `knowledge/shared/` 層**（`shared/wiki/` + `shared/raw/`
> + `schema/index/log`）—— Wiki 引擎（ark-wiki-engine）與 bot 啟動實際讀的是 `shared/`，
> 不是扁平的 `knowledge/wiki/`。少一層 `shared/` 會讓索引讀不到且**不報錯**。
> 另 MEMORY 歸檔落 **`memory/archive/`**（1.8.1 起 —— 記憶歸記憶，不進 knowledge；
> 舊 `knowledge/raw/memory-archive/` 已作廢並遷出）。
> 詳見 `references/architecture-drift-feedback.md`。

### 五類知識來源（L1–L5，v2.4 補）

除了 private + shared，team 可依定位納入外部/業務來源。權威定義見
**`references/knowledge-sources-map.md`**：

| 代號 | 來源 | 目錄/位置 | 進 search_order？ |
|------|------|-----------|:----------------:|
| private | 各 instance 私有 | `knowledge/<instance>/` 或 `agents/<name>/knowledge/` | ✅ 最前 |
| L2 產品庫 | 專案產品知識（層名**依產品**，`hoyeah` 只是案例） | `knowledge/<product>/` | ✅ 次之 |
| L1 github | 外部 repo 蒸餾來源 | `$ARK_GITHUB_ROOT/`（`github-sources.yaml`） | ✅ 再次 |
| shared | 跨 agent 共用 | `knowledge/shared/` | ✅ 最後 |
| L5 weknora | 外部 RAG（ark-weknora-cli） | 外部服務 | ❌ **不進** |

- **team.yaml 宣告 `knowledge_sources`**（如 `[private, hoyeah, github, shared, weknora]`）→
  `build_kiro.py` 依此建目錄骨架，並**自動寫 `knowledge_search_order`**（信任度遞減
  `private → 產品 → github → shared`，weknora 排除）。未宣告 → 預設 `[private, shared]`。
- L1 github 統一 schema 見 `references/github-sources.md`（`ARK_GITHUB_ROOT`，禁寫死路徑）。
- L5 weknora 接入見 `references/weknora-checklist.md`（`.env` 變數；不進 search_order）。

> 🔴 **品質檢查（validate 驗）**：team.yaml 宣告 knowledge_sources 時，`build_kiro.py --validate` 會查
> ① 有 `knowledge_search_order` 且涵蓋非 weknora 的來源 ② weknora 不在 search_order 內
> ③ shared/產品櫃目錄存在、含 github 則 `github-sources.yaml` 存在。

### memory/ 目錄與四層記憶分工（每個 agent 必有；2.2.0 起 build_kiro 自動建）

> 🔴 **權威參考：`references/memory-architecture.md`**（ark_team_agent ≥ 1.11.0 為記憶規範定版）。
> 新建照 §2 直接產；既有部署照 §4 遷移（順序不可逆：先接蒸餾、再瘦身）。

| 層 | 落點 | 誰寫 | 進 context |
|---|---|---|---|
| 判準 | `steering/BRAIN.md` | ✋ 人 | ✅ |
| 導覽 + 判準級里程碑 | `steering/MEMORY.md`（保持瘦身） | ✋ 人 | ✅ |
| 持久事實 | `memory/memory.md`（四分節、≤ 2000 tokens） | 🤖 `memory-distill` 排程蒸餾 | 🔸 |
| 事件流水 | `memory/daily/YYYY-MM-DD.md` | 🤖 bot 自動／✋ team 收尾手寫 | ❌ |
| 舊事件 | `memory/archive/YYYY-MM.md` | 🤖 `_builtin:memory-consolidate` | ❌ |

- `dir="."` 的 manager → 根層 `memory/`；子 agent → 各自 `agents/<name>/memory/`
- build_kiro 產 `memory/daily/`、`memory/archive/`（`.gitkeep`）+ `memory/memory.md` 四分節骨架（`assets/memory/memory.md`），冪等不覆寫
- 規則只寫在根 `AGENTS.md`「記憶怎麼用」（**單一權威**），BRAIN／MEMORY／SOUL 只引用
- 🔴 **不再使用「每完成一個段落更新 MEMORY.md」** —— 那句讓 always-on 的 MEMORY.md 變成事件流水（實測 73 KB）
- `--validate` 會對 MEMORY.md > 20 KB、日期事件分節 > 5、缺 memory/ 骨架、舊規範殘留給 ⚠️

### artifacts/ 產出目錄（取代舊 output/，v2.0 更新）

agent 產出（報告等）放 `artifacts/`（底下可分 `reports/`），**不再用 `output/`**
—— 與套件 1.2.19 起的骨架一致。`.gitkeep` 骨架：`memory/` + `artifacts/` + `scripts/`。

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

**Skills 來源：** 從 `https://github.com/igs-paddyyang-tw/ark-kiro-skills` clone 到**專案根目錄的 `skills/`**。

**Clone 流程：**

```bash
# Clone 到專案根目錄（與 agents/ 同層）
git clone https://github.com/igs-paddyyang-tw/ark-kiro-skills.git skills/

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
1. git clone ark-kiro-skills → {project}/skills/（共用倉庫）
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
| Leader / PM | ark-project-planning, ark-doc-coauthoring, ark-superpowers | 規劃+共筆+設計圖 |
| AI Dev | ark-skill-creator, ark-mcp-builder, ark-pipeline-recipes | Skill 開發+MCP+LLM |
| Coder / 全端 | ark-skill-creator, ark-code-review, ark-webapp-generator, ark-db-query | 開發+審查+全端 |
| QA / 測試 | ark-test-runner, ark-security-audit, ark-code-review | 品質保證 |
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

產出後自動驗證（context 佔比可用 Kiro 內建量測或人工估算）：

- [ ] `agents/{role}.json` 有 name/description/prompt/tools/resources/allowedTools
- [ ] `agents/{role}.json` 有 knowledgeBase resource 指向 knowledge/
- [ ] `agents/{role}.json` 有 model（建議 "auto"）+ welcomeMessage
- [ ] 專案根 `AGENTS.md` 有「⚠️ reply 必用」+ MCP 工具表 + 編號選項 + 終端回饋 + SDD 流程；`audit_agents_layout.py` 通過
- [ ] `steering/CODE.md` 有程式碼規範（Python 專案時）
- [ ] `steering/MEMORY.md` 是導覽骨架（記憶住在哪 + 快照 + 里程碑索引），**無「每完成一個段落」**
- [ ] 每個 agent 有 `memory/daily/`、`memory/archive/`、`memory/memory.md` 四分節（`--validate` 無記憶 ⚠️）
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
- [ ] `artifacts/` 目錄存在（**不是** `output/`，套件 1.2.19 起已改）

---

## 完成回報格式

```
✅ .kiro workspace 已建立

📁 產出清單：
- .kiro/agents/{role}.json
- AGENTS.md（workspace 根；全域行為準則）
- .kiro/steering/CODE.md（程式碼規範）
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
- artifacts/

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

> 🔴 **本表必須與 `assets/steering/` 目錄實況一致** —— 維護時逐一核對檔名。
> 曾經列了四個不存在的檔名（AGENTS/USER/SOUL/MEMORY.md），照著走的人會發現「說要 copy 的檔案不在」。
> （註：原文曾引用 `test_scaffold.py` 自動驗此表，該測試現不存在，改為人工核對。）

| 檔案 | 說明 |
|------|------|
| `BRAIN.md` | 五層判準段（資源分工 + 技能／腳本分界 + 四層記憶摘要，標 AGENTS.md 為單一權威；inclusion: always）＋ `{private_kb}`／`{role_section}` 佔位符 |
| `brain-roles/<role>.md` | 角色知識背景（admin／ai-dev／coder／data／leader／librarian／market／qa／report／strategy，源自 ark_team_agent 角色範本；leader 含品質護欄）＋ `_default.md` 待填骨架 |
| `CODE.md` | Kiro CLI 行為指南（程式碼規範，fileMatch: *.py） |
| `MEMORY-template.md` | 記憶**導覽**骨架（記憶住在哪 + 快照 + 里程碑索引 + 待辦；build_kiro 產 MEMORY.md 用它） |
| `SOUL-root.md` | 根目錄／預設角色：通用 AI 助手 |
| `SOUL-admin.md` | admin 角色（服務管理，不接業務） |
| `SOUL-leader.md` | leader 角色（需求拆解、派工、收斂） |
| `SOUL-worker.md` | worker 角色（執行、回報） |
| `TEAM.md` · `TEAM-template.md` | 團隊運作規範（inclusion: manual，不併進 always 入口檔） |

> `assets/memory/memory.md`：`memory/memory.md` 四分節骨架（環境慣例／工具怪癖／人與偏好／進行中長期事項），build_kiro 複製到每個 agent。

> ✅ `AGENTS.md`、`CLAUDE.md` 範本 2.6.0 起在 `assets/`（專案根入口檔，build_kiro 產）。
> ⚠️ 尚缺 `USER.md` 的預設 asset（待辦，見 `docs/plans/ark-agent-skills-bot-builder-optimization-plan.md` 的 P1-3）。

### references/（按需載入）

| 檔案 | 說明 |
|------|------|
| `role-templates.md` | 已知角色索引（10 種內建角色） |
| `role-templates-gamedev.md` | 🎮 **game dev 角色包**（game-planner / math-designer / liveops / game-analyst 等，遊戲研發專業角色定位 + 交付物 + prompts 配方）|
| `role-templates-webtool.md` | 🌐 **web tool 角色包**（frontend / backend / ui-designer 等，Web 工具／內部後台／webbot 應用開發角色定位 + 交付物 + prompts 配方）|
| `role-templates-aibi.md` | 📈 **AI/BI 角色包**（aibi-manager / bi-lead / semantic-keeper / query-analyst / insight-investigator / report-narrator / pulse-monitor / viz-builder，AI/BI 網站分析維運團隊；語意契約先行 + 證據等級三態）|
| `aibi/roles/*.yaml` | 📈 aibi **8 個角色 profile**（一次性收進 init 的參考資產；原設計在 ark-agent-role-profile，供其 lint/render 當 `--roles-dir`）|
| `aibi/aibi-team-pattern.yaml` | 📈 aibi **team pattern**（一次性收進 init 的參考資產；原設計在 ark-agent-team-design，供 gen_team/team_spec_lint 使用）|
| `role-skills-map.md` | 角色 → Skills 對應表 |
| `role-prompts-map.md` | 🆕 角色 → Prompts 對應表（`role_prompts:` 錨點，ops/work 雙層；`_build_prompts` 讀此表非硬編）|
| `skill-selection-map.md` | 🗺️ **Skill 選用地圖**（問題類型 → 用哪個 skill / 怎麼串鏈）—— 放進專案 AGENTS.md，教大腦調度既有武器 |
| `knowledge-schema-template.md` | 知識庫 schema 模板 |
| `knowledge-sources-map.md` | 🆕 **五類知識來源地圖**（L1 github / L2 產品庫 / private / shared / L5 weknora 定義 + search_order 信任度序 + private 命名機制；B1）|
| `knowledge-governance-scoring.md` | 🆕 **知識庫治理評分標準**（100 分 9 維度 A-I + 三層資源分工 + 紅線；萃取自 knowledge-management-spec）|
| `github-sources.md` | 🆕 **L1 github 統一 schema**（`ARK_GITHUB_ROOT` + repos[]，git pull→diff→蒸餾流程，取代寫死路徑；B3）|
| `weknora-checklist.md` | 🆕 **L5 weknora 接入 checklist**（.env 變數 / agent-chat / 不進 search_order；B5）|
| `prompt-schema-v1.md` | 🆕 提詞資產 frontmatter 契約（prompts/ 的 ops/work 雙層 + 範例段 + 模板變數）|
| `defaults/README.md` | 預設角色說明 |
| `five-layer-architecture.md` | 🆕 **五層架構**（大腦／記憶／知識庫／技能／腳本）定義、技能 vs 腳本分界與升格規則、team／bot 標準目錄對照、檢核清單 |
| `memory-architecture.md` | 🧠 **記憶架構四層分工**（ark_team_agent ≥ 1.11.0 定版）：新建規範 + 既有部署遷移 SOP（先接 memory-distill 再瘦身 MEMORY.md）+ 驗證 + 風險 —— 改記憶相關範本前必讀 |
| `architecture-drift-feedback.md` | 🔴 **模板 vs 演化實例的三項缺口回饋**（knowledge/shared 層、memory/ 目錄、artifacts/）—— 維護本 skill 前必讀 |


---

## Workshop 引導（agent-team-workshop）

本 Skill 對應 Workshop Step 2：為每個 agent 配置 .kiro/。

### 觸發提詞（逐一配置）

```
為 pm-agent 配置 .kiro/，角色是專案經理
```

```
為 coder-agent 配置 .kiro/，角色是全端開發者
```

```
為 qa-agent 配置 .kiro/，角色是 QA 測試工程師
```

### 批次配置（進階）

```
為 ai-dev-agent 配置 .kiro/，角色是 AI 工程師，
專精 LLM 整合、Prompt Engineering、MCP 開發，
部署 ark-mcp-builder 和 ark-pipeline-recipes（llm-tools 食譜）Skills
```

### 預期產出（每個 agent）

- `agents/{name}-agent/.kiro/steering/SOUL.md` — 角色定義
- `agents/{name}-agent/AGENTS.md` — 行為準則（複本，wd 根）
- `agents/{name}-agent/.kiro/steering/MEMORY.md` — 記憶骨架
- `agents/{name}-agent/.kiro/agents/{role}.json` — Agent 配置

### 下一步

全部 agent 配置完成後：
- 單 bot（ark_bot_agent 消費端）→ `ark-agent-bot-builder`
- 團隊 daemon（ark_team_agent）→ `ark-agent-team-builder`
- 獨立 web/TG/排程應用（非套件）→ `ark-webapp-generator`

### 卡關時

- 只配 leader + 1 個 worker 即可（最小可用）
- 不確定角色描述 → 直接說「用預設」
- 目錄不存在 → 先確認 Step 1 已完成
