---
name: ark-chart-generator
description: |
  [DEPRECATED — 已併入 ark-pipeline-recipes（讀 references/chart-generator.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 chart_generator.py 標準化圖表 Skill，使用 Matplotlib 將結構化數據轉換為圖表， 輸出至 artifacts/charts 目錄。支援折線圖、長條圖、散點圖、圓餅圖、直方圖五種圖表類型。 適用於報表生成、數據分析與 Workflow 自動化流程，可供 PDF 報表或 Dashboard 使用。 使用此 Skill 當使用者提及圖表、chart、視覺化、折線圖、長條圖、圓餅圖、 散點圖、直方圖、matplotlib、報表圖表、數據圖表、 或任何需要將數據轉換為圖片的場景。
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

# ark-chart-generator（已併入 ark-pipeline-recipes）

本 skill 已併入 **`ark-pipeline-recipes`**，內容原樣搬到 `ark-pipeline-recipes/references/chart-generator.md`。請改讀那一頁。

消費端若還沒有 `ark-pipeline-recipes`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：內容移至 `ark-pipeline-recipes/references/chart-generator.md`，本目錄只留轉址；角色對照表改指 ark-pipeline-recipes |
