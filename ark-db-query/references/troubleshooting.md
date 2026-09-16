# 錯誤碼處置對照

| error.code | 意義 | agent 處置 |
|------------|------|-----------|
| DRIVER_MISSING | 驅動未安裝 | 依 hint 執行 pip install 後重跑一次；再失敗回報使用者 |
| CONN_FAILED | 連線失敗 | 跑 `db_health.py --db-type ...` 取得逐項診斷，回報失敗的 check |
| QUERY_FAILED | SQL/查詢錯誤 | 先跑 `bq_schema.py schema` 核對欄位名與型別，修正 SQL 重跑 |
| GATE_BLOCKED | 守門攔截（exit 3） | 掃描超限 → 縮小掃描範圍（見 bq-cookbook）；寫入攔截 → 確認意圖後 --allow-write；`--gate-explain` 看被哪層擋 |
| BUDGET_EXCEEDED | 每日預算攔截（exit 4） | 停止並回報使用者；確認業務必要才調高 `ARK_BQ_DAILY_BUDGET_USD` |
| BAD_INPUT | 參數錯誤（exit 2） | 依 message 修正呼叫參數；ledger 目錄不可寫也走此碼 → 設 `ARK_DB_LEDGER_DIR` |
| TIMEOUT | 查詢逾時（exit 7，BQ job 已 cancel） | 縮小掃描範圍或提高 `--query-timeout` |

# 常見情境

## BQ: dry-run 顯示 would_exceed_cap=true
優先順序：加分區欄位過濾（_PARTITIONDATE / date 欄）→ SELECT 指定欄位取代 * →
加 TABLESAMPLE SYSTEM (1 PERCENT) 做探索性分析。只有確認業務必要才調高 --max-bytes-billed。

## BQ: 403 Access Denied
GOOGLE_APPLICATION_CREDENTIALS 指向的服務帳號缺 roles/bigquery.jobUser（跑查詢）
或 roles/bigquery.dataViewer（讀表）。回報使用者補權限，不要嘗試其他憑證。

## MongoDB: ServerSelectionTimeoutError
host/port 錯或網路不通。db_health.py 的 connect_and_ping 會給出實際錯誤字串。

## pymssql 安裝失敗（缺 FreeTDS）
Linux: `apt-get install freetds-dev` 後重裝。Windows 用官方 wheel 通常免編譯。

## stdout 不是合法 JSON
v3.0 起 stdout 純度已機制化：所有 driver 呼叫的輸出重導至 stderr，
stdout 保證只有單一 JSON object。若仍見混入，屬 P2 bug（不該再需要「取最後一行」）。
