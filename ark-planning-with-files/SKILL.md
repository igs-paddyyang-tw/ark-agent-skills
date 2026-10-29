---
name: ark-planning-with-files
description: |
  [DEPRECATED — 已併入 ark-superpowers（「工作模式 → files（長任務持久化）」；原文在 references/modes/files.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：持久化任務追蹤：複雜任務（3+ 步驟）自動建立 3-File Pattern（task_plan.md / findings.md / progress.md）， 防止 context 丟失、goal drift、錯誤重複。參考 Manus 模式。 使用此 Skill 當使用者提及 planning with files、任務追蹤、持久化計畫、 3-file pattern、防止遺忘、長任務管理、Manus workflow、 或任何需要跨 session 保持任務狀態的場景。
metadata:
  version: "2.0.0"
  schema_version: "1.2"
  status: deprecated
  updated: 2026-10-29
  category: process
  form: instruction
  domain: general
  author: paddyyang
---

# ark-planning-with-files（已併入 ark-superpowers）

本 skill 已併入 **`ark-superpowers`** 的「工作模式 → files（長任務持久化）」。原內容原樣保留在 `ark-superpowers/references/modes/files.md`。

消費端若還沒有 `ark-superpowers`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-superpowers .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：併入 `ark-superpowers`，內容移至 `ark-superpowers/references/modes/files.md`，本目錄只留轉址；角色對照表改指 ark-superpowers |
