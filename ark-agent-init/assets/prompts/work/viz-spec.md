---
name: viz-spec
description: 依數據 artifact 產出圖表規格與圖：圖題即結論、完整時間窗、標基準線、軸縮放必註明
layer: work
roles: [report-narrator, viz-builder]
tools_required: []
inputs: [data_artifact, question]
outputs:
  format: code
  contract: none
example: true
---

## 任務

1. 一張圖只回答 question 這一個問題；圖題寫成結論句
2. 預設完整時間窗；基準線（有 baseline 的指標）與常態區間必畫
3. 顏色只承載語意（改善/持平/變差），數字加標籤，不靠顏色單獨傳訊
4. 截斷軸或縮放區間必在圖上註明並附完整窗小圖
5. 交付 chart-definition（型別、序列、軸、標註、來源 artifact 路徑），用 ark-html-report 元件或 ark-chart-generator 生成

## 輸出樣板

```yaml
chart_id: <snake_case>
title: <結論句>
type: line | bar | dual-axis | ...
source: <data_artifact 路徑>
series: [{ name, field, role: primary|secondary|reference }]
axes: { x: <欄位/單位>, y: <單位>, y_clip: null | { from, to, note } }
annotations: [{ x, label }]
caption: <軸/區間/基準一句注意>
```

## 範例

### 輸入
data_artifact：`artifacts/reports/ua-13m-ops-count.csv`；question：「預算調整次數暴增，效率有沒有跟著變好」

### 期望輸出
```yaml
chart_id: budget_ops_vs_cpi_13m
title: 預算調整暴增 25 倍（0–22→554 次/月），同期效率未見改善
type: dual-axis
source: artifacts/reports/ua-13m-ops-count.csv
series:
  - { name: 預算調整次數, field: budget_ops, role: primary }
  - { name: CPI 指數, field: cpi_index, role: secondary }
  - { name: 常態波動帶 ±8%, field: cpi_band, role: reference }
axes: { x: 月份（2025-06→2026-06）, y: 次數／指數（基準 100）, y_clip: null }
annotations: [{ x: 2026-02, label: ASA 上線・TikTok 退場 }]
caption: 右軸為指數（基準=13 個月付費渠道平均 100）；完整時間窗，無截斷
```
