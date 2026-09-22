---
title: "agent prompt 片段與消費端對接"
type: reference
updated: 2026-09-04
---

# agent prompt 片段與消費端對接

## 排他句（貼進 instance prompt／SOUL.md）

套件內建的 team MCP 自帶 `wiki_query` 與 `wiki_ingest` 兩個同名工具
（`team_mcp.py` 的 `_handle_wiki_query` / `_handle_wiki_ingest`），
與本 skill 的觸發詞重疊 → agent 會在同名能力之間亂選。

**但排他只涵蓋 query，不涵蓋 ingest** —— 見下方「為何寫入不排他」。

> **知識庫查詢**一律執行
> `python .kiro/skills/ark-wiki-engine/scripts/wiki_query.py --wiki_dir <你的 wiki> --query "<問題>"`，
> 解析其 stdout JSON 的 `results`。**不要使用 team 內建的 `wiki_query` 工具**
> —— 它是簡易關鍵字掃描，沒有 L0 精確層與 L3 圖譜擴散。
>
> **知識庫寫入不在此列** —— 你若是 worker，維持既有做法：把內容寫到 `raw/`，
> 由排程 ingest。（原因見下方「為何寫入不排他」。）
>
> 結果中 `approved: false` 的內容是**未經人工審核的模型蒸餾產出**，
> 引用時必須標註；`meta.index_fresh: false` 時答案照用，另提醒維護者重建索引。
>
> 我的 domain 是 `<domain>`（查跨域知識時用
> `--knowledge_root knowledge --domains <domain>,shared`）。

> ⚠️ **`--domains` 要在 prompt 裡寫死各 instance 自己的範圍**（D-4）。
> 不預設掃全部 domain 的理由：A 專案的口徑會污染 B 專案的回答。

## 🔴 為何寫入不排他

內建的 `wiki_ingest` 有**可信的 role gate**：`tools_for_role(_role)` 讓 worker
看不到該工具，handler 內另有 `if _role not in ("admin", "leader", "manager")` 擋一次。
`_role` 來自 daemon 啟動 team_mcp 的 `--role` 參數，**agent 改不了**。

`scripts/wiki_ingest.py` 是 bash 腳本，**任何能跑 bash 的 agent 都能執行它**
→ 把寫入也排他過去，等於**移除一個真的管控**。

政策：

| 角色 | 查詢 | 寫入 |
|------|------|------|
| worker | `wiki_query.py`（排他） | 寫到 `raw/`，**不呼叫 ingest** |
| admin / leader / manager | `wiki_query.py`（排他） | `wiki_ingest.py` 或內建工具皆可 |
| 排程 | — | `wiki_ingest.py`（guard／taxonomy 內建，比內建工具嚴格） |

> **不要在腳本裡加 `--role` 檢查** —— 呼叫者自報的 role 不是邊界。
> 🔴 **manager 納入依賴套件修**：套件 `ark_team_agent` 的 handler gate 一度硬編僅
> `("admin","leader")`，manager 被擋。已開問題單
> `ark_team_agent/docs/issues/2026-09-22-wiki-ingest-role-gate-add-manager.md`。
> 該版落地前，manager 走 daemon 內建 `wiki_ingest` 仍被擋，只能改跑 `scripts/wiki_ingest.py`。

## 🖥️ IDE／私訊整理知識庫（不經 daemon 的完整範例）

daemon 的 role gate 只作用在 team MCP 內建的 `wiki_ingest` 工具。在 **KIRO IDE 直接對話**
或 **bot 私訊（DM）** 場景，agent 直接跑 `scripts/wiki_ingest.py`（docstring 明寫「不依賴 team MCP」），
**不經 team MCP、沒有 role gate** —— 信任邊界是**在場的真人**。整理流程與 daemon 蒸餾同一套產物與守門：

| 場景 | 入口 | 授權來源 |
|------|------|---------|
| team daemon（多 agent） | team MCP `wiki_ingest` 工具 | daemon `--role` gate（admin/leader/manager） |
| KIRO IDE 對話 | 直接跑 `scripts/wiki_ingest.py` | 無 gate（真人在場） |
| bot 私訊（DM） | agent 在 session 內跑腳本 | 無 gate（真人在場） |

```bash
# 1. 素材寫進 raw/（人可讀底本）：knowledge/<domain>/raw/<白話檔名>.md
# 2. 蒸餾入庫（給 --schema 才做 tags 白名單守門，勿 --no-guard）
python scripts/wiki_ingest.py \
    --source knowledge/<domain>/raw/<file>.md \
    --wiki_dir knowledge/<domain>/wiki \
    --schema knowledge/<domain>/schema.md \
    --by <你的角色/名字>
# 3. 守門三件
python scripts/wiki_guard.py scan knowledge/<domain>/wiki/<new>.md
python scripts/wiki_taxonomy.py check --schema <schema> knowledge/<domain>/wiki/<new>.md
python scripts/wiki_lint.py --schema <schema>          # 以 exit code 為準
# 4. 索引重建 + freshness
python scripts/wiki_index.py build && python scripts/wiki_index.py freshness
```

> 🔴 **`raw/` 只增不改、`wiki/` 禁手寫**（ingest 產出）—— IDE/私訊整理也照這條，不手寫 wiki 頁繞過蒸餾。
> 蒸餾規則見 `distill-rules.md`。

## 決策樹（給 agent 的 SOP）

```
需求進來
├─ 查知識 / 找口徑 / 有沒有 XXX？ → wiki_query.py（先 --top_k 3，不夠再 --full）
├─ 要把 wiki 內容帶進回答或提詞？ → wiki_context.py --budget_chars
├─ meta.index_fresh = false？      → 答案照用，另提醒維護者跑 wiki_index.py build
├─ 匯入 raw / 報告蒸餾入庫？       → **僅 admin/leader/manager/排程**：wiki_ingest.py（勿 --no-guard）
│                                    worker：寫到 raw/ 即可
├─ 新概念沒有合法 tag？            → wiki_taxonomy.py propose（不自創）
├─ 健檢 / CI？                     → wiki_lint.py --json（以 exit code 為準）
├─ 圖譜 / 孤兒頁？                 → wiki_graph.py
└─ 專案還沒有 knowledge/？          → build_wiki.py <dir> <name>
```

## 自動注入（選配）

若套件支援 pre-message hook，可在組提詞前注入 wiki context：

```bash
CTX=$(python .kiro/skills/ark-wiki-engine/scripts/wiki_context.py \
        --knowledge_root knowledge --domains hoyeah,shared \
        --query "$USER_MSG" --top_k 3 --budget_chars 2500)
# 零結果時 $CTX 是空字串，可無條件串接
```

## 與其他 skill 的對接

| skill | 關係 |
|-------|------|
| `ark-md-report` | 報告產出後可用 `wiki_ingest.py` 蒸餾入庫；`report_register` 契約不變 |
| `ark-news-daily` | CollectorRunner 可消費 `wiki_query.py --format json` 的 `results` |
| `ark-html-report` | 呈現層，不直接對接（先經 `ark-md-report`） |

## 索引由誰建

**agent 只讀索引，不建索引。** 產出時機只有兩個：

1. `wiki_ingest.py` 落盤後自動 `build`
2. CI／排程定期 `build`

查詢端**刻意不自動重建**（D-5）—— 15 個 instance 併發時會撞 build lock 並拖慢查詢。
`--rebuild-if-stale` 留給維護者手動用。
