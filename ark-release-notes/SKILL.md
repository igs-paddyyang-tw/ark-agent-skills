---
name: ark-release-notes
description: "當使用者需要從 git log 產出結構化 changelog 或版本說明時使用此技能。觸發條件包括：提及「changelog」「release notes」「版本說明」「變更日誌」，或要求整理近期 commit 為可讀的變更摘要。產出可作為日報素材或 GitHub Release 說明。不適用於完整 spec/design 文件撰寫——該場景請用 ark-superpowers。"
metadata:
  schema_version: 1
  status: active
  updated: 2026-08-19
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

> 🔴 **先跑腳本產分類骨架（零 LLM、deterministic），LLM 只補 highlight 摘要段。**

1. 跑 `scripts/changelog_gen.py` 產出規則式分類骨架：
   ```bash
   python scripts/changelog_gen.py --last 20              # 最近 N 筆
   python scripts/changelog_gen.py --range v1.0.0..HEAD   # tag 範圍
   python scripts/changelog_gen.py --since 2026-09-01     # 日期起
   python scripts/changelog_gen.py --last 20 --output CHANGELOG.md  # 寫檔
   ```
   腳本自動：規則式解析 Conventional Commits（feat/fix/refactor/docs/chore/
   test/perf/build/ci/style，非規範落 other，`!`/`BREAKING CHANGE` 歸 breaking）、
   分類分組、附統計（commit 數/檔案數/行數/貢獻者）。
2. **LLM 只補這一步**：讀腳本產出的骨架，替重要變更寫一句話 highlight 摘要
   （放在檔首「## ⭐ Highlights」段）。不重做分類 —— 分類是腳本的職責。
3. 定稿：可作為日報素材或 GitHub Release 說明。

## 產出格式

- 版本標題 + 日期
- 分類變更列表（breaking / feat / fix / … / other）← 腳本產
- 統計摘要（commit/檔案/行數/貢獻者）← 腳本產
- ⭐ Highlights（重要變更一句話摘要）← LLM 補
