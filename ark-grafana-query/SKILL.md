---
name: ark-grafana-query
description: |
  Grafana 監控查詢工具箱（executor 型），agent 用 bash 直接呼叫 scripts/ 下的腳本。
  支援：列出 Dashboards/Panels、查詢 Panel 數據（Prometheus/Loki/CloudWatch/InfluxDB）、查詢告警狀態。
  使用此 Skill 當使用者或 agent 提及：系統監控、Grafana、dashboard、alert、
  metrics、日誌查詢、服務狀態、CPU/Memory/Disk、或任何需要從 Grafana 取得監控資料的場景。
metadata:
  schema_version: "1.1"
  status: active
  category: executor
  outputs:
    - { format: data, audience: ai }
  render: none
  version: "1.0.0"
  updated: 2026-09-16
  author: paddyyang
---

# ark-grafana-query

Grafana 監控查詢工具箱，agent 一行 bash 呼叫，行為 deterministic。

## Agent SOP（決策樹）

```
需求進來
├─ 不知道有哪些 Dashboard / Panel？
│    → grafana_dashboards.py list             （列出所有 dashboard）
│    → grafana_dashboards.py panels --uid XX  （列出某 dashboard 的所有 panel）
├─ 想看某個 Panel 的即時數據？
│    → grafana_query.py --uid XX --panel-id N [--from 1h] [--to now]
├─ 想直接跑 PromQL / LogQL？
│    → grafana_query.py --datasource-uid DS --expr "up{job='xxx'}" --from 1h
├─ 想看目前有哪些告警在 firing？
│    → grafana_alerts.py list [--state firing]
├─ 想看告警規則定義？
│    → grafana_alerts.py rules [--folder XX]
└─ 連不上？
     → 確認 GRAFANA_URL + GRAFANA_TOKEN / GRAFANA_USER + GRAFANA_PASSWORD 環境變數
```

## 呼叫範例（複製即用）

```bash
# 列出所有 Dashboard
python scripts/grafana_dashboards.py list

# 列出某 Dashboard 的 Panels
python scripts/grafana_dashboards.py panels --uid "abc123"

# 查詢某 Panel 近 1 小時數據
python scripts/grafana_query.py --uid "abc123" --panel-id 4 --from 1h

# 直接跑 PromQL
python scripts/grafana_query.py --datasource-uid "prometheus" --expr "rate(http_requests_total[5m])" --from 1h

# 查 Loki 日誌
python scripts/grafana_query.py --datasource-uid "loki" --expr '{job="slotverse"} |= "error"' --from 30m --limit 50

# 查看所有 firing 的告警
python scripts/grafana_alerts.py list --state firing

# 查看告警規則
python scripts/grafana_alerts.py rules
```

## 認證方式（二選一）

| 方式 | 環境變數 | 適用 |
|------|---------|------|
| API Token | `GRAFANA_URL` + `GRAFANA_TOKEN` | 推薦（Service Account Token） |
| 帳密 | `GRAFANA_URL` + `GRAFANA_USER` + `GRAFANA_PASSWORD` | Basic Auth |

## 輸出契約（統一 JSON）

```json
{
  "success": true,
  "data": {
    "rows": [...],
    "count": 42,
    "truncated": false,
    "out_file": null
  },
  "meta": {
    "tool": "grafana",
    "command": "query",
    "elapsed_ms": 234,
    "grafana_url": "http://44.193.161.132:3000"
  }
}
```

失敗：`{"success": false, "error": {"code": "...", "message": "...", "hint": "..."}}`
code 枚舉：`AUTH_FAILED | CONN_FAILED | NOT_FOUND | QUERY_FAILED | BAD_INPUT`

## Deterministic 守門

| 守門 | 機制 |
|------|------|
| read-only | 所有操作皆為 GET，不會修改 Grafana 任何設定 |
| context 保護 | stdout 預設最多 50 筆，全量走 `--out` 檔案 |
| 超時 | 預設 30s，可 `--timeout` 調整 |

## 部署方式

```
.kiro/skills/ark-grafana-query/
├── SKILL.md
├── scripts/
│   ├── grafana_common.py    ← 共用（認證/輸出/env）
│   ├── grafana_dashboards.py ← list / panels
│   ├── grafana_query.py      ← 查 panel 或直接跑 query
│   └── grafana_alerts.py     ← 告警狀態/規則
├── references/
│   └── troubleshooting.md
└── requirements.txt

環境需求（.env 或系統環境變數）：
  GRAFANA_URL=http://44.193.161.132:3000
  GRAFANA_USER=admin          # 或用 GRAFANA_TOKEN
  GRAFANA_PASSWORD=xxx

一次性安裝：
  pip install requests
```

## 誰用

| Agent | 用途 |
|-------|------|
| architect-agent | 技術日報、架構分析時查系統狀態 |
| admin-agent | 維運日報、異常排查 |
| developer-agent | 效能分析、部署後驗證 |
| tester-agent | 壓測結果查看 |

## 注意事項

- 所有腳本只做 GET，**不寫入 Grafana**（不建 dashboard、不改 alert rule）
- 認證資訊走環境變數，不要寫死在腳本或 memory 裡
- Panel 數據格式因 datasource 類型而異（Prometheus 回時序、Loki 回 log lines）
- 大量 log 查詢用 `--out` 落盤，不要塞進 stdout

## Datasource 支援

| 類型 | Panel 查詢路徑 | 備註 |
|------|--------------|------|
| Prometheus | 取 target 的 `expr` → range query | PromQL |
| Loki | 同上 fallback 到 Loki API | LogQL |
| InfluxDB | target 無 `expr` → 整包原生 target 送 `/api/ds/query` | InfluxQL/Flux 由 Grafana 代理翻譯 |
| SQL 類 | 同 InfluxDB 路徑 | rawSql 由 Grafana 執行 |

InfluxDB panel（如 netdata 系統監控）的 target 用 `measurement`/`select`/`tags`
結構而非 `expr`，skill 會自動改走原生 target 直送路徑，回傳含 `series` 名稱與 ISO 時間。
