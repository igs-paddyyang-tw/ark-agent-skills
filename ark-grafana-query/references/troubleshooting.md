# Grafana Skill 故障排除

## 錯誤碼對照

| code | 原因 | 處置 |
|------|------|------|
| `AUTH_FAILED` | Token/帳密錯誤或過期 | 確認 .env 的 GRAFANA_TOKEN 或 GRAFANA_USER + GRAFANA_PASSWORD |
| `CONN_FAILED` | 連不到 Grafana | 確認 GRAFANA_URL 正確、網路可達、防火牆放行 |
| `NOT_FOUND` | Dashboard UID 或 Panel ID 不存在 | 用 `grafana_dashboards.py list` 確認 UID |
| `QUERY_FAILED` | 查詢執行失敗 | 檢查 expr 語法（PromQL/LogQL）是否正確 |
| `BAD_INPUT` | 參數不足或格式錯 | 參照 SKILL.md 呼叫範例 |

## 常見問題

### Q: 連線成功但查不到數據
- 確認時間範圍內有資料（`--from 7d` 試試）
- 確認 datasource-uid 正確（用 Grafana UI 的 datasource 頁面看 UID）
- Prometheus 的 `up` 指標是最好的測試：`--expr "up" --from 5m`

### Q: Panel 查詢回空
- 該 Panel 可能是 stat/gauge 類型（只取最新值）→ 改用 `--from 5m`
- Panel 可能用了 variable template → 直接用 `--datasource-uid` + `--expr` 模式

### Q: InfluxDB panel 查詢（netdata 系統監控等）
- InfluxDB panel 的 target 沒有 `expr`，用 `measurement`/`select`/`tags` 結構
- skill 會自動把原生 target 整包送 `/api/ds/query`，由 Grafana 代理翻譯 InfluxQL
- 回傳每筆帶 `series`（series 名稱）、`time`（ISO）、`value`
- 若回 500：多半是 target 帶了 dashboard variable（如 `$__interval` 以外的自訂變數），
  這類需在 UI 端展開；純系統指標（cpu/ram/disk）不受影響

### Q: Loki 查詢超時
- 縮小時間範圍（`--from 15m`）
- 加入更多 label 過濾（`{job="xxx", level="error"}`）
- 用 `--limit 20` 限制結果

### Q: 401 但帳密確定對
- Grafana 9+ 預設停用 Basic Auth → 需開啟或改用 Service Account Token
- 設定路徑：Grafana → Administration → Service Accounts → 建立 Token

### Q: 如何找 Datasource UID
```bash
python grafana_dashboards.py panels --uid "YOUR_DASHBOARD_UID"
# 看 datasource 欄位
```
或直接呼叫：
```bash
# 列出所有 datasource（需 admin 權限）
python -c "
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
sys.path.insert(0, 'scripts')
import grafana_common as C
C.load_env()
import json
print(json.dumps(C.grafana_get('/api/datasources'), indent=2, ensure_ascii=False))
"
```
