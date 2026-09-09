---
name: ark-telegram-bot
description: |
  [DEPRECATED — 已由 ark-webapp-generator 取代]
  2026-09-08 三合一（webapp-generator v2.0 併入 telegram-bot 與 scheduler-generator）。
  保留本頁只為讓舊觸發詞（Telegram Bot 開發、Bot 專案建置、Web App、Mini App、Menu 命令、InlineKeyboard、telegram adapter）仍能導向遷移說明 ——
  **不要使用本 skill，改用 `ark-webapp-generator`。**
metadata:
  schema_version: "1"
  status: deprecated
  author: paddyyang
  category: scaffolder
  replaced_by: ark-webapp-generator
  deprecated_at: 2026-09-08
---

# ark-telegram-bot（已停用）

> ⚠️ **DEPRECATED — 已由 `ark-webapp-generator` 取代**（2026-09-08）

## 為什麼

2026-09-08 三合一（webapp-generator v2.0 併入 telegram-bot 與 scheduler-generator）。

## 改用什麼

**分流**：① 要「web + 排程 + TG」的獨立應用 → `ark-webapp-generator`；② 只要送訊息／推播／告警 → `ark-telegram-sender`；③ 要 ark_bot_agent 套件的消費端骨架 → `ark-agent-bot-builder`。

## 舊觸發詞

Telegram Bot 開發、Bot 專案建置、Web App、Mini App、Menu 命令、InlineKeyboard、telegram adapter

說出以上任一關鍵字時，**直接改用 `ark-webapp-generator`**，不要沿用本 skill 的內容
（它的產出方式已經過時）。

## 取回舊內容

```bash
git log --oneline --diff-filter=D -- ark-telegram-bot/SKILL.md   # 找到刪除它的 commit
git show <commit>~1:ark-telegram-bot/SKILL.md
```
