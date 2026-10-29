---
name: ark-cost-tracker
description: |
  [DEPRECATED — 已併入 ark-pipeline-recipes（讀 references/cost-tracker.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 API 呼叫成本追蹤 Skill，記錄 LLM API 的 token 使用量和費用。 支援 Gemini、Ollama 等多個 LLM 後端的成本計算。 使用此 Skill 當使用者提及成本追蹤、API 費用、token 使用量、 cost tracking、或任何需要監控 LLM 呼叫成本的場景。
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

# ark-cost-tracker（已併入 ark-pipeline-recipes）

本 skill 已併入 **`ark-pipeline-recipes`**，內容原樣搬到 `ark-pipeline-recipes/references/cost-tracker.md`。請改讀那一頁。

消費端若還沒有 `ark-pipeline-recipes`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-pipeline-recipes .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：內容移至 `ark-pipeline-recipes/references/cost-tracker.md`，本目錄只留轉址；角色對照表改指 ark-pipeline-recipes |
