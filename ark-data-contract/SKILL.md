---
name: ark-data-contract
description: |
  [DEPRECATED — 已併入 ark-pipeline-recipes（讀 references/data-contract.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：當使用者需要驗證管線元件間的 schema 契約時使用此技能。觸發條件包括：提及「資料契約」「schema 驗證」「管線契約」，或需要確保上下游元件的輸入/輸出格式一致。適用於 ETL 管線、agent 間訊息傳遞、API 回應格式的契約定義與驗證。
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

# ark-data-contract（已併入 ark-pipeline-recipes）

本 skill 已併入 **`ark-pipeline-recipes`**，內容原樣搬到 `ark-pipeline-recipes/references/data-contract.md`。請改讀那一頁。

消費端若還沒有 `ark-pipeline-recipes`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：內容移至 `ark-pipeline-recipes/references/data-contract.md`，本目錄只留轉址；角色對照表改指 ark-pipeline-recipes |
