# Pipeline State Schema

> 工作流鏈的狀態持久化格式。每個 feature 一份 YAML 檔案，記錄當前進度與歷史分數。
> 四個 Skill（grill-me / superpowers / spec-executor / validator）開頭讀取、結尾寫入。

---

## 檔案路徑

```
docs/pipeline/{feature}.yaml
```

- `{feature}`：kebab-case 功能名稱（與 plan.md 檔名對齊）
- 範例：`docs/pipeline/user-auth-refactor.yaml`

---

## Schema 定義

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `feature` | string | ✅ | 功能名稱（同檔名） |
| `phase` | enum | ✅ | 當前階段：`grill` / `spec` / `execute` / `validate` / `shipped` |
| `decision_summary_path` | string | | grill-me 產出的決策摘要路徑 |
| `spec_path` | string | | superpowers 產出的 spec 路徑 |
| `design_path` | string | | superpowers 產出的 design 路徑 |
| `plan_path` | string | | superpowers 產出的 plan 路徑 |
| `acceptance_report_path` | string | | spec-executor 產出的驗收報告路徑 |
| `drift_report_path` | string | | validator 產出的 drift report 路徑 |
| `drift_scores` | list[float] | ✅ | 歷次 drift_score 陣列（append-only） |
| `acceptance_rates` | list[float] | | 歷次 acceptance_rate 陣列（append-only） |
| `loop_count` | int | ✅ | 迴圈執行次數（從 0 開始） |
| `last_direction` | enum | | 最近一次分流方向：`update_docs` / `fix_code` / `clarify_requirements` / `ship` |
| `created_at` | datetime | ✅ | 首次建立時間（ISO 8601） |
| `updated_at` | datetime | ✅ | 最後更新時間（ISO 8601） |

---

## 完整 YAML 範例

```yaml
# docs/pipeline/user-auth-refactor.yaml
feature: user-auth-refactor
phase: validate
decision_summary_path: docs/one-pagers/user-auth-refactor.md
spec_path: docs/specs/user-auth-refactor-spec.md
design_path: docs/designs/user-auth-refactor-design.md
plan_path: docs/plans/user-auth-refactor-plan.md
acceptance_report_path: docs/reports/user-auth-refactor-plan-acceptance.md
drift_report_path: knowledge/team-agent/wiki/operations/drift-report.md
drift_scores:
  - 62.5
  - 78.0
  - 91.5
acceptance_rates:
  - 85.7
  - 95.2
loop_count: 2
last_direction: fix_code
created_at: "2026-08-10T14:30:00+08:00"
updated_at: "2026-08-11T09:15:00+08:00"
```

---

## 各 Skill 的讀寫行為

### ark-grill-me

- **開頭**：檢查 `docs/pipeline/{feature}.yaml` 是否存在。若存在且 `phase != grill`，提示使用者「此 feature 已進入 {phase} 階段，確定要回到拷問嗎？」
- **結尾**：建立或更新狀態檔，設定 `phase: grill`，寫入 `decision_summary_path`

### ark-superpowers

- **開頭**：讀取狀態檔，取得 `decision_summary_path` 作為輸入 context
- **結尾**：更新 `phase: spec`，寫入 `spec_path` / `design_path` / `plan_path`

### ark-spec-executor

- **開頭**：讀取狀態檔，取得 `plan_path`；檢查 `loop_count` 是否觸發保險絲（≥ 3 → 人工介入）
- **結尾**：更新 `phase: execute`，append `acceptance_rates`，寫入 `acceptance_report_path`

### ark-code-spec-validator

- **開頭**：讀取狀態檔，取得 `loop_count` + `drift_scores` 歷史
- **結尾**：更新 `phase: validate`（或 `shipped`），append `drift_scores`，更新 `loop_count += 1`，寫入 `last_direction` + `drift_report_path`

---

## 狀態機流程圖

```
         ┌──────────────────────────────────┐
         │                                  │
    ┌────▼────┐    ┌──────┐    ┌─────────┐  │  ┌──────────┐    ┌─────────┐
    │  grill  │───▶│ spec │───▶│ execute │──┼─▶│ validate │───▶│ shipped │
    └─────────┘    └──────┘    └─────────┘  │  └──────────┘    └─────────┘
         ▲                          ▲       │       │
         │                          │       │       │
         └──── clarify_requirements ┼───────┘       │
                                    │               │
                                    └── fix_code ───┘
```

---

## 注意事項

- `drift_scores` 和 `acceptance_rates` 是 append-only，不可覆寫歷史值
- `loop_count` 只在 validator 結尾遞增（代表完成一輪完整迴圈）
- 狀態檔不存在時，由第一個觸發的 Skill 建立（通常是 grill-me）
- `docs/pipeline/` 目錄應加入 `.gitignore`（狀態檔為本地工作狀態，非交付物）

---

## 版本

- v1.0 — 2026-08-11 初版
