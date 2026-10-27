# Agent 五層架構（大腦・記憶・知識庫・技能・腳本）× 目錄對照

> v2.3.0 起本 skill 的設計意圖由「三引擎」擴為**五層**：在大腦／記憶／知識之外，
> 把「會做什麼」拆成**技能**（共用、必要）與**腳本**（本專案、客製）兩層，並給出分界判準。
> 來源：kiro-cli 2026-10-16 五層對照分析（nana-bot 實例），`docs/designs/agent-five-layer-architecture-design.md`。

## 1. 五層定義

| 層 | 比喻 | 回答的問題 | 特性 |
|---|---|---|---|
| 🧠 大腦 BRAIN | 個性與判斷力 | 我是誰、怎麼判斷、紅線在哪 | always-on 注入；人寫 |
| 📝 記憶 Memory | 經歷 | 之前發生過什麼 | 時間軸；daily → 蒸餾 → 歸檔（見 `memory-architecture.md`） |
| 📚 知識庫 Knowledge | 專業 | 事實、規格、領域資料 | 可檢索；raw → ingest → wiki（見 `knowledge-sources-map.md`） |
| 🖐️ 技能 Skill | 手腳（基本必要能力） | **怎麼做**一件標準的事 | 跨專案共用；上游 ark-agent-skills 版控；SKILL.md + 自帶 scripts |
| 🔌 腳本 Script | 外接工具（附屬客製能力） | 本專案**額外**要接什麼 | 綁本專案資料／環境／外部服務；不共用 |

## 2. 技能 vs 腳本（分界判準）

| 判準 | 技能 | 腳本 |
|---|---|---|
| 換一個專案還用得上嗎？ | ✅ | ❌ |
| 綁本專案的資料檔、模板、主機、帳號？ | 否（設定走 `.env`） | 是 |
| 誰維護 | 上游 skills repo（提案 → 審批 → apply） | 本專案自己 |
| 怎麼更新 | `sync_skills` / `ark-skills-align` 的 `mirror_sync` 從上游對齊 | 直接改、直接 commit |

- 🔴 **skill 目錄下的 `scripts/` 屬技能層**（技能的實作），不是本文的「腳本」。
- **升格規則**：腳本被第二個專案需要 → 抽掉寫死值改走 `.env` → 回貢上游成技能。
  實例：ninja-team 的 A4 資訊圖卡 → ark-html-report 1.3.0。
- **反向**：技能裡出現寫死的內網 IP、帳號、ID → 那段是腳本，留在消費端，不回貢。
  實例：ninja-bot 的 weknora 本地版寫死 agent ID，上游版改讀 `.env`。

## 3. 標準目錄對照

| 層 | team（ark_team_agent） | bot（ark_bot_agent） | 誰寫 | 進 context |
|---|---|---|---|---|
| 🧠 人格 | `.kiro/steering/SOUL.md` | 同左 | ✋ 人（`--profile` 可渲染） | ✅ |
| 🧠 規範 SSOT | 根 `AGENTS.md`（子 agent 工作目錄根各一份複本；`steering/` 不放 —— 見 SKILL.md 頂部單一權威） | 同左 | ✋ 人／daemon | ✅ |
| 🧠 判準 | `.kiro/steering/BRAIN.md` | 同左（`context_builder` 自動注入） | 🤖 build_kiro 產（判準＋角色段，once）／✋ 人補 | ✅ |
| 🧠 畫像／程式規範 | `.kiro/steering/USER.md`、`CODE.md` | 同左 | ✋ 人 | ✅／🔸 |
| 📝 導覽 + 里程碑 | `.kiro/steering/MEMORY.md`（< 20 KB） | 同左 | ✋ 人 | ✅ |
| 📝 持久事實 | `memory/memory.md` | 同左 | 🤖 `memory-distill`／consolidate | 🔸 |
| 📝 事件流水 | `memory/daily/` | 同左 | team ✋ 收尾手寫；bot 🤖 自動 | ❌ |
| 📝 近況 | — | `memory/recent.md` | 🤖 bot | 🔸 |
| 📝 舊事件 | `memory/archive/` | 同左 | 🤖 | ❌ |
| 📚 共用櫃 | `knowledge/shared/` | 同左 | 🤖 ingest | 🔸 檢索 |
| 📚 私有櫃 | `knowledge/<instance>/`、`agents/<name>/knowledge/` | 同左 | 🤖 ingest | 🔸 檢索 |
| 📚 產品／github／weknora | `knowledge/<product>/`、`$ARK_GITHUB_ROOT`、外部 RAG | 選配 | 🤖 排程 | 🔸 |
| 🖐️ 技能（共用） | `.kiro/skills/<name>/`（複本，非 symlink） | 同左 | 上游 | 🔸 按需 |
| 🖐️ 技能（套件內建） | `ark_team_agent` 內建工具 | `ark_bot_agent.skills.internal` | 套件 | — |
| 🔌 腳本（業務） | `scripts/`、專案自己的模組 | `skills/` 裡綁本專案的插件（見下方註） | 本專案 | — |
| 🔌 腳本（維運） | `scripts/` | 同左 | 本專案 | — |
| 🔌 外部工具 | `.kiro/settings/mcp.json`（daemon 產）／`.mcp.json` | 同左 | ✋／daemon | — |
| 產出 | `artifacts/{reports,sim,perf,triage}/` | `output/{reports,replies,images,exports,drafts}/` | 🤖／✋ | ❌ |

> ⚠️ bot 的根 `skills/` 是 ark_bot_agent 的 **`BaseSkill` 插件包**（`run_bot(skills=["skills"])` 掃描），
> **目錄名是套件慣例，不要改名**。它屬哪一層看**內容**，不看目錄名：插件通用、換專案還用得上 → 技能
> （該升格回貢）；綁本專案 config／templates／資料 → 腳本。和 `.kiro/skills`（SKILL.md 技能）同名但不同機制，
> BRAIN.md 寫明本專案 `skills/` 的定位即可，不需同步。（2.3.1 更正：2.3.0 曾寫「本質是腳本層」，太武斷）

## 4. 紅線（五層之間）

- 對話紀錄、bot 回覆、失敗訊息**只進記憶**，絕不進知識庫（實例：舊版 bot 把 > 200 字回覆寫進根層
  `knowledge/raw/`，含「處理失敗」訊息；ark_bot_agent 已改落 `output/replies/`，1.5.0 之後的版本生效）。
- 根層 `knowledge/raw/`、`knowledge/wiki/` 不屬任何櫃 —— 出現即放錯。
- 技能修改只能提案回上游；消費端直接改技能 = 下次同步被判 LOCAL 卡住或被覆蓋。
- 產出不進記憶也不進知識庫（recall 搜不到 `artifacts/`／`output/`）。

## 5. 檢核清單（建置或稽核 workspace 時）

- [ ] AGENTS.md 佈局：`scripts/audit_agents_layout.py` 通過（專案根 1＋編制內子 agent 根各 1＋steering 0）
- [ ] `.kiro/steering/BRAIN.md` 存在，且是本 agent 專用（無範本殘留的他角色路徑）
- [ ] BRAIN.md 的資源表列出五層，並寫明本專案「腳本」在哪
- [ ] 根層 `knowledge/` 只有櫃子目錄 + `index.md`／`log.md`／`schema.md`，沒有 `raw/`、`wiki/`
- [ ] `knowledge/index.md` 不寫死頁數（以各櫃 `wiki_index.py md` 產出為準）
- [ ] `.kiro/skills` 與上游一致（`mirror_sync plan` 無 STALE／LOCAL）
