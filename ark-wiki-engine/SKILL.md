---
name: ark-wiki-engine
description: |
  Agent 直接呼叫的 Wiki 知識庫 executor（捆綁可執行 scripts/，不掛 MCP、不跑 server）。
  四層搜尋（metadata 精確 → BM25 持久索引 → 語意 → 圖譜擴散 → RRF 融合）回統一 JSON 契約，
  Layer 0 兜底永不掛零；ingest 內建 guard-first 消毒與 tags 受控詞彙守門；兩層信任模型
  （deterministic | llm-distilled，未審核強制 seedling 並在注入時帶 ⚠）。
  使用此 skill 當使用者或 agent 提及：查 wiki、查知識庫、knowledge base、口徑定義在哪、
  RAG、文件搜尋、知識圖譜、wiki ingest、匯入知識、wiki 健檢、受控詞彙、tag 白名單、
  報告蒸餾入庫、建 wiki 骨架 —— 即使只是「知識庫有沒有 XXX」也應呼叫本 skill 的
  wiki_query.py，而非 team MCP 內建的 wiki_query。
  不適用於：分析結論的 Markdown 產出請用 ark-md-report；人類視圖請用 ark-html-report。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "3.0"
  updated: 2026-09-04
  outputs:
    # wiki_query / wiki_context 的 JSON 契約歸受控詞彙 data
    # （`json` 不是合法 format 值，與 ark-db-query 同一判準：不為單一 skill 放寬守門）
    - { format: data, audience: ai }
    - { format: md, audience: both }
  render: none
  depends_on: []
  consumed_by: [ark-md-report, ark-news-daily, ark-html-report]
  # 只取代 query —— 內建的 wiki_ingest 有可信的 role gate（見「ingest 的授權邊界」），
  # bash 腳本無法複製那個管控，故不宣稱取代它
  replaces: [mcp-wiki-server, team-mcp.wiki_query]
---

# ark-wiki-engine v3

**executor 型 skill**：agent 用 bash 一行呼叫 `scripts/` 下的腳本，stdout 回統一 JSON 契約。
不掛 MCP、不跑 FastAPI server、不 import `src.*`。

**v2 → v3 的根本改變**：四層搜尋原本只存在於 `build_wiki.py` 的模板字串（產出到消費端的
`src/skills/wiki_skills/`），而消費端的 `src/wiki` 已被刪除 —— 等於四層邏輯在 runtime 沒有載體。
v3 把它變成真實可執行的 `scripts/wiki_query.py`，索引落在 `knowledge/{domain}/wiki/.index/`。

## 模式路由

```
收到 wiki 相關任務
├─ 專案已有 knowledge/ 目錄？
│    ├─ 是 → operate（查詢 / ingest / lint / 蒸餾）
│    └─ 否 → scaffold（`build_wiki.py <dir> <name>`，只產知識庫骨架）
└─ 例外：使用者明說「重建骨架」→ scaffold 優先於目錄偵測
```

與三件套的分工：本 skill 管「庫」；分析結論的產出是 `ark-md-report`（Content 軌）、
人類視圖是 `ark-html-report`（View 軌）。報告是 wiki 的 ingest **素材**，
**禁止**把報告複製進 `wiki/` —— 蒸餾規則見 `references/distill-rules.md`。

## Agent SOP（決策樹）

```
需求進來
├─ 查知識 / 找口徑 / 有沒有 XXX？ → wiki_query.py（先 --top_k 3，不夠再 --full）
├─ 要把 wiki 內容帶進回答或提詞？ → wiki_context.py --budget_chars
├─ meta.index_fresh = false？      → 答案照用，另提醒維護者跑 wiki_index.py build
├─ 匯入 raw / 報告蒸餾入庫？       → wiki_ingest.py（guard/taxonomy 內建，勿 --no-guard）
├─ 新概念沒有合法 tag？            → wiki_taxonomy.py propose（不自創）
├─ 健檢 / CI？                     → wiki_lint.py --json（以 exit code 為準）
├─ 圖譜 / 孤兒頁？                 → wiki_graph.py
└─ 專案還沒有 knowledge/？          → build_wiki.py <dir> <name>
```

## 呼叫範例（複製即用）

