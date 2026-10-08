---
name: ark-spec-executor
description: |
  讀取 ark-superpowers 產出的 plan.md（7 欄任務表 + AC-ID + 依賴），以 deterministic 腳本
  解析契約 → DAG 排序 → 逐任務派給 runner 實作 → AC 機械驗收（留證據）→ checkpoint →
  驗收報告 + pipeline 狀態 + 迴圈判定。CIV 模式（Coordinator-Implementor-Verifier）：腳本當
  Coordinator/Verifier，LLM 只當 Implementor。
  使用此 Skill 當使用者提及 執行計畫、跑 plan、run plan、自動交付、spec executor、驗收、
  按計畫執行、把 plan 跑完、/execute，或 validator 分流回「missing_in_code 為主 → 補實作」。
  不適用於：plan 還沒寫請先用 ark-superpowers；需求釐清請用 ark-grill-me；跑完後的 code↔docs
  一致性請用 ark-code-spec-validator（本 skill 只驗「任務有沒有做完」，不驗「文件有沒有對齊」）。
metadata:
  version: "2.0.0"
  schema_version: 1
  status: active
  updated: 2026-09-30
  category: process
  outputs:
    - format: md
      audience: both
  depends_on: [ark-superpowers, ark-code-spec-validator]
  author: paddyyang
---

# ark-spec-executor v2 — 讓 plan 可執行、可驗收、可中斷續跑

v1 是純文件 skill：解析、排序、驗收、重試、報告全靠 LLM 即興，plan 格式還停在舊 5 欄。
v2 把 Coordinator 與 Verifier 全部落成腳本：**LLM 只做一件事——照 prompt 寫出 `output_file`**。
其餘（契約檢查、DAG、驗收方法解析、證據、checkpoint、越界守衛、報告、pipeline）零 LLM。

## 資產地圖

| 路徑 | 職責 | 何時用 |
|------|------|--------|
| `scripts/plan_lint.py` | plan 契約 lint（PL-001~007）；superpowers doc_lint **SP-070 的委派端** | 拿到 plan 第一步；exit 2 = 骨架 FAIL 拒跑 |
| `scripts/plan_parse.py` | 解析 7/4 欄表 → tasks.json；依賴（隱含序號 + `[← X.Y]`）；Kahn 拓撲（milestone 優先）；`--dry-run` 印執行順序 | 執行前預覽 |
| `scripts/ac_verify.py` | 依 `references/verify-methods.md` 解析驗證方法並執行，留指令/exit/證據；無法驗證 = pending **不算通過** | run_plan 內建呼叫；也可單獨驗某任務 |
| `scripts/run_plan.py` | 執行引擎：runner 派工 → 驗收 → checkpoint；重試注入證據；human 任務 blocked；依賴失敗 skipped；越界寫入守衛；task/plan timeout | 主入口 |
| `scripts/report_gen.py` | 驗收報告 + `docs/pipeline/<feature>.yaml`（phase=execute、append acceptance_rates）+ 迴圈判定（閾值從 validator 的 loop-rules.md 解析，不硬編碼） | run 之後 |
| `references/plan-contract.md` | **AC-ID 的唯一定義端**（superpowers id-scheme 委派）+ 任務表契約 + 任務狀態機 | 寫/改 plan 時 |
| `references/verify-methods.md` | 驗證方法優先序（verify: 提示 > tests/ 路徑 > AC 關鍵字 > manual） | 寫 AC 時 |
| `references/task-prompt.md` | Implementor prompt 模板（單任務、只寫 output_file、docstring 標 AC） | run_plan 自動套 |
| `references/runners.yaml` | runner 指令模板（kiro / claude；flags 依實際 CLI 核對） | 切真 runner 前 |
| `tests/fixtures/` | plan-valid / plan-cycle / plan-badrole | lint 回歸 |
| `scripts/tests/test_spec_executor_cli_contract.py` | 五支 `--help` 零依賴、守衛先於第三方 import | 改腳本後 |

## 工作流

