---
name: ark-uml-generator
description: |
  [DEPRECATED — 已併入 ark-superpowers（設計階段「設計圖（Mermaid）」；原文在 references/uml-diagrams.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：產出 Mermaid 格式的 UML 圖表，用於系統設計文件。 支援序列圖、類別圖、ERD、流程圖、元件圖。 使用此 Skill 當使用者提及 UML、序列圖、類別圖、ERD、流程圖、 架構圖、Mermaid、畫圖、系統互動圖、資料模型圖。
metadata:
  version: "2.0.0"
  schema_version: "1.2"
  status: deprecated
  updated: 2026-10-29
  category: document
  form: instruction
  domain: general
  author: paddyyang
---

# ark-uml-generator（已併入 ark-superpowers）

本 skill 已併入 **`ark-superpowers`**：設計階段「設計圖（Mermaid）」。原內容原樣保留在 `ark-superpowers/references/uml-diagrams.md`。

消費端若還沒有 `ark-superpowers`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-superpowers .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：併入 `ark-superpowers`，內容移至 `ark-superpowers/references/uml-diagrams.md`，本目錄只留轉址；角色對照表改指 ark-superpowers |
