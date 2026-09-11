# 架構回饋：模板缺的三項（來自演化後的實例）

> **來源**：2026-09-07 拿 `ark-agent-init`（原 `ark-kiro-init`）的產出模板，
> 對照本機 kiro-cli 根目錄（nana-bot 消費端，已套件化為 `ark_bot_agent`、演化半年）。
> **性質**：這不是版本落差，是「初始化模板 vs 演化後的真實實例」的落差。
> 以下三項是**模板該補上**的，否則照模板產出的新專案在實務上會踩到既有踩坑。

---

## ① 缺 `knowledge/shared/` 層 —— 而 Wiki 引擎實際讀的就是這層

**模板現況**：只定義「每個 agent 私有 `knowledge/` 五件套」
（`schema.md` / `index.md` / `log.md` / `raw/` / `wiki/overview.md`）。

**實例現況**：根目錄有**兩層** knowledge：

```
knowledge/
├── shared/              ← 🔴 模板沒定義，但 Wiki 引擎與 start.py 實際讀這層
│   ├── wiki/            ← 共用結構化知識（BM25 索引建在此）
│   ├── wiki/.index/     ← bm25 索引產物
│   ├── raw/
│   ├── tasks/ decisions/ agent_profiles/ artifacts/
│   ├── schema.md / index.md / log.md
└── （MEMORY 歸檔已移出 knowledge → 見下方 memory/archive/；1.8.1 起）
```

> 🔴 **記憶歸記憶、知識歸知識**：MEMORY.md 日期分節歸檔在 `memory/archive/`，
> **不在 knowledge**（1.8.1 起；舊 `knowledge/raw/memory-archive/` 已作廢並遷出）。

**為什麼一定要補**：本機 MEMORY 記過**四次**「少一層 shared」的靜默失效
（`layer1_bm25` / `indexer` / `wiki_distill` / `server/main.py` 都曾少一層 `shared`
→ 索引讀不到、蒸餾產出搜不到，且不拋例外不寫 log）。
若新專案照模板只建扁平 `knowledge/wiki/`，Wiki 引擎會讀不到索引。

**建議模板動作**：
- 團隊級 knowledge 一律建 `knowledge/shared/{wiki,raw}/` + `schema/index/log`
- `memory/archive/` 給 MEMORY 歸檔（1.8.1 起 —— 記憶歸記憶，不在 knowledge）
- 在 `AGENTS.md`／`schema.md` 明寫「Wiki 引擎讀 `shared/`，禁止手寫 `wiki/`，只由 ingest 產出」

---

## ② 缺 `memory/` 目錄 —— 記憶落點已不只是 `steering/MEMORY.md`

**模板現況**：記憶只放在 `.kiro/steering/MEMORY.md`（單檔）。

**實例現況**：套件（`ark_bot_agent` 1.0.0/1.0.1）把記憶落點收斂成 `memory/` 目錄：

```
memory/                  ← 根層（dir="." 的 manager 記憶落這裡）
├── daily/YYYY-MM-DD.md   ← 每日 log（自動累積）
├── recent.md
└── memory.md
agents/<name>/memory/    ← 子 agent 各自的 memory/（同結構）
```

**為什麼一定要補**：套件用「工作目錄 == 專案根」判斷記憶落點
（`paths.get_agent_memory_dir()` 單一出口）。`dir="."` 的 manager 記憶要落在
**根 `memory/`**，子 agent 落在**各自 `memory/`**。
本機曾因此產生「除了 memory/ 什麼都沒有的孤兒目錄 `agents/manager-agent/`」的 bug。
模板若只給 `steering/MEMORY.md`，套件層的 daily log / recent / consolidate
機制沒有落點，會靜默寫到錯的地方或讀不到自己剛寫的記憶。

**建議模板動作**：
- 每個 agent workspace（含根）都建 `memory/{daily/,recent.md,memory.md}`
- `steering/MEMORY.md` 仍保留（人類可讀的長期記憶 + 自動歸檔到 `memory/archive/`）
- 兩者分工寫進 `AGENTS.md`：`memory/` = 套件寫入的執行期記憶；`steering/MEMORY.md` = 專案敘事記憶

---

## ③ `artifacts/` 取代 `output/` —— 產出目錄名已更新

**模板現況**：agent 產出目錄用 `output/`。

**實例現況**：套件 1.2.19 起補的骨架用 `artifacts/`：

```
agents/<name>/
├── artifacts/reports/    ← 報告等產出（取代舊 output/）
├── knowledge/
├── memory/
└── .kiro/
```

**為什麼要補**：本機 ai-dev-agent 的實際產出在 `artifacts/reports/`。
模板若還寫 `output/`，會與套件產出的 `.gitkeep` 骨架不一致，
造成「模板建了 `output/`、套件寫進 `artifacts/`」兩個目錄並存的困惑。

**建議模板動作**：
- 產出目錄統一改 `artifacts/`（底下可分 `reports/` 等子類）
- `.gitkeep` 骨架比照套件 1.2.19：`memory/` + `artifacts/` + `scripts/`

---

## 附：本機比模板「進步」的設計判斷（模板可考慮吸收）

這些不是缺口，是實例的刻意選擇，列出供模板參考：

| 項目 | 模板 | 實例（更好） |
|------|------|-------------|
| AGENTS.md 內容 | 塞滿 team 派工規範（`reply()`/`send_to_instance`/MCP 表） | **只留通用規範**；team 派工規範移到 `TEAM.md` + `inclusion: manual`（通用對話不常駐團隊編制） |
| 根 agent 定位 | admin 管理者 | 通用助手（chat + agent 同讀根目錄，人格不混淆） |
| `settings/mcp.json` | 帶 MCP server 定義 | **全空 `{}`** 是正確狀態（CLI 內建 web_fetch，mcp-server-fetch 冗餘） |

> 🔴 判準：把 team-only 的內容放進 always-on 的 `AGENTS.md`，會讓每個非團隊場景
> 都吃到派工規範的 context 負擔。模板預設應區分「通用 steering（always）」與
> 「團隊 steering（manual）」。