```bash
S=.kiro/skills/ark-wiki-engine/scripts

python $S/wiki_query.py   --wiki_dir knowledge/shared/wiki --query "留存口徑" --top_k 3
python $S/wiki_query.py   --knowledge_root knowledge --domains hoyeah,shared --query "DAU 定義"
python $S/wiki_context.py --wiki_dir knowledge/shared/wiki --query "$MSG" --budget_chars 2500
python $S/wiki_ingest.py  --source knowledge/raw/notes.md --wiki_dir knowledge/shared/wiki \
                          --schema knowledge/shared/schema.md --by librarian-agent
python $S/wiki_index.py   build --wiki_dir knowledge/shared/wiki
python $S/wiki_lint.py    --wiki_dir knowledge/shared/wiki --json
python $S/wiki_graph.py   --wiki_dir knowledge/shared/wiki --json
python $S/build_wiki.py   ./myproject demo --install-skill ./myproject/.kiro/skills
```

完整參數、exit code 見 `references/scripts-reference.md`。

## JSON 契約

```json
{
  "ok": true,
  "query": "留存口徑",
  "results": [{
    "page": "kpi/retention-definition", "slug": "retention-definition",
    "title": "留存率口徑定義", "score": 0.0328, "layers": ["L0", "L1", "L3"],
    "type": "concept", "status": "mature", "trust": "deterministic",
    "approved": true, "tags": ["kpi"], "summary": "D1 留存 = …"
  }],
  "meta": {
    "total": 7, "top_k": 5, "truncated": false, "out_file": null, "domains": [],
    "index_used": true, "index_fresh": true,
    "layers_used": ["L0","L1","L3"], "layers_skipped": {"L2": "no_embeddings"},
    "tokenizer": "bigram", "bm25_backend": "purepy", "warnings": [], "elapsed_ms": 5
  }
}
```

錯誤：`{"ok": false, "error": {"code": "...", "msg": "..."}}`，exit 2。
Schema：`references/query-contract.schema.json`。

| code | 意義 |
|------|------|
| `WIKI_DIR_NOT_FOUND` | 目錄不存在 |
| `BAD_ARGUMENTS` | 參數互斥或缺必要組合（如多 domain 未給 `--domains`） |
| `SCHEMA_NOT_FOUND` | `--schema` 指向的檔案不存在 |
| `INDEX_MISSING` / `INDEX_STALE` | 索引不存在／過期（**warning，仍回答**） |
| `TOKENIZER_MISMATCH` | 索引與本機分詞不同（warning，改記憶體重算） |
| `GUARD_BLOCKED` | ingest 來源含注入等違規，已隔離且不落盤 |
| `TAG_NOT_IN_WHITELIST` | tags 不在 schema 白名單，不落盤 |
| `BUILD_LOCKED` | 另一個 index build 進行中 |

> **stdout 只放機器契約，人看的進度一律 stderr。** 這條在實作中被違反三次
> （進度混印、漏 import、self-test 先印人類結果），每次都讓 agent 端 `json.loads` 直接炸
> —— `scripts/tests/test_ingest_guard.py` 對每支腳本每條 `--json` 路徑都驗。

## 三條硬規則（由腳本強制，不靠 LLM 記得）

1. **受控詞彙** —— 頁面 tags 只能用 `schema.md` 白名單；新概念 `wiki_taxonomy propose` → 人工 `approve`。
   `wiki_ingest --schema` 遇未知 tag **exit 1 且不落盤**。
2. **Guard-first ingest** —— 任何 raw 入庫前必過 `wiki_guard`；違規進 `raw/_quarantine/` 不入庫。
   順序寫死在 `ingest_file`，**窮舉參數組合皆無法跳過**（測試釘住）。`--no-guard` 僅限除錯，
   會在 stderr 警告並在 `log.md` 記 `no-guard` 供稽核。
3. **兩層信任** —— 腳本搬運 = `trust: deterministic`；LLM 改寫／摘要 = `trust: llm-distilled`
   + `approved`（必填）。`approved: false` 強制 `status: seedling`，`wiki_context` 注入時帶 ⚠。

## 四層與降級矩陣

| 層 | 資料來源 | 命中條件 | 缺失時行為 |
|----|----------|----------|------------|
| L0 精確 | `.index/metadata.json` | slug／title／page_id 相等 1.0（固定置頂）；alias 相等 0.95；包含 0.8 | 現場掃 frontmatter，`index_used: false` |
| L1 BM25 | `.index/bm25/postings.json` | score > 0 | 記憶體重算；分詞不符回 `TOKENIZER_MISMATCH` |
| L2 語意 | `.index/embeddings/` | cosine ≥ 閾值 | **預設不啟用** → `layers_skipped.L2` |
| L3 圖譜 | `.index/graph.json` | L0∪L1 前 3 名的 1-hop 出／入鄰居 | 現場解析 `[[wikilink]]` |
| 兜底 | `wiki/` 全文 | 子字串命中 → 0.4 | **永遠可用** |

