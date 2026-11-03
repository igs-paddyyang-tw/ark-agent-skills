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

## BQ: 憑證檔「was not found」／could not automatically determine credentials
**先別懷疑金鑰遺失** —— 最常見根因是 `GOOGLE_APPLICATION_CREDENTIALS` 設成**相對路徑**
（如 `secrets/<sa-key>.json`）：從專案根手動跑 OK，但排程／daemon 觸發的 agent
`working_directory` 不是專案根（如 `agents/<name>/`）→ 相對路徑解析失敗。依序三查：

```bash
echo "GAC=${GOOGLE_APPLICATION_CREDENTIALS:-<未設>}"   # ① 是相對還是絕對
pwd; realpath "$GOOGLE_APPLICATION_CREDENTIALS"         # ② 以當下 cwd 解析到哪
ls -la "$(realpath "$GOOGLE_APPLICATION_CREDENTIALS")"  # ③ 檔案存在性與權限
python scripts/db_health.py --db-type bigquery          # 逐項診斷（credentials_env → 連線 → 最小查詢）
```

修法：在服務啟動時（`.env`／systemd `Environment=`）就把 GAC 設成**絕對路徑**；
程式端若必須吃相對路徑，以專案根哨兵（如 `team.yaml`／`agents.yaml`）定位後再絕對化。
驗證時**從非專案根的 cwd 重跑**一次，才算模擬到排程環境。未設 GAC 且確定走 ADC 時才設 `ARK_BQ_ADC_OK=1`。

## BQ: No module named 'google.cloud'（DRIVER_MISSING）
不一定是沒裝 —— agent（LLM）常自行打系統 `python` 而非專案 `.venv/bin/python`，
`google-cloud-bigquery` 只裝在 venv。先確認 `python -c "import sys; print(sys.executable)"`；
修法是呼叫時寫死 venv 直譯器，或 systemd unit 的 `PATH` 把 `.venv/bin` 排最前。
確認是同一個直譯器仍缺套件，才照 hint `pip install`。

## MongoDB: ServerSelectionTimeoutError
host/port 錯或網路不通。db_health.py 的 connect_and_ping 會給出實際錯誤字串。

## pymssql 安裝失敗（缺 FreeTDS）
Linux: `apt-get install freetds-dev` 後重裝。Windows 用官方 wheel 通常免編譯。

## stdout 不是合法 JSON
v3.0 起 stdout 純度已機制化：所有 driver 呼叫的輸出重導至 stderr，
stdout 保證只有單一 JSON object。若仍見混入，屬 P2 bug（不該再需要「取最後一行」）。
