# test-report 契約 v1

`aiqa_report.py --run <run>` 產出：
- `test-report.md`：frontmatter（run_id / game / machine / backend / device / reader / visual / checklist sha / pack sha / protocol / model / 起訖）→ 摘要表（總數、六種 verdict、自動化率、與人工一致率、**誤 PASS**、耗時 / LLM 呼叫）→ §1 依公司分類樹（可貼回「總進度」）→ §2 FAIL（斷言、期望 vs 實際、證據路徑、重現步驟、規格依據、人工對照）→ §3 與人工不一致 → §4 NEEDS_HUMAN → §5 BLOCK → §6 FLAKY → §7 N/A → §8 附錄
- `test-results.xlsx`：sheet「aiqa結果」= 公司欄位（編號 / 類別 / 項目 / 測試目的 / 步驟 / 重複次數 / 預期結果 / 執行人員=aiqa / Android / iOS / 測試日期 / 備註 / Mantis單號）+ aiqa verdict + 證據；sheet「總進度」= 原表格式
- `mantis-drafts.md`：每個 FAIL 一張（摘要 / 重現 / 期望 / 實際 / 附件 / 環境）
- `benchmark.json`：M1 自動化率、M2 誤 PASS、M3 一致率（可比數）、M4 NEEDS_HUMAN、M6 每項秒數、M7 FLAKY 率、by_tier

run 目錄：`manifest.json`、`results.json`、`items/<id>/verdict.json`、`items/<id>/rep-k/{step-*.png, roi-*.png, cap-*.png, observations.json, verdict.json, trace.jsonl}`。
