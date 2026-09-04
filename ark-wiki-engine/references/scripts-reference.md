---
title: "scripts/ 完整參數參考"
type: reference
updated: 2026-09-04
---

# scripts/ 完整參考

所有腳本：`python .kiro/skills/ark-wiki-engine/scripts/<name>.py --help`。
**stdout 只放機器契約（`--json` 的 JSON），人看的進度一律 stderr。**

| exit code | 意義 |
|----------:|------|
| 0 | 成功（查詢零結果也是 0 —— 「wiki 沒有這個內容」是正常回答） |
| 1 | 業務層失敗：guard 擋下、未知 tag、lint 有 error、索引過期（`freshness`） |
| 2 | 參數或環境錯誤：`WIKI_DIR_NOT_FOUND` / `BAD_ARGUMENTS` / `SCHEMA_NOT_FOUND` / `BUILD_LOCKED` |

## wiki_query.py — 四層搜尋

```bash
python scripts/wiki_query.py --wiki_dir knowledge/hoyeah/wiki --query "留存口徑"
python scripts/wiki_query.py --knowledge_root knowledge --domains hoyeah,shared --query "DAU 定義"
python scripts/wiki_query.py --wiki_dir ... --query ... --top_k 3 --full --max_chars 6000
python scripts/wiki_query.py --wiki_dir ... --query ... --type concept --tags kpi --status mature
python scripts/wiki_query.py --wiki_dir ... --query ... --trust deterministic --approved-only
python scripts/wiki_query.py --wiki_dir ... --query ... --layers L0,L1,L3
python scripts/wiki_query.py --wiki_dir ... --query ... --full --out /tmp/ctx.md
python scripts/wiki_query.py --wiki_dir ... --query ... --format text     # 給人看
```

| 參數 | 說明 |
|------|------|
| `--wiki_dir` / `--knowledge_root`+`--domains` | **二擇一**。多 domain 必須顯式列出（D-4），不預設掃全部 |
| `--top_k` | 預設 5 |
| `--full` | 帶頁面全文；受 `--max_chars`（預設 8000）限制，超過標 `truncated` |
| `--out <path>` | 全文落盤，`results` 不再帶 `content`，`meta.out_file` 指向檔案 |
| `--layers` | 顯式指定層（`L0,L1,L3`）。預設全開 |
| `--tokenizer` | `auto`（預設）/ `jieba` / `bigram` |
| `--rebuild-if-stale` | 索引過期時先重建（預設只警告，D-5） |
| `--format` | `json`（預設，機器）/ `text`（v2 人類輸出） |

輸出契約見 `query-contract.schema.json`。`meta` 必看三欄：

- `index_fresh: false` → 索引過期，**答案照用**，另提醒維護者重建
- `warnings` 含 `TOKENIZER_MISMATCH` → 索引與本機分詞不同，已改記憶體重算
- `layers_skipped.L2 = "no_embeddings"` → 語意層未啟用（預設狀態，不是錯）

## wiki_index.py — 索引

```bash
python scripts/wiki_index.py build     --wiki_dir knowledge/hoyeah/wiki [--tokenizer auto|jieba|bigram]
python scripts/wiki_index.py md        --wiki_dir ... [--output ...] [--dry_run]
python scripts/wiki_index.py freshness --wiki_dir ...        # exit 0 fresh / 1 stale
python scripts/wiki_index.py --wiki_dir ...                  # 無子命令 = md（v2 相容）
```

`build` 產出 `.index/`：`manifest.json` / `metadata.json` / `graph.json` /
`bm25/postings.json` / `userdict.txt` / `.gitignore`。
先寫 `.index.tmp/` 再 `os.replace` 原子切換；同時取 lock，第二個 build 回 `BUILD_LOCKED`。

> `--backend bm25s` 目前**明確回 `BAD_ARGUMENTS`**（排在 W4）——
> 不靜默降級成 purepy。

## wiki_context.py — 可注入的 context 區塊

```bash
python scripts/wiki_context.py --knowledge_root knowledge --domains hoyeah,shared \
    --query "$USER_MSG" --top_k 3 --budget_chars 2500 [--format md|json]
```

三條規則：未審核帶 ⚠、**超預算整筆丟棄不截半段**、零結果輸出空字串 exit 0
（注入端可無條件串接）。

