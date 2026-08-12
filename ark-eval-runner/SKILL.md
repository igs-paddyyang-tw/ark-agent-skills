---
name: ark-eval-runner
description: "當使用者需要對 LLM 輸出進行回歸評測時使用此技能。觸發條件包括：提及「LLM 評測」「回歸測試」「prompt 評分」「模型品質」，或要求用 prompt 集 + 斷言 + 多次取樣計算通過率。適用於 prompt 變更後的品質驗證、模型切換前後的效果對比。不適用於 pytest 單元測試——該場景請用 ark-test-runner。"
metadata:
  schema_version: 1
  status: active
  author: paddyyang
  category: pipeline
  outputs:
    - format: md
      audience: both
---

# ark-eval-runner

> LLM 輸出回歸評測。prompt 集 + 斷言 + 多次取樣通過率。

## 觸發條件

- 使用者提及「LLM 評測」「回歸測試」「prompt 評分」「模型品質」
- prompt 變更後需要驗證輸出品質
- 模型切換前後效果對比
- 要求計算多次取樣通過率

## Negative Trigger

- pytest 單元測試 → 請用 `ark-test-runner`
- 程式碼品質檢查 → 不在本 skill 範圍

## 工作流程

1. 載入 eval 定義檔（prompt 集 + 預期斷言）
2. 對每個 prompt 執行 N 次取樣（可配置）
3. 對每次輸出執行斷言檢查（exact / contains / regex / semantic）
4. 計算通過率並標記回歸項目
5. 產出評測報告（含逐項結果 + 總體通過率）

## 產出格式

- 評測摘要（總通過率 / 回歸數 / 改善數）
- 逐項結果表格（prompt_id / pass_rate / failures）
- 回歸警告與建議