```bash
# 0. 開頭：讀 docs/pipeline/<feature>.yaml 取 plan_path；loop_count ≥ 3 → 保險絲，停下問人（loop-rules.md）
python scripts/plan_lint.py docs/plans/<name>-plan.md                 # 1. 契約：P0 拒跑、P1 建議修、P2 標 manual 列
python scripts/plan_parse.py docs/plans/<name>-plan.md --dry-run      # 2. 看執行順序與每列的驗證方法（auto/manual）
python scripts/run_plan.py docs/plans/<name>-plan.md --workspace . --runner dry   # 3a. 乾跑：產全部 prompt、跑驗收，不執行
python scripts/run_plan.py docs/plans/<name>-plan.md --workspace . --runner kiro  # 3b. 真跑（或 claude / cmd --exec）
python scripts/report_gen.py docs/plans/<name>-plan.md --workspace .  # 4. 報告 + pipeline + 迴圈判定
```

步驟 3 中斷（timeout / 當機 / 人為 Ctrl-C）後**直接重跑同指令**：checkpoint 跳過已 pass，只重做 fail。
`--milestone N` 只跑一段；`--no-resume` 從頭；`--strict-scope` 越界寫入視為 fail 並 git 還原。

## 任務狀態機與驗收率

`pass | fail（重試 ≤ max-retries）| blocked（human，等人工）| skipped（依賴未完成）| pending（無法自動驗證）`
acceptance_rate = pass / total × 100（total 含全部狀態）。**只有 pass 算數**——pending 與 blocked 都不是「差不多完成」。

| 驗收結果 | 判定（閾值讀 loop-rules.md） | 動作 |
|----------|---------------------------|------|
| ≥ ship | `ship` | 自動觸發 ark-code-spec-validator 做 drift check |
| retry ≤ x < ship | `retry_failed` | 報告列修復清單 → `run_plan.py` 重跑（resume 只跑失敗項） |
| < retry | `stop` | 停，依方向分流：missing_in_code 為主 → 回本 skill；mismatch 為主 → ark-grill-me |

## 穩定性設計（v2 相對 v1 的差異，全部可驗）

| 風險 | v1 | v2 |
|------|----|----|
| plan 格式漂移 | LLM 猜欄位 | plan_lint 嚴格欄數 / 角色枚舉 / AC-ID 唯一 / 依賴存在 / 無環，P0 拒跑 |
| 驗收靠關鍵字猜 | 「其他 → output 內容分析」 | 四層解析，猜不到 = pending 不算通過；每筆留指令+exit+證據 |
| 中斷後重來 | 有 checkpoint 描述、無實作 | 每任務落盤（atomic replace），resume 預設開 |
| 重試無方向 | 「更詳細 prompt」 | 上輪驗收證據與 runner log 注入下輪 prompt |
| agent 越界改檔 | 「只能寫 output_file」（無守門） | git 變更比對 output_file，警告；--strict-scope 還原並判 fail |
| human 任務 | 未定義 | blocked，不阻塞非依賴任務，報告列人工待辦 |
| 閾值散落 | SKILL.md 硬寫 90/70 | 從 loop-rules.md 解析，找不到才用預設並標明 |
| 幽靈引用 | plan-contract.md / plan_lint.py 不存在 | 兩者皆實體化，superpowers 與 validator 的委派可兌現 |

## Runner 設定

`references/runners.yaml` 的 kiro / claude 模板佔位 `{prompt_file} {cwd} {output_file} {task_id} {role}`。
角色人格：run_plan 找 `agents/<role>-agent/.kiro/steering/SOUL.md` 注入 prompt，找不到用預設。
**先 `--runner dry` 確認每個任務的 prompt 與驗證方法都合理，再切真 runner**——dry 跑完的 pending 列就是 plan 要補 `verify:` 的地方。

## 與上下游的契約

- **上游 superpowers**：任務表 7 欄契約、角色枚舉、`[← X.Y]`、`related_spec/design` frontmatter；SP-070 委派 plan_lint.py（exit 0/1/2）
- **下游 validator**：AC-ID `AC-NNN` + 測試 docstring `AC: AC-NNN`（ac_verify 對 pytest 任務檢查標記，缺則警告）；pipeline 狀態檔 schema；loop-rules 閾值與分流
- **本 skill 不做**：不寫 spec/design（superpowers）、不驗 code↔docs 對齊（validator）、不解 rebase 衝突、不安裝依賴（缺 pytest 等環境問題導向 ark-env-doctor）

## 邊界

- 只寫 plan 指定的 output_file 與 `data/`、`docs/reports/`、`docs/pipeline/`
- 單任務 timeout 預設 900s、全 plan 3600s、重試 2 次——皆可參數化
- LLM 呼叫成本歸 runner 端記錄；本 skill 只記 duration
