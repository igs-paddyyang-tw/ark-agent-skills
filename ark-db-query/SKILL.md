---
name: ark-db-query
description: |
  Agent 直接呼叫的多資料庫查詢工具箱（executor 型，捆綁可執行 scripts/，非產碼食譜）。
  以 bash 執行捆綁腳本即可查詢 SQLite / PostgreSQL / MySQL / MSSQL / MongoDB / BigQuery，
  統一回傳 JSON 契約（rows/count/truncated/out_file + meta）。
  BigQuery 路徑完整取代 BQ MCP server：bq_query.py（dry-run 成本估算 + maximum_bytes_billed
  強制守門）、bq_schema.py（datasets/tables/schema/preview，零查詢費）、bq_export.py（大結果分頁落盤）。
  內建 deterministic 守門：read-only 預設、掃描位元組上限、stdout 截斷保護 context window。
  使用此 skill 當使用者或 agent 提及：資料庫查詢、SQL、db query、BigQuery、BQ、查資料表、
  資料庫連線、取代 BQ MCP、query 資料、拉數據、匯出資料表，或任何需要從資料庫取得資料的場景 ——
  即使只是「幫我看一下某張表有什麼欄位」也應使用本 skill 的 bq_schema.py 而非 MCP。
metadata:
  schema_version: "1.1"
  status: active
  category: executor        # v1 誤標 pipeline、實為 scaffolder；v2 起為可直接執行工具箱
  outputs:
    - { format: json, audience: ai }        # stdout 統一 JSON 契約
    - { format: jsonl/csv, audience: ai }   # --out 落盤，供 etl-pipeline / chart-generator 消費
  render: none
  depends_on: []
  replaces: [bq-mcp-server]
  author: paddyyang
  version: "2.0"
  updated: 2026-08-19
---

# ark-db-query v2.0

**定位：executor。agent 用 bash 直接呼叫 `scripts/` 下的腳本，不生成程式碼、不掛 MCP。**

v1 → v2 的根本改變：v1 是「產出 db_query.py 的食譜」（每次使用都要 LLM 重新生成程式碼）；
v2 捆綁測試過的腳本，agent 一行 bash 呼叫，行為 deterministic。
BigQuery 全路徑取代 BQ MCP —— multi-agent 場景下每個 agent 不再掛載 MCP server，
只需複製本 skill 至 `.kiro/skills/`，MCP server 負載歸零。

## Agent SOP（決策樹）

```
需求進來
├─ 不知道有哪些表 / 欄位？
│    → bq_schema.py datasets / tables / schema     （零費用，不要用 SELECT 猜）
├─ 想先看幾筆資料長相？
│    → bq_schema.py preview --table ds.tbl          （tabledata.list，零費用，禁用 SELECT * LIMIT）
├─ BigQuery 分析查詢？
│    → 1. bq_query.py --dry-run                     （先看 bytes_processed / estimated_cost_usd）
│      2. would_exceed_cap=true → 改寫 SQL 縮小掃描（partition / 日期 / 指定欄位），回到 1
│      3. bq_query.py（正式執行，自動帶 maximum_bytes_billed 上限）
├─ 結果集大（>1000 筆）或要給下游 ETL？
│    → bq_export.py --out data/x.jsonl              （stdout 只回摘要+樣本，全量在檔案）
├─ 其他資料庫（sqlite/pg/mysql/mssql/mongo）？
│    → db_query.py --db-type ...
└─ 連不上 / CONN_FAILED？
     → db_health.py --db-type ...                    （逐項診斷：驅動→憑證→連線→最小查詢）
```

## 呼叫範例（複製即用）

```bash
# BigQuery：先估算再執行（兩步是標準流程，不可省略 dry-run）
python scripts/bq_query.py --project my-proj --sql-file /tmp/q.sql --dry-run
python scripts/bq_query.py --project my-proj --sql-file /tmp/q.sql --limit 100

# BigQuery 中繼資料（全部零費用）
python scripts/bq_schema.py tables  --project my-proj --dataset analytics
python scripts/bq_schema.py schema  --project my-proj --table analytics.daily_kpi
python scripts/bq_schema.py preview --project my-proj --table analytics.daily_kpi --limit 5

# 大結果匯出（串接 etl-pipeline / chart-generator）
python scripts/bq_export.py --project my-proj --sql-file /tmp/q.sql --out data/kpi.jsonl

# 其他資料庫
python scripts/db_query.py --db-type sqlite --db-path ./data/app.db --sql "SELECT * FROM users"
python scripts/db_query.py --db-type postgresql --host $PG_HOST --database gamedb \
    --user reader --password-env PG_PASS --sql-file /tmp/q.sql
python scripts/db_query.py --db-type mongodb --host $MONGO_HOST --database player_profile \
    --collection player_profiles --filter '{"vip_level":{"$gte":5}}' \
    --sort '[["ltv.total_spend",-1]]' --limit 20
```

**Agent 呼叫紀律：**

1. SQL 一律寫入暫存檔用 `--sql-file`，不要在 bash 引號裡拼長 SQL（轉義地獄）
2. 解析回傳時只認 stdout 的 JSON envelope；`success:false` 時讀 `error.hint` 決定下一步
3. `truncated:true` 表示 stdout 只有樣本 —— 需要全量就重跑並加 `--out`，然後讀檔案，
   **不要**調大 `--max-stdout-rows` 把幾千筆塞進對話
