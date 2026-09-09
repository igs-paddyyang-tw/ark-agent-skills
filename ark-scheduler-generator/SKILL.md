---
name: ark-scheduler-generator
description: |
  [DEPRECATED — 已由 ark-webapp-generator 取代]
  2026-09-08 三合一（排程引擎已是 webapp-generator v2.0 的可選層）。
  保留本頁只為讓舊觸發詞（加入排程、gen workflow、工作流引擎、排程引擎、每日報表自動化、APScheduler）仍能導向遷移說明 ——
  **不要使用本 skill，改用 `ark-webapp-generator`。**
metadata:
  schema_version: "1"
  status: deprecated
  author: paddyyang
  category: scaffolder
  replaced_by: ark-webapp-generator
  deprecated_at: 2026-09-08
---

# ark-scheduler-generator（已停用）

> ⚠️ **DEPRECATED — 已由 `ark-webapp-generator` 取代**（2026-09-08）

## 為什麼

2026-09-08 三合一（排程引擎已是 webapp-generator v2.0 的可選層）。

## 改用什麼

**分流**：獨立應用要排程 → `ark-webapp-generator`；ark_team_agent 消費端的排程走 `scheduler.yaml`，由套件內建，不需要 scaffold。

## 舊觸發詞

加入排程、gen workflow、工作流引擎、排程引擎、每日報表自動化、APScheduler

說出以上任一關鍵字時，**直接改用 `ark-webapp-generator`**，不要沿用本 skill 的內容
（它的產出方式已經過時）。

## 取回舊內容

```bash
git log --oneline --diff-filter=D -- ark-scheduler-generator/SKILL.md   # 找到刪除它的 commit
git show <commit>~1:ark-scheduler-generator/SKILL.md
```
