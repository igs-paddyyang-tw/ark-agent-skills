---
name: ark-kpi-calculator
description: |
  [DEPRECATED — 已併入 ark-pipeline-recipes（讀 references/kpi-calculator.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出標準化 KPI 計算引擎模組 + MCP Tool，支援遊戲類指標（DAU/MAU/ARPU/RTP/留存率/LTV） 與通用指標（轉換率/流失率/NPS）。產出 Python 模組 + MCP Tool 定義 + pytest 測試。 使用此 Skill 當使用者提及 KPI 計算、指標引擎、DAU、ARPU、RTP、留存率、 LTV、遊戲數據指標、calculate kpi、metrics engine、 或任何需要產出標準化指標計算邏輯的場景。
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

# ark-kpi-calculator（已併入 ark-pipeline-recipes）

本 skill 已併入 **`ark-pipeline-recipes`**，內容原樣搬到 `ark-pipeline-recipes/references/kpi-calculator.md`。請改讀那一頁。

消費端若還沒有 `ark-pipeline-recipes`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：內容移至 `ark-pipeline-recipes/references/kpi-calculator.md`，本目錄只留轉址；角色對照表改指 ark-pipeline-recipes |
