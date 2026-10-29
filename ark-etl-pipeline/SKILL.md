---
name: ark-etl-pipeline
description: |
  [DEPRECATED — 已併入 ark-pipeline-recipes（讀 references/etl-pipeline.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 etl_pipeline.py 資料轉換 Skill，將任何資料來源（CSV、JSON、API 回傳、 Skill 輸出、資料庫查詢）轉換為 chart_generator 可直接使用的標準格式 （x/y/labels 陣列）。支援欄位選取、篩選、排序、聚合、分組統計。 適用於 Workflow 中串接資料來源與圖表產生。 使用此 Skill 當使用者提及 ETL、資料轉換、資料清洗、data transform、 資料管線、資料前處理、轉換格式、 或任何需要將原始資料轉換為圖表標準格式的場景； 也涵蓋管線最後的 Load/匯出步驟 —— 提及匯出檔案、存成 CSV、輸出 JSON、 產生 Markdown 檔、資料備份時，用本 skill 的匯出章節將結果寫入磁碟。
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

# ark-etl-pipeline（已併入 ark-pipeline-recipes）

本 skill 已併入 **`ark-pipeline-recipes`**，內容原樣搬到 `ark-pipeline-recipes/references/etl-pipeline.md`。請改讀那一頁。

消費端若還沒有 `ark-pipeline-recipes`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：內容移至 `ark-pipeline-recipes/references/etl-pipeline.md`，本目錄只留轉址；角色對照表改指 ark-pipeline-recipes |
