# 報告契約對照（與 ark-code-spec-validator 共用）

兩個 validator 產出的報告都是 ark-md-report `review` 型，下游（CollectorRunner、wiki ingest）用同一套路由。

## frontmatter 對照

| 欄位 | ark-code-spec-validator | ark-prompt-spec-validator |
|------|------------------------|---------------------------|
| `subject` | repo 路徑 | 被驗證 md 的 repo 相對路徑 |
| `source_skill` | ark-code-spec-validator | ark-prompt-spec-validator |
| `score` | drift_score（API 0.5 / dep 0.2 / test 0.3） | L1 0.4 / L2 0.6 |
| `score_version` | "v2" | "v1"（本 skill 獨立計版，不與 code validator 混比） |
| `verdict` | sound / needs-work / broken | 同 |
| `findings` | 由 drift 條目統計 | L1 finding + L2 失敗案例統計 |
| `tags` | 依 wiki 受控詞彙 | 預設 `[skill-review, prompt]`，`--tags` 覆寫；有 wiki 時對照 schema.md 白名單 |

## log line

`prompt_report.py --log <path>` 追加 pipe-delimited 一行，格式對齊 code validator 的 log.md 精神（不含空格）：

```
date|sha|subject|score|l1|l2|verdict|scoring_version
2026-09-11|e9c1945|ark-agent-skills/ark-db-query/SKILL.md|84|90|80|needs-work|1
```

`l2` 無值時填 `N/A`。建議路徑：`knowledge/{proj}/wiki/operations/prompt-drift-log.md`，與 `drift-report.md` 同目錄。

正式歸檔走 ark-md-report 的 `report_register.py`（`docs/reports/log.md` + `_index.md`），本 log 只是給 CollectorRunner 的輕量趨勢線。

## 兩個 validator 的分工

| | ark-code-spec-validator | ark-prompt-spec-validator |
|---|---|---|
| 比對對象 | Python code ↔ spec/design doc | Markdown 提詞 ↔ schema + 行為預期 |
| 判定性質 | 全靜態 deterministic | L1 deterministic；L2 機率性（N 次取通過率） |
| 觸發詞 owner | drift report、驗證 spec、API 比對、AC 覆蓋 | 驗證提詞、prompt drift、SKILL.md 檢查、steering 驗證、提詞 eval |
| 不做 | 提詞內容 | code / import / test |
