---
name: ark-anomaly-detector
description: |
  [DEPRECATED — 已併入 ark-pipeline-recipes（讀 references/anomaly-detector.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 KPI 異常偵測模組 + 告警規則引擎 + MCP Tool + 排程整合。 支援 Z-score、IQR、移動平均偏差三種偵測演算法， 告警規則以 YAML 配置，支援 Telegram/Slack 通知。 使用此 Skill 當使用者提及異常偵測、告警規則、KPI 監控、 anomaly detection、數據告警、指標異常、DAU 突降、 或任何需要自動偵測數據異常並發送通知的場景。
metadata:
  version: "2.0.0"
  schema_version: "1.2"
  status: deprecated
  updated: 2026-10-29
  category: pipeline
  form: instruction
  domain: general
  author: paddyyang
---

# ark-anomaly-detector（已併入 ark-pipeline-recipes）

本 skill 已併入 **`ark-pipeline-recipes`**，內容原樣搬到 `ark-pipeline-recipes/references/anomaly-detector.md`。請改讀那一頁。

消費端若還沒有 `ark-pipeline-recipes`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：內容移至 `ark-pipeline-recipes/references/anomaly-detector.md`，本目錄只留轉址；角色對照表改指 ark-pipeline-recipes |
