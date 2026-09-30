---
related_spec: docs/specs/demo-spec.md
---
# demo-plan-badrole — plan_lint 回歸用非法角色範例（應 P0 拒跑 exit 2）

角色 `dev`/`backend` 不在枚舉 coder|ai-dev|qa|human。

| # | 任務 | 角色 | 產出檔案 | 估時 | AC-ID | AC |
|---|------|------|----------|------|-------|-----|
| 1.1 | 建模組 | dev | src/x.py | 1h | AC-001 | verify: import；可 import |
| 1.2 | 建 API | backend | src/api.py | 1h | AC-002 | verify: file；檔案建立 |
