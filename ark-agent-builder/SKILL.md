---
name: ark-agent-builder
description: |
  [DEPRECATED — 已由 ark-agent-bot-builder 取代]
  2026-09-08 改名重寫 v3.0（原版自己搭架構；新版是 ark_bot_agent 套件的消費端骨架產生器）。
  保留本頁只為讓舊觸發詞（建立 AI Bot、產出 Bot workspace、快速建 Agent Bot、chatbot、ai-bot-builder）仍能導向遷移說明 ——
  **不要使用本 skill，改用 `ark-agent-bot-builder`。**
metadata:
  schema_version: "1"
  status: deprecated
  author: paddyyang
  category: scaffolder
  replaced_by: ark-agent-bot-builder
  deprecated_at: 2026-09-08
---

# ark-agent-builder（已停用）

> ⚠️ **DEPRECATED — 已由 `ark-agent-bot-builder` 取代**（2026-09-08）

## 為什麼

2026-09-08 改名重寫 v3.0（原版自己搭架構；新版是 ark_bot_agent 套件的消費端骨架產生器）。

## 改用什麼

**分流**：單 bot → `ark-agent-bot-builder`；多 agent 團隊 daemon → `ark-agent-team-builder`；非套件的獨立 FastAPI 應用 → `ark-webapp-generator`。

## 舊觸發詞

建立 AI Bot、產出 Bot workspace、快速建 Agent Bot、chatbot、ai-bot-builder

說出以上任一關鍵字時，**直接改用 `ark-agent-bot-builder`**，不要沿用本 skill 的內容
（它的產出方式已經過時）。

## 取回舊內容

```bash
git log --oneline --diff-filter=D -- ark-agent-builder/SKILL.md   # 找到刪除它的 commit
git show <commit>~1:ark-agent-builder/SKILL.md
```
