---
name: golden-questions
description: 為指標建立或執行 golden questions 評測集，回報通過率並判定是否可保持 queryable
layer: work
roles: [semantic-keeper, admin]
tools_required: []
inputs: [metric_id, mode]
outputs:
  format: data
  contract: md-report
example: true
---

## 任務

mode = `build`：為 metric_id 產至少 3 題自然語言問題，每題附標準答案（數值 + 分子/分母/時間窗）與判定容差；問題要覆蓋：直接查、帶時間比較、帶維度切分。
mode = `run`：把每題交給 query-analyst 執行，比對回傳值與標準答案（容差內為 pass），產通過率；<95% 則建議 bi-lead 將該指標鎖回 `draft`。

規則：標準答案由已核可的查詢或月報既有數字產生，不得寫「待補」；容差用絕對值或 pp 明寫。

## 輸出樣板

```
| # | 問題 | 標準答案 | 容差 | 結果（run 時） |
|---|------|---------|------|---------------|
通過率：<pass/total>（門檻 95%）→ 判定：保持 queryable / 鎖回 draft
失敗題分析（run 時）：<題號｜回傳值｜差異｜疑似原因（契約/SQL/資料）>
```

## 範例

### 輸入
metric_id：`cpi_index`；mode：`run`

### 期望輸出
| # | 問題 | 標準答案 | 容差 | 結果 |
|---|------|---------|------|------|
| 1 | 2026-05 整體 CPI 指數 | 64（基準=13 個月付費渠道平均 100） | ±1 | pass（64） |
| 2 | 2026-05 vs 2025-06 CPI 指數變化 | 173→64，-63% | ±2pt | pass |
| 3 | 2026-05 各渠道 CPI 指數 | ASA 21 / GA 52 / FBA 72 / FBi 93 | ±1 | fail（FBi 回傳 88） |
| 4 | 2026-02 CPI 指數 | 83 | ±1 | pass |
通過率：3/4 = 75%（門檻 95%）→ 判定：鎖回 draft
失敗題分析：#3｜88 vs 93｜-5｜疑似 SQL 漏掉 FB iOS 的 SKAN 補回口徑（契約 v1.3 有寫，SQL 未實作）
