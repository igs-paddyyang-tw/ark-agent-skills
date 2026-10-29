---
name: ark-quality-gates
description: |
  一支指令跑三道品質關並產出報告：tests（pytest＋覆蓋率）、lint（語法檢查＋ruff）、
  security（內建規則：硬編碼密鑰、eval／exec、shell=True、SQL 字串拼接、不安全反序列化、關閉 TLS 驗證；
  有裝就加跑 bandit、pip-audit）。缺工具會明說跳過並給安裝指令，不假裝通過；有關失敗即 exit 1。
  使用此 Skill 當使用者提及跑測試、test runner、pytest、覆蓋率、coverage、line coverage、pytest --cov、
  程式碼審查、code review、PR 審查、lint、程式碼品質、安全性掃描、security audit、弱點偵測、
  依賴漏洞、品質守門、quality gate、上線前檢查。
  不適用於：code 與 spec 是否一致請用 ark-code-spec-validator；提詞與 SKILL.md 檢查請用 ark-prompt-spec-validator；
  開發環境跑不起來請用 ark-env-doctor。
metadata:
  version: "1.0.0"
  schema_version: "1.2"
  status: active
  updated: 2026-10-29
  category: process
  form: executor
  domain: general
  replaces: [ark-code-review, ark-security-audit, ark-test-runner]
  outputs:
    - format: data
      audience: ai
    - format: md
      audience: human
  author: paddyyang
---

# ark-quality-gates

一支指令跑 **tests／lint／security** 三道關，結果寫成 JSON（給 AI）與 Markdown（給人）。
規格：kiro-cli `docs/specs/ark-quality-gates-spec.md`。

## 用法

```bash
# 三關全跑（在專案根目錄）
python scripts/quality_gates.py --path . --json quality.json --md quality.md

# 用專案自己的 venv 跑測試，覆蓋率低於 80% 算失敗
python scripts/quality_gates.py --path . --python .venv/bin/python --fail-under 80

# 只跑部分關；CI 用 --strict（缺工具 = 失敗，不放行）
python scripts/quality_gates.py --path src --only lint,security --strict
```

Exit：`0` 全過（skip 不算失敗，除非 `--strict`）· `1` 有關失敗 · `2` 參數錯誤。

## 三道關

| 關 | 一定會跑（只用標準庫） | 有裝才加強 | 失敗條件 |
|---|---|---|---|
| tests | `<python> -m pytest -q` | `pytest-cov` → 行覆蓋率 | 有 failed／error；`--fail-under` 未達 |
| lint | 每個 `.py` 語法編譯檢查 | `ruff check` | 語法錯誤；ruff 違規 |
| security | 內建規則（AST 判函式呼叫，`model.eval()`、`ast.literal_eval` 不會誤報） | `bandit`、`pip-audit`（讀 requirements.txt） | 任何 high |

- **skip 一定附原因與安裝指令**：pytest 沒裝、0 個測試、沒有 `.py` 檔、外部工具不存在
- 刻意的用法（例：執行使用者設定的指令需要 `shell=True`）在該行加 `# nosec`；略過筆數會出現在摘要，不靜默
- 預設排除 `.git .venv venv node_modules __pycache__ build dist .tox` 與各種 cache 目錄

## 輸出

```json
{"verdict": "fail", "path": "/repo", "strict": false,
 "gates": [{"name": "security", "status": "fail", "summary": "6 個檔；high 1、其他 0（只跑內建規則）",
            "findings": [{"file": "svc.py", "line": 3, "rule": "shell-true", "severity": "high",
                          "message": "subprocess shell=True 有指令注入風險；改傳 list 參數"}],
            "hint": "未安裝 bandit、pip-audit（只跑內建規則）：pip install bandit pip-audit", "suppressed": 0}]}
```

Markdown 報告：總判定 → 三關狀態表 → 每關失敗明細（每關最多 50 筆，完整在 JSON）。

## 在流程裡的位置

```
ark-superpowers（plan）→ ark-spec-executor（實作）→ ark-quality-gates（品質）＋ ark-code-spec-validator（對規格）→ 交付
```

- 交付前兩道驗證互補：本 skill 驗「程式本身健不健康」，code-spec-validator 驗「做的是不是規格要的」
- 排程／CI 直接看 exit code；要給人看就把 `--md` 交給 ark-html-report 渲染

## 原產碼食譜

三個舊 skill 的原文保留在 `references/recipes/`，**只在要把檢查做成 bot 插件（BaseSkill）時讀**：
[`code-review.md`](references/recipes/code-review.md)、[`security-audit.md`](references/recipes/security-audit.md)、
[`test-runner.md`](references/recipes/test-runner.md)。

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 1.0.0 | 2026-10-29 | 由 ark-code-review、ark-security-audit、ark-test-runner 合併：從「教你寫檢查模組」改為可直接執行的三道關（`scripts/quality_gates.py`＋11 項測試）；原食譜原樣保留在 `references/recipes/` |
