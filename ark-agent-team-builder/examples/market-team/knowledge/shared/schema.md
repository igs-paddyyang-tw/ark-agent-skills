# shared 知識庫 Schema（v3.0）

> **本櫃定位**：排程蒸餾 + 使用者放入 + 跨 agent 共用的市場情報知識。
> 對照 `knowledge/market-team-agent/`（本團隊自己分析產出的情報）。
> 🔴 記憶歸記憶、知識歸知識：本櫃只放知識；記憶歸檔在 `memory/archive/`。

## Frontmatter 欄位
title / type / tags / created / updated（必要）；status / sources / related / aliases / trust（建議）

## 合法 type
concept / entity / source / synthesis / comparison / overview / system

## 目錄結構
```
knowledge/shared/
├── raw/     → 原始素材（給人查證，只增不改）
├── wiki/    → 結構化知識（給 AI 檢索，ingest 蒸餾產出）
├── .index/  → 搜尋索引（自動生成）
└── schema.md / index.md / log.md
```

## 操作規則
- raw/ 只讀；wiki/ 由 ingest 蒸餾產出（禁止手寫）
- 改 wiki 同步 index.md + log.md（append-only）
- **知識庫都經蒸餾**：raw（給人）→ ingest → wiki（給 AI）
