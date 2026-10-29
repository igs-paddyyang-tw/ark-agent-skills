---
name: ark-llm-tools
description: |
  [DEPRECATED — 已併入 ark-pipeline-recipes（讀 references/llm-tools.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 LLM 通用工具 Skills（summarize、analyze、qa、intent_parse）， 搭配 GeminiAdapter 或 LLMAdapter 進行文字摘要、資料分析、問答、意圖解析。 使用此 Skill 當使用者提及 LLM 摘要、AI 分析、智能問答、意圖解析、 或任何需要 LLM 文字處理能力的場景。 專責 LLM 工具函式與 provider 抽象。
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

# ark-llm-tools（已併入 ark-pipeline-recipes）

本 skill 已併入 **`ark-pipeline-recipes`**，內容原樣搬到 `ark-pipeline-recipes/references/llm-tools.md`。請改讀那一頁。

消費端若還沒有 `ark-pipeline-recipes`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：內容移至 `ark-pipeline-recipes/references/llm-tools.md`，本目錄只留轉址；角色對照表改指 ark-pipeline-recipes |
