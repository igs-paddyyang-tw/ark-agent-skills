---
name: ark-release-notes
description: "當使用者需要從 git log 產出結構化 changelog 或版本說明時使用此技能。觸發條件包括：提及「changelog」「release notes」「版本說明」「變更日誌」，或要求整理近期 commit 為可讀的變更摘要。產出可作為日報素材或 GitHub Release 說明。不適用於完整 spec/design 文件撰寫——該場景請用 ark-superpowers。"
metadata:
  author: paddyyang
  category: document
  outputs:
    - format: md
      audience: both
---

# ark-release-notes

> git log → 結構化 changelog MD → 日報素材。

## 觸發條件

- 使用者提及「changelog」「release notes」「版本說明」「變更日誌」
- 要求整理近期 commit 為可讀摘要
- 版本發佈前需要變更說明
- 日報/週報需要開發進度素材

## Negative Trigger

- 完整 spec / design 文件 → 請用 `ark-superpowers`
- 專案規劃文件 → 請用 `ark-project-planning`

## 工作流程

1. 讀取 git log（指定範圍：tag..HEAD / 日期區間 / commit 數）
2. 分類 commit（feat / fix / refactor / docs / chore / breaking）
3. 群組化相關 commit（同模組 / 同 issue）
4. 產出結構化 changelog（Conventional Commits 格式）
5. 附加統計摘要（檔案數 / 行數 / 貢獻者）

## 產出格式

- 版本標題 + 日期
- 分類變更列表（feat / fix / breaking / other）
- 統計摘要
- 可選：highlight（重要變更一句話摘要）
