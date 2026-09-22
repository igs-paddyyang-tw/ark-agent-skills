---
name: exec-summary
description: 把已查證的數字與歸因寫成執行摘要／資料故事，倒金字塔、口徑原樣帶入，md/html 雙軌並戳記
layer: work
roles: [report-narrator]
tools_required: []
inputs: [analysis_artifacts, audience]
outputs:
  format: md
  contract: md-report
example: true
---

## 任務

1. 只使用 analysis_artifacts 內的數字；缺數寫「尚無數據」，不補算不重算
2. 第一段「給主管的三句話」：方向／主因／下一步；每句帶數字
3. 總表先行，分節敘事每節一張圖一個結論（圖交 viz 產出或 report-narrator 兼任時自產）
4. 口徑四件套與證據等級原樣帶入：corr 用「同期／伴隨」，因果詞只在 causal 出現
5. 依 audience 調整篇幅不調整條件（部長版 ≤1 頁；運營／行銷版含操作建議）
6. 產 ark-md-report（AI 軌）→ ark-html-report 渲染（人軌）→ report_pair.py 戳記一致才交付

## 輸出樣板

```
# <報告題：結論句>
給主管的三句話：① <方向+數字> ② <主因+證據等級> ③ <下一步>
| 指標 | 期初 | 期末 | 變化 | 證據等級 |
## 1. <節題=結論>  <一圖> <一段>
...
## 限制與下一步
口徑：<契約 id/version 清單>　戳記：<sha 前 8 碼>
```

## 範例

### 輸入
analysis_artifacts：`artifacts/reports/ua-13m-cpi.md`, `artifacts/reports/ua-13m-investigation.md`；audience：部長

### 期望輸出
# 換渠道帶來近三倍效率，預算微調沒有回報
給主管的三句話：① 方向對了——同一塊錢帶進的新玩家近三倍（CPI 指數 173→64，ROAS 指數 11→247，corr）② 主因是 2026-02 換對渠道（ASA 上線、TikTok 退場），同期成本指數 138→83，不是調參數 ③ 下一步把人力從每月 554 次預算微調搬去有對照的素材測試，並排 ASA on/off 測試把相關升級成因果
| 指標 | 2025-06 | 2026-05 | 變化 | 證據等級 |
|---|---|---|---|---|
| CPI 指數 | 173 | 64 | -63% | corr |
| D2 | 27.9% | 38.8% | +10.9pp | corr |
| ROAS 指數 | 11 | 247 | ×22 | corr |
## 1. 進步與「換對渠道」同期發生
（圖：CPI 指數 13 個月折線，2026-02 拐點標註）ASA 品牌詞成本僅大盤 1/5，但只佔月花費 3.5–8%；增量待 on/off 測試。
## 限制與下一步
全部為觀察相關；2026-06 回收未成熟。口徑：cpi_index v1.3、d2_return_rate v1.2、roas_30d_index v1.1　戳記：a3f9c21e
