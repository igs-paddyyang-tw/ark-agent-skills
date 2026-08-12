# 蒸餾規則（報告 → Wiki synthesis）

報告（docs/reports/，時點快照）與 wiki 頁面（長期演化知識）的銜接契約。
承接 `report_register.py --wiki` 的 source 建議。

## 觸發條件

| 情境 | 動作 |
|------|------|
| 同 subject 累積 ≥2 份報告 | 開（或更新）該 subject 的 synthesis 頁 |
| 單份報告含 P0 finding 且 subject 無對應頁 | 開 entity/system 頁，sources 指向報告 |
| report_register --wiki 有命中建議 | 將報告路徑加入命中頁面的 sources，並更新該頁內容 |
| 報告 verdict 與現有頁面結論矛盾 | 不改寫 —— 用矛盾標記並列，等人裁決 |

## 開新頁 vs 更新舊頁

- **更新**：subject 相同、結論方向一致 → 更新既有頁內容與 `updated`，sources 追加新報告
- **開新頁**：新 subject，或既有頁已 mature 且新結論推翻它 → 開新頁 + 舊頁加矛盾標記互連
- 蒸餾產物一律 `trust: llm-distilled`、`approved: false`、`status: seedling` —— 人工審核後才升級

## 引用格式

- 引用報告結論：`（[報告](../../docs/reports/review/2026-08-11-xxx.md#F-3)，verdict: needs-work）`
- Finding/Decision 級引用用穩定 ID（#F-x / #D-x），不引行號
- provenance 欄位記來源鏈：`report:docs/reports/review/xxx.md#F-3`

## 禁止事項

- ❌ 把報告全文複製進 wiki/（報告留在 docs/reports/，wiki 只留蒸餾結論 + source 連結）
- ❌ 蒸餾時強化或弱化原報告語氣（confidence: low 的推測不得寫成事實）
- ❌ 自創 tag（走 wiki_taxonomy propose）
- ❌ 解決矛盾（只標記，`> ⚠️ **矛盾**：報告 A 說 X，頁面原結論 Y，待釐清`）

## 蒸餾後檢查清單

1. `wiki_guard scan {新頁}` — 蒸餾內容也過消毒（引用的報告片段可能含污染）
2. `wiki_taxonomy check --schema {schema} {新頁}` — tags 合規
3. `wiki_lint --schema {schema}` — frontmatter 完整（含 trust/approved）
4. 索引重建 + `wiki_index --freshness` 確認
5. log.md 追加：`{date} | distill | {page} | llm-distilled | {agent} | from {report-path}`
