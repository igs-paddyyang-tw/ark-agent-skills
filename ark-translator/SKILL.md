---
name: ark-translator
description: |
  [DEPRECATED — 已併入 ark-pipeline-recipes（讀 references/translator.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 translator.py 多語言翻譯 Skill，搭配 Gemini LLM 進行高品質翻譯， 支援繁體中文、簡體中文、英文、日文互譯。 保留 Markdown 格式與程式碼區塊不翻譯，支援批次翻譯。 使用此 Skill 當使用者提及翻譯、translate、多語言、i18n、 中翻英、英翻中、日翻中、或任何需要語言轉換的場景。
metadata:
  version: "2.0.0"
  schema_version: "1.2"
  status: deprecated
  updated: 2026-10-29
  category: pipeline
  form: instruction
  domain: general
  author: paddyyang
---

# ark-translator（已併入 ark-pipeline-recipes）

本 skill 已併入 **`ark-pipeline-recipes`**，內容原樣搬到 `ark-pipeline-recipes/references/translator.md`。請改讀那一頁。

消費端若還沒有 `ark-pipeline-recipes`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：內容移至 `ark-pipeline-recipes/references/translator.md`，本目錄只留轉址；角色對照表改指 ark-pipeline-recipes |
