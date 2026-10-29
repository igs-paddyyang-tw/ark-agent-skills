---
name: ark-test-runner
description: |
  [DEPRECATED — 已併入 ark-quality-gates（tests 關（pytest＋覆蓋率），可直接執行；原產碼食譜在 references/recipes/test-runner.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 test_runner.py 自動化測試執行 Skill，執行 pytest 測試並產生覆蓋率報告。 支援指定測試目錄、框架選擇、覆蓋率報告產生， 可串接 chart-generator 產生覆蓋率圖表。 使用此 Skill 當使用者提及測試執行、test runner、跑測試、 覆蓋率、coverage、pytest、自動化測試、 或任何需要執行測試並產生報告的場景。
metadata:
  version: "2.0.0"
  schema_version: "1.2"
  status: deprecated
  updated: 2026-10-29
  category: pipeline
  form: instruction
  domain: general
  author: paddyyang
---

# ark-test-runner（已併入 ark-quality-gates）

本 skill 原本只是「教你寫一個檢查模組」的產碼食譜。現在改由 **`ark-quality-gates`** 直接執行：

```bash
python <ark-agent-skills>/ark-quality-gates/scripts/quality_gates.py --path . --json quality.json --md quality.md
```

原食譜原樣保留在 `ark-quality-gates/references/recipes/test-runner.md`（要把檢查做成 bot 插件時才需要）。

消費端若還沒有 `ark-quality-gates`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-quality-gates .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：併入 `ark-quality-gates`（可執行的 tests 關（pytest＋覆蓋率）），原食譜移至 `ark-quality-gates/references/recipes/test-runner.md`，本目錄只留轉址 |
