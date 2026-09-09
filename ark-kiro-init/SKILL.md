---
name: ark-kiro-init
description: |
  [DEPRECATED — 已由 ark-agent-init 取代]
  2026-09-07 更名（kiro-init 的名字綁死單一 CLI，而它產出的是多 CLI 共用的 workspace）。
  保留本頁只為讓舊觸發詞（建立 .kiro、產生 workspace、初始化 kiro 配置、kiro init、kiro-init、設定角色的 .kiro）仍能導向遷移說明 ——
  **不要使用本 skill，改用 `ark-agent-init`。**
metadata:
  schema_version: "1"
  status: deprecated
  author: paddyyang
  category: scaffolder
  replaced_by: ark-agent-init
  deprecated_at: 2026-09-08
---

# ark-kiro-init（已停用）

> ⚠️ **DEPRECATED — 已由 `ark-agent-init` 取代**（2026-09-08）

## 為什麼

2026-09-07 更名（kiro-init 的名字綁死單一 CLI，而它產出的是多 CLI 共用的 workspace）。

## 改用什麼

新名同時產出 CLAUDE.md / AGENTS.md 等多 CLI 入口，以 SSOT 連結同一份人格。

## 舊觸發詞

建立 .kiro、產生 workspace、初始化 kiro 配置、kiro init、kiro-init、設定角色的 .kiro

說出以上任一關鍵字時，**直接改用 `ark-agent-init`**，不要沿用本 skill 的內容
（它的產出方式已經過時）。

## 取回舊內容

```bash
git log --oneline --diff-filter=D -- ark-kiro-init/SKILL.md   # 找到刪除它的 commit
git show <commit>~1:ark-kiro-init/SKILL.md
```
