---
name: ark-security-audit
description: |
  [DEPRECATED — 已併入 ark-quality-gates（security 關（內建規則＋bandit／pip-audit），可直接執行；原產碼食譜在 references/recipes/security-audit.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 security_audit.py 安全性掃描 Skill，對專案進行程式碼安全性檢查與弱點偵測。 檢查項目包含硬編碼密碼、SQL injection、eval 使用、依賴套件漏洞、路徑穿越等。 輸出 issues 清單、嚴重度摘要與風險分數。 使用此 Skill 當使用者提及安全性掃描、security audit、弱點偵測、 vulnerability scan、程式碼安全、依賴檢查、 或任何需要檢查專案安全性的場景。
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

# ark-security-audit（已併入 ark-quality-gates）

本 skill 原本只是「教你寫一個檢查模組」的產碼食譜。現在改由 **`ark-quality-gates`** 直接執行：

```bash
python <ark-agent-skills>/ark-quality-gates/scripts/quality_gates.py --path . --json quality.json --md quality.md
```

原食譜原樣保留在 `ark-quality-gates/references/recipes/security-audit.md`（要把檢查做成 bot 插件時才需要）。

消費端若還沒有 `ark-quality-gates`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-quality-gates .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：併入 `ark-quality-gates`（可執行的 security 關（內建規則＋bandit／pip-audit）），原食譜移至 `ark-quality-gates/references/recipes/security-audit.md`，本目錄只留轉址 |