## wiki_ingest.py — 匯入（guard-first，順序不可調換）

```bash
python scripts/wiki_ingest.py --source knowledge/raw/notes.md --wiki_dir knowledge/wiki \
    --schema knowledge/schema.md --by librarian-agent
python scripts/wiki_ingest.py --source knowledge/raw/ --batch --wiki_dir knowledge/wiki --no-index
```

固定流程：`guard scan` → 骨架（`trust: deterministic`）→ `taxonomy check`（給 `--schema` 時）
→ 落盤 → `index.md` + `log.md` → `wiki_index.py build`。

| 參數 | 說明 |
|------|------|
| `--schema` | 給了才做 tags 白名單守門。**未知 tag → exit 1 且不落盤** |
| `--by` | 寫入 `log.md` 的執行者（出問題要能回答「誰寫的」） |
| `--no-guard` | 繞過 guard —— stderr 醒目警告 + `log.md` 記 `no-guard`（可稽核） |
| `--no-index` | 不重建索引（batch 中間步驟用） |

## wiki_lint.py — 健檢（CI 用 exit code）

```bash
python scripts/wiki_lint.py --wiki_dir knowledge/wiki --json
python scripts/wiki_lint.py --wiki_dir ... --schema knowledge/schema.md   # 加驗 tags 白名單
python scripts/wiki_lint.py --wiki_dir ... --errors-only
```

error：缺必填欄位（含 `trust`）、`llm-distilled` 未帶 `approved`、
`approved:false` 卻非 `seedling`、tag 不在白名單、斷裂 wikilink。
warning：孤立頁面、建議欄位、非法枚舉值、`seedling` 逾期。

## wiki_graph.py — 圖譜

```bash
python scripts/wiki_graph.py --wiki_dir knowledge/wiki               # 人類報告
python scripts/wiki_graph.py --wiki_dir ... --json                   # 含 adjacency
python scripts/wiki_graph.py --wiki_dir ... --mermaid
python scripts/wiki_graph.py --wiki_dir ... --export .index/graph.json
```

## wiki_guard.py — 消毒關卡

```bash
python scripts/wiki_guard.py scan file.md [--json]
python scripts/wiki_guard.py sweep --raw_dir knowledge/raw [--json]
python scripts/wiki_guard.py self-test [--json]
```

偵測：注入詞組（多語系）、零寬／bidi 控制字元、HTML 隱藏樣式、超長編碼 blob。
教學／防禦文件可在 frontmatter 標 `guard: reviewed` 豁免注入規則（其餘仍驗）。

## wiki_taxonomy.py — 受控詞彙

```bash
python scripts/wiki_taxonomy.py list    --schema knowledge/schema.md [--json]
python scripts/wiki_taxonomy.py check   --schema ... page1.md page2.md [--json]
python scripts/wiki_taxonomy.py propose --schema ... new-tag --reason "..." --by agent
python scripts/wiki_taxonomy.py approve --schema ... new-tag      # 人工執行
python scripts/wiki_taxonomy.py migrate --schema ... --wiki_dir ...
```

> ⚠️ 白名單解析要求 `- ` 清單**緊接** `## tags 白名單` 標題。
> 格式不合 → 白名單靜默變空集合，而空集合的語意是
> **所有 tag 都不合法 → ingest 全被擋**（fail-closed）。

## build_wiki.py / validate_wiki.py — scaffold

```bash
python scripts/build_wiki.py <output_dir> <project_name> [--install-skill <.kiro/skills>]
python scripts/build_wiki.py --validate <project_dir> [--json]
```

v3 只產 `knowledge/{name}/` 骨架（raw / wiki / `.index` / schema / index / log / overview）。
**不再產 `src/`、server、Web UI** —— 那些是四層引擎的第二份實作，D-2 裁定刪除。
要取回舊模板：`git show <v2 commit>:ark-wiki-engine/scripts/build_wiki.py`。

## scripts/tests/ — 守門

```bash
python3 -m pytest scripts/tests -q                 # 系統 python（bigram 路徑）
.venv/bin/python -m pytest scripts/tests -q        # venv（jieba 路徑）
```

**兩個解譯器都要跑** —— 有無 jieba 會走到不同層，只跑一邊等於只驗一半。
