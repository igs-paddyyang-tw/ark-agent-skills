---
name: ark-code-review
description: |
  [DEPRECATED — 已併入 ark-quality-gates（lint 關（ruff＋語法），可直接執行；原產碼食譜在 references/recipes/code-review.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出程式碼審查 Skill，支援 Python/TypeScript 程式碼品質檢查、 風格一致性驗證、安全性掃描、PR 審查報告產生。 使用此 Skill 當使用者提及程式碼審查、code review、PR 審查、 程式碼品質、lint、或任何需要檢查程式碼品質的場景。
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

# ark-code-review（已併入 ark-quality-gates）

本 skill 原本只是「教你寫一個檢查模組」的產碼食譜。現在改由 **`ark-quality-gates`** 直接執行：

```bash
python <ark-agent-skills>/ark-quality-gates/scripts/quality_gates.py --path . --json quality.json --md quality.md
```

原食譜原樣保留在 `ark-quality-gates/references/recipes/code-review.md`（要把檢查做成 bot 插件時才需要）。

消費端若還沒有 `ark-quality-gates`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-quality-gates .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：併入 `ark-quality-gates`（可執行的 lint 關（ruff＋語法）），原食譜移至 `ark-quality-gates/references/recipes/code-review.md`，本目錄只留轉址 |
