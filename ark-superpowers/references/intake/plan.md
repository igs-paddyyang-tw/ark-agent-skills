# intake/plan.md — plan 訪談題庫（ADR-005）

plan 的任務表契約由 `ark-spec-executor` 的 plan-contract v2 擁有；本題庫只引導填內容。

| # | 章節鍵 | 問題 | 產出 |
|---|--------|------|------|
| 1 | summary | 這份 plan 要交付 spec/design 的哪些部分？ | 摘要 |
| 2 | milestones | 分幾個里程碑（Wave）？每個的 deterministic 放行閘門是什麼？ | 里程碑（AC-x 由 executor 配號） |
| 3 | risk | 最可能出錯的地方？緩解措施？ | 風險管理 |
| 4 | verification | 怎麼驗每個里程碑真的完成（不以「感覺」放行）？ | 驗證標準 |
| 5 | rollback | 出事怎麼回滾？ | 回滾計畫 |

> 任務表欄位與 AC-ID 配號交 `ark-spec-executor/scripts/plan_lint.py` 驗（doc_lint plan 型委派）。
> 每個里程碑的閘門要能用 exit code / grep 判定，不用 prose 期望。
