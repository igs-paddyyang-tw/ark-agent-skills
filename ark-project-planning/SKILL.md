---
name: ark-project-planning
description: |
  [DEPRECATED — 已併入 ark-superpowers（「工作模式 → plan（流程與派工）」；原文在 references/modes/plan-workflow.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：標準化專案計畫流程。收到新功能需求時使用：釐清需求、撰寫規格文件、拆解任務、 分派給 Agent、追蹤進度、驗收交付。 Use when receiving new feature requests, project planning, task delegation to agents. 觸發條件：新功能、新需求、派工、拆任務、專案規劃、project plan。
metadata:
  version: "3.0.0"
  schema_version: "1.2"
  status: deprecated
  updated: 2026-10-29
  category: process
  form: instruction
  domain: general
  author: paddyyang
---

# ark-project-planning（已併入 ark-superpowers）

本 skill 已併入 **`ark-superpowers`** 的「工作模式 → plan（流程與派工）」。原內容原樣保留在 `ark-superpowers/references/modes/plan-workflow.md`。

消費端若還沒有 `ark-superpowers`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-superpowers .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 3.0.0 | 2026-10-29 | **Breaking**：併入 `ark-superpowers`，內容移至 `ark-superpowers/references/modes/plan-workflow.md`，本目錄只留轉址；角色對照表改指 ark-superpowers |
