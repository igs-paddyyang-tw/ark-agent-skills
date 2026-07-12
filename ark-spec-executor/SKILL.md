---
author: paddyyang
name: ark-spec-executor
description: |
  讀取 plan.md（含任務表+AC+依賴），自動拆解→角色切換執行→AC 驗收→產出驗收報告。
  Spec-Driven 的 CIV 模式（Coordinator-Implementor-Verifier），
  參考 Augment CIV + LangGraph Plan-and-Execute。
  使用此 Skill 當使用者提及 執行計畫、run plan、自動交付、spec executor、
  跑 plan、驗收、自動執行任務、或任何需要按 plan 逐步完成開發的場景。
---

# ark-spec-executor

讀取 execution plan，自動拆解任務 → 角色切換執行 → AC 驗收 → 驗收報告。

## 觸發條件

- 「執行 plan」、「跑 plan」、「run plan」
- 「自動交付」、「按計畫執行」
- 「spec executor」、「自動開發」
- 「把這個 plan 跑完」、「幫我執行這份計畫」
- `/execute docs/plans/xxx-plan.md`

---

## 工作流鏈定位

```
ark-grill-me（拷問設計）
    ↓ 決策摘要
ark-superpowers（產出 Spec/Design/Plan）
    ↓ docs/plans/{name}-plan.md
【ark-spec-executor】（自動執行）
    ↓ 程式碼 + docs/reports/{name}-acceptance.md
ark-code-spec-validator（驗證一致性）
    ↓ Drift Report
```

---

## 輸入

| 參數 | 必要 | 說明 |
|------|------|------|
| plan_path | ✅ | plan.md 檔案路徑 |
| dry_run | | 只解析不執行（預覽模式） |
| resume | | 從 checkpoint 恢復（預設 true） |
| milestone | | 只跑指定 milestone（如 M1） |

### Plan 格式要求

```markdown
| # | 任務 | 產出檔案 | 估時 | AC |
|---|------|----------|------|-----|
| 1.1 | DB migration | `path/to/file.sql` | 20min | 表建立成功 |
```

---

## 輸出

- 程式碼產出（依 plan 指定的 output_file）
- `docs/reports/{plan_name}-acceptance.md`（驗收報告）
- `data/{plan_name}-progress.json`（checkpoint）

---

## 核心能力

### 1. Plan 解析

- frontmatter 提取（title, related_spec, related_design）
- Markdown 任務表格解析
- 依賴推斷（同 milestone 內按序號前後）
- 角色推斷（從 output_file 路徑 + title 關鍵字）

### 2. DAG 排序

- Kahn's algorithm 拓撲排序
- 環形依賴偵測（拋出 CyclicDependencyError）

### 3. 角色切換執行

| 角色 | 推斷規則 | Agent 目錄 |
|------|----------|-----------|
| coder | 預設 | agents/coder-agent/ |
| ai-dev | 含 design/prompt/llm | agents/ai-dev-agent/ |
| qa | 含 test/測試 | agents/qa-agent/ |

切換時：
- `cwd` 切到 agent 目錄
- 載入 SOUL.md 作為 context
- kiro-cli 為主力，Gemini API 為 fallback

### 4. AC 驗收（4 種方式）

| AC 關鍵字 | 驗證方式 |
|-----------|----------|
| 檔案/建立/存在 | `file_exists` |
| import/載入 | `python3 -c "import ..."` |
| 測試/test/pass | `pytest {file}` |
| 其他 | output 內容分析 |

### 5. 重試

- 首次失敗 → 注入 error context → 第 2 次
- 再失敗 → 更詳細 prompt → 第 3 次
- 最終失敗 → 標記 FAILED，繼續非依賴任務

### 6. Checkpoint

- `data/{plan}-progress.json`
- 中斷後恢復，跳過已通過任務
- 依賴失敗的任務自動 skip

---

## 使用範例

### TG 指令

```
/execute docs/plans/my-feature-plan.md
/execute docs/plans/my-feature-plan.md --dry-run
/execute docs/plans/my-feature-plan.md --milestone M1
```

### Skill 呼叫

```python
result = await registry.invoke("spec_executor", {
    "plan_path": "docs/plans/my-feature-plan.md",
    "dry_run": False,
    "resume": True,
})
# result.data = {"report_path": "...", "total": 21, "passed": 19, "pass_rate": 90.5}
```

---

## 驗收報告格式

```markdown
# 驗收報告

## 摘要
| 指標 | 值 |
|------|-----|
| 總任務 | 21 |
| 通過 | 19 |
| 失敗 | 2 |
| 通過率 | 90.5% |

## 任務結果
| # | 任務 | 角色 | 狀態 | AC 驗證 | 耗時 |
|---|------|------|------|---------|------|
| 1.1 | DB migration | coder | ✅ pass | 表建立 ✓ | 15s |

## 未通過清單
### 2.3 layer2_tfidf
- AC：語意相近可搜到
- 失敗原因：sklearn 未安裝
```

---

## 注意事項

- 單任務 timeout 120 秒
- 全 plan timeout 30 分鐘
- LLM 呼叫成本計入 cost_tracker
- 只能寫入 plan 指定的 output_file 路徑
- 需要 kiro-cli 在 PATH（否則走 Gemini fallback）

---

## 🔄 Loop Engineering — 自動迴圈

ark-spec-executor 是四段工作流鏈的執行引擎，支援自動迴圈修復：

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│   ark-grill-me → ark-superpowers → ark-spec-executor    │
│        ↑                                    │           │
│        │              ark-code-spec-validator ←┘         │
│        │                     │                          │
│        │         score < 70  │  score ≥ 90             │
│        │              ↓      │      ↓                   │
│        └──── 重新拷問 ←┘    ✅ Ship                      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 自動觸發規則

| 上游 Skill | 產出 | 自動觸發 ark-spec-executor？ |
|-----------|------|-------------------------------|
| ark-superpowers | plan.md | ✅ 詢問使用者是否執行 |
| ark-grill-me | 決策摘要 | ❌ 先走 superpowers |

### 下游迴圈規則

| 驗收結果 | 動作 |
|----------|------|
| pass_rate ≥ 90% | ✅ 自動觸發 `ark-code-spec-validator` 做最終 drift check |
| pass_rate 70-89% | ⚠️ 產出修復任務清單 → 自動重跑失敗項 |
| pass_rate < 70% | 🛑 停止，建議使用者用 `ark-grill-me` 重新釐清需求 |

### 搭配使用提示

- 「幫我寫 spec 然後跑完」→ superpowers + spec-executor
- 「跑完後驗證一下」→ spec-executor + code-spec-validator
- 「全自動從頭跑」→ grill-me + superpowers + spec-executor + validator

