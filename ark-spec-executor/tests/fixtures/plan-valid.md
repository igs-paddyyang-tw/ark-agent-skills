---
related_spec: docs/specs/demo-spec.md
related_design: docs/designs/demo-design.md
---
# demo-plan — plan_lint 回歸用合格範例（全綠：無 P0/P1/P2）

契約：7 欄任務表、AC-ID 全檔唯一、角色合法、AC 帶 verify 提示或可自動推斷。

| # | 任務 | 角色 | 產出檔案 | 估時 | AC-ID | AC |
|---|------|------|----------|------|-------|-----|
| 1.1 | 建立核心模組 | coder | src/core.py | 2h | AC-001 | verify: import；模組可被 import 且無語法錯 |
| 1.2 | 補單元測試 | qa | tests/test_core.py | 1h | AC-002 | verify: pytest；測試全數 pass |
| 2.1 | 撰寫 CLI 入口 [← 1.1] | coder | src/cli.py | 1h | AC-003 | verify: file；cli.py 檔案建立完成 |