融合 RRF（k=60）→ 去重 → frontmatter 過濾 → `top_k`。
**零第三方依賴時全功能可用**（purepy backend + CJK bigram 分詞），只有召回品質差異。

## 索引生命週期

- **誰建**：`wiki_ingest.py` 落盤後自動 build，或 CI／排程定期 build。**agent 只讀**。
- **原子性**：先寫 `.index.tmp/` 再 `os.replace`；同時取 lock，第二個 build 回 `BUILD_LOCKED`。
- **freshness**：比對 manifest 的 `content_hash`。過期時 `index_fresh: false` + warning，
  **仍用舊索引回答**。
- **為何查詢端不自動重建**：15 個 instance 併發會撞 lock 並拖慢查詢。
  維護者要重建用 `--rebuild-if-stale` 或直接 `wiki_index.py build`。

## 🔴 ingest 的授權邊界（executor 化弱化的地方）

內建 `wiki_ingest` 有**可信的 role gate**（`tools_for_role` 讓 worker 看不到該工具，
handler 另有 `_role not in ("admin","leader")` 擋一次；`_role` 來自 daemon 的
`--role` 啟動參數，agent 改不了）。而 `scripts/wiki_ingest.py` 是 bash 腳本 ——
**任何能跑 bash 的 agent 都能執行**。

因此：**排他句只涵蓋查詢，不涵蓋寫入。** worker 維持「寫到 `raw/`、由排程 ingest」；
只有 admin／leader／排程才用 `wiki_ingest.py`。
**不要在腳本裡加 `--role` 檢查** —— 呼叫者自報的 role 不是邊界。
完整政策表見 `references/agent-prompt-snippets.md`。

> `authority.L2: wiki_ingest` 這條**不是由 DecisionManager 執行的**（matrix 未被
> team_mcp 讀取）—— 實際管控就是上面那個 role gate。讀 matrix 的人會誤以為有拍板流程。

## Multi-agent 部署（取代 MCP 掛載）

1. 複製 skill 到消費端 `.kiro/skills/ark-wiki-engine/`
   （或 `build_wiki.py ... --install-skill <.kiro/skills>`）
2. `team.yaml` **不寫**任何 wiki 相關 `mcp` / `mcp_servers` 設定
3. instance prompt 加排他句 —— 套件內建的 team MCP 自帶同名的 `wiki_query` 與 `wiki_ingest`，
   不排他 agent 會亂選。片段見 `references/agent-prompt-snippets.md`
4. 各 instance 在 prompt 裡寫死自己的 `--domains`（不預設掃全部 domain）
5. 選配：套件若支援 pre-message hook，掛 `wiki_context.py` 自動注入

## 產出檔案（scaffold 模式）

```
knowledge/{name}/
├── raw/                    原始素材（唯讀；_quarantine/ 為 guard 隔離區）
├── wiki/                   結構化頁面
│   └── .index/             索引（自帶 .gitignore，不進版控）
├── schema.md               頁面規格 + tags 白名單
├── index.md                頁面索引
└── log.md                  append-only：date | op | page | trust | by | note
```

> v3 **不再產** `src/skills/wiki_skills/`、`src/server/`、Web UI —— 那是四層引擎的第二份實作。
> 要取回舊模板：`git show <v2 commit>:ark-wiki-engine/scripts/build_wiki.py`。

## 注意事項

- `raw/` 唯讀；`raw/_quarantine/` 人工檢視後處置
- 改頁面後同步 `index.md`（`wiki_index.py md`）；`log.md` **append-only**，勿改欄序
- 矛盾只標記不解決：`> ⚠️ **矛盾**：來源 A 說 X，來源 B 說 Y，待釐清。`；不確定用 `(?)`
- summary 擷取跳過 frontmatter **與純標題段落** —— H1 通常就是 title，拿它當摘要等於沒有摘要
- category 自動偵測分數 ≤1 時回 uncertain，要求人工指定，不靜默入庫
- 測試**兩個解譯器都要跑**（有無 jieba 會走到不同層）：`python3 -m pytest scripts/tests -q`

## references/

| 檔案 | 內容 |
|------|------|
| `page-schema.md` | frontmatter v3.1 欄位、type／status／trust 枚舉、wikilink、aliases 為何重要 |
| `scripts-reference.md` | 每支腳本完整參數、exit code、範例 |
| `query-contract.schema.json` | JSON Schema（測試與下游 agent 共用） |
| `agent-prompt-snippets.md` | instance prompt 排他句、hook 範例、與其他 skill 的對接 |
| `distill-rules.md` | 報告 → wiki 的蒸餾規則 |
| `schema-template.md` | schema.md 範本 |
