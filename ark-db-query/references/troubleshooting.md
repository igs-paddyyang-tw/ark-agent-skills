# 錯誤碼處置對照

| error.code | 意義 | agent 處置 |
|------------|------|-----------|
| DRIVER_MISSING | 驅動未安裝 | 依 hint 執行 pip install 後重跑一次；再失敗回報使用者 |
| CONN_FAILED | 連線失敗 | 跑 `db_health.py --db-type ...` 取得逐項診斷，回報失敗的 check |
| QUERY_FAILED | SQL/查詢錯誤 | 先跑 `bq_schema.py schema` 核對欄位名與型別，修正 SQL 重跑 |
| GATE_BLOCKED | 守門攔截 | 掃描超限 → 縮小掃描範圍（見 bq-cookbook）；寫入攔截 → 確認意圖後 --allow-write |
| BAD_INPUT | 參數錯誤 | 依 message 修正呼叫參數 |

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
腳本保證 stdout 只有一個 JSON object；若混入其他輸出，多半是驅動套件印了警告 ——
以最後一行 JSON 為準，並回報此現象（屬 P2 bug）。
