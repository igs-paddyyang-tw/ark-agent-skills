---
name: ark-doc-coauthoring
description: |
  [DEPRECATED — 已併入 ark-superpowers（「工作模式 → coauthor（互動共筆）」；原文在 references/modes/coauthor.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：引導使用者透過結構化工作流共同撰寫文件。 使用此 Skill 當使用者想要撰寫文件、提案、技術規格、決策文件或類似結構化內容。 此工作流幫助使用者有效傳遞上下文、透過迭代精煉內容、並驗證文件對讀者有效。 當使用者提及撰寫文件、建立提案、草擬規格或類似文件任務時觸發。
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

# ark-doc-coauthoring（已併入 ark-superpowers）

本 skill 已併入 **`ark-superpowers`** 的「工作模式 → coauthor（互動共筆）」。原內容原樣保留在 `ark-superpowers/references/modes/coauthor.md`。

消費端若還沒有 `ark-superpowers`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-superpowers .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：併入 `ark-superpowers`，內容移至 `ark-superpowers/references/modes/coauthor.md`，本目錄只留轉址；角色對照表改指 ark-superpowers |
