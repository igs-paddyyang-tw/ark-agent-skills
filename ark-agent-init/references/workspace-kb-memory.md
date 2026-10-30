# 知識庫、記憶、產出目錄的產出細節

> 2026-10-30 自 SKILL.md 原樣搬出（盤點 O-4：主檔只留流程與決策）。

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