4. 寫入語句預設被擋（`GATE_BLOCKED`）；確認是刻意寫入才加 `--allow-write`

## 輸出契約（所有腳本統一）

```json
{
  "success": true,
  "data": {"rows": [/* 最多 max-stdout-rows 筆 */], "count": 8421,
           "truncated": true, "out_file": "data/kpi.jsonl"},
  "meta": {"db_type": "bigquery", "elapsed_ms": 1834, "job_id": "...",
           "cache_hit": false, "bytes_processed": 52428800,
           "estimated_cost_usd": 0.000305}
}
```

失敗（exit code 1）：`{"success": false, "error": {"code", "message", "hint"}}`
`code` 枚舉：`DRIVER_MISSING | CONN_FAILED | QUERY_FAILED | GATE_BLOCKED | BAD_INPUT`

## Deterministic 守門（內建，非提詞約束）

| 守門 | 機制 | 覆寫方式 |
|------|------|----------|
| read-only 預設 | DML/DDL 正則攔截 → `GATE_BLOCKED` | `--allow-write` |
| BQ 成本上限 | 強制 `maximum_bytes_billed`（預設 1 GiB） | `--max-bytes-billed` / `ARK_BQ_MAX_BYTES_BILLED` |
| BQ 先估後跑 | 執行前必跑 dry-run，超限直接擋 | 無（上限內才放行） |
| context 保護 | stdout 預設最多 20 筆，全量走 `--out` 檔案 | `--max-stdout-rows`（不建議調大） |
| 憑證不落 log | 密碼走 `--password-env` 讀環境變數 | —（`--password` 明文保留但不建議） |

## BQ MCP → 本 skill 對照表（遷移用）

| BQ MCP tool | 替代呼叫 | 差異 |
|-------------|----------|------|
| `list_datasets` | `bq_schema.py datasets` | 同 |
| `list_tables` | `bq_schema.py tables --dataset DS` | 多回 num_rows / size_mb / 分區欄位 |
| `get_table_schema` | `bq_schema.py schema --table DS.TBL` | RECORD 巢狀欄位攤平為點記法 |
| `preview_table` | `bq_schema.py preview --table DS.TBL` | 走 tabledata.list，零費用 |
| `execute_query` | `bq_query.py` | 多 dry-run 守門 + bytes 上限 + context 截斷 |
| （無對應） | `bq_export.py` | MCP 做不到的大結果分頁落盤 |

## Multi-agent 部署（取代 MCP 掛載）

```
每個 agent 的 .kiro/skills/ark-db-query/     ← 複製本 skill 整個資料夾
├── SKILL.md
├── scripts/（6 支腳本）
├── references/
└── requirements.txt

環境需求（各 agent 工作目錄 .env 或系統環境變數）：
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
  GOOGLE_CLOUD_PROJECT=my-proj
  ARK_BQ_MAX_BYTES_BILLED=1073741824        # 選填，預設 1 GiB
  PG_PASS=... / MSSQL_PASS=...              # 各 DB 密碼

一次性安裝（只裝用到的驅動）：
  pip install google-cloud-bigquery --break-system-packages
```

MCP 掛載與本 skill 的資源差異：MCP 是常駐 server，N 個 agent 掛載 = N 條長連線 + server 常駐記憶體；
本 skill 是隨用隨起的短命進程，跑完即釋放，無常駐負載、無單點。
併發上限轉由 BigQuery 端配額管理（project 級 quota），不再受自建 MCP server 吞吐限制。

## 依賴（按需安裝）

| db_type | 套件 | 備註 |
|---------|------|------|
| sqlite | 內建 | — |
| bigquery | google-cloud-bigquery | 服務帳號金鑰 |
| postgresql | psycopg[binary]（fallback psycopg2-binary） | 同步驅動，CLI 場景不需 asyncpg |
| mysql | pymysql | 純 Python，免編譯，取代 aiomysql |
| mssql | pymssql | — |
| mongodb | pymongo | — |

## 附帶資源

| 路徑 | 用途 | 載入時機 |
|------|------|----------|
| `scripts/db_common.py` | 共用契約/守門/落盤（其餘腳本 import，不直接呼叫） | — |
| `references/bq-cookbook.md` | BQ 常用查詢範本（省 bytes 寫法、分區過濾、去重） | 寫 BQ SQL 前 |
| `references/troubleshooting.md` | 錯誤碼 → 處置對照 | 收到 success:false 時 |

## 注意事項

- 本 skill 不再產出 `src/skills/python_skills/db_query.py`；需要框架內 Skill 類別包裝時，
  以薄轉接層 subprocess 呼叫本 skill 腳本，勿複製邏輯（單一事實來源在 `scripts/`）
- Workflow YAML 串接方式不變：step 改為 bash 執行腳本，`output` 讀 stdout JSON 或 `--out` 檔案
- 報表/圖表下游（etl-pipeline、chart-generator）消費 `--out` 的 jsonl/csv，不消費 stdout 樣本
