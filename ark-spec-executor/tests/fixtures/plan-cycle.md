---
related_spec: docs/specs/demo-spec.md
---
# demo-plan-cycle — plan_lint 回歸用循環依賴範例（應 P0 拒跑 exit 2）

1.1 依賴 2.1、2.1 依賴 1.1 → 循環，Kahn 拓撲無法排序。

| # | 任務 | 角色 | 產出檔案 | 估時 | AC-ID | AC |
|---|------|------|----------|------|-------|-----|
| 1.1 | 模組 A [← 2.1] | coder | src/a.py | 1h | AC-001 | verify: import；A 可 import |
| 2.1 | 模組 B [← 1.1] | coder | src/b.py | 1h | AC-002 | verify: import；B 可 import |
