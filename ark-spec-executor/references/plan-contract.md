# plan-contract.md — plan 任務表契約與 AC-ID 擁有權（ark-spec-executor 為 AC- 唯一定義端）

> superpowers 的 id-scheme.md 將 `AC-NNN` 委派本檔定義；validator 的 ac-id-convention.md 定義 test 端標記。
> 三方以 `depends_on` 互引，定義只寫一次。

## 任務表

| 版型 | 表頭（欄數嚴格） |
|------|----------------|
| plan-full | `\| # \| 任務 \| 角色 \| 產出檔案 \| 估時 \| AC-ID \| AC \|`（7） |
| plan-onepager | `\| # \| 任務 \| 產出檔案 \| AC \|`（4，角色由產出路徑推斷：tests/→qa、含 prompt/llm/agent/skill→ai-dev、其餘 coder） |

## 欄位

| 欄 | 規則 |
|----|------|
| # | `{milestone}.{seq}`；同 milestone 依序號隱含依賴（1.2 ⇐ 1.1）；跨 milestone 在任務名尾 `[← X.Y]`（可多個） |
| 角色 | `coder` / `ai-dev` / `qa` / `human`，大小寫不敏感；human = 執行時 blocked 等人工，不算通過 |
| 產出檔案 | 相對路徑，唯一允許寫入的範圍（run_plan 以 git 變更比對越界）；不可為佔位符 |
| AC-ID | `AC-NNN`，全檔唯一，刪除不重用；**由 executor 配號**（superpowers 產 plan 時留空或用 build_docs 委派） |
| AC | 一條原子驗收條件；可含 `verify:` 提示（見 verify-methods.md）；沒有可自動驗證方法者以 manual 處理，不算通過 |

## DAG
- Kahn 拓撲排序；同層依 (milestone, seq) 穩定排序
- 循環依賴 → P0 拒跑；依賴指向不存在任務 → P0

## 狀態機（每任務）
`todo → running → pass | fail → (retry ≤ N) → fail` ；`blocked`（human）；`skipped`（依賴 fail/blocked/skipped）；`pending`（無法自動驗證）
acceptance_rate = pass / total × 100（total 含 blocked/pending/skipped）
