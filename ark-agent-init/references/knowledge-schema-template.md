# Knowledge Schema 模板（v3.1 — 含自我成長 + 多層規則）

> 此模板由 `build_kiro.py` 產出到每個 Agent 的 `knowledge/schema.md`。

---

## 知識庫三層架構

```
專案根目錄/
├── knowledge/
│   └── shared/                   ← 🔴 共用知識庫（Wiki 引擎與 start.py 實際讀這層）
│       ├── raw/                  ← 排程 LLM 分析 Agent 知識後放入 / 人類放入
│       ├── wiki/                 ← 共用精煉知識（BM25 索引 .index/ 建在此）
│       ├── schema.md
│       ├── index.md
│       └── log.md
│
└── agents/{name}-agent/
    └── knowledge/                ← Agent 私有知識庫（Agent 自己維護）
        ├── raw/
        ├── wiki/                 ← 私有精煉知識（各自的 .index/）
        ├── schema.md             ← 本模板
        ├── index.md
        └── log.md
```

> 🔴 **一定要有 `shared/` 這一層**（不是扁平的 `knowledge/wiki/`）。
> Wiki 引擎與 `start.py` 讀的是 `knowledge/shared/wiki/`。本機 MEMORY 記過**四次**
> 「少一層 shared」的靜默失效（索引讀不到、蒸餾搜不到，不拋例外不寫 log）。
> team.yaml 的 `knowledge_search_order` 列的櫃名（如 `[<self>, shared]`）
> 各對應 `knowledge/<櫃名>/`。

## 讀取優先順序

| 優先 | 來源 | 何時搜尋 |
|------|------|---------|
| 1️⃣ | 自己的 `knowledge/wiki/` | **預設**（所有查詢先搜自己） |
| 2️⃣ | `knowledge/shared/wiki/` | 自己的找不到 or 明確指定「共用知識」 |


## 寫入規則

| 場景 | 寫入位置 | 說明 |
|------|---------|------|
| Agent 完成任務學到東西 | **自己的** `knowledge/wiki/` | 私有，不影響他人 |
| Agent 解決了通用問題 | **自己的** `knowledge/wiki/` | 先存私有 |
| 排程整理（daily） | `knowledge/shared/raw/` | LLM 分析私有知識 → 提取通用部分 → 放入 shared/raw |
| IDE 手動寫入 | `knowledge/shared/raw/` | 人類放入 raw → LLM ingest → wiki |

## 共用知識同步機制

```
┌─────────────────┐      排程 daily-knowledge-digest
│ Agent A wiki/   │──┐
│ Agent B wiki/   │──┤──→ LLM 分析通用性 → shared/raw/ → ingest → shared/wiki/
│ Agent C wiki/   │──┘
└─────────────────┘
         ↑ 寫入                        ↓ 讀取（優先級 2）
    各 Agent 私有                   所有 Agent 可搜尋
```

## 自我成長規則

Agent 在以下時機必須更新**自己的**知識庫：

| 觸發時機 | 動作 | 寫入位置 |
|---------|------|---------|
| 完成任務後 | 萃取學到的技巧/模式 → 寫成 wiki 頁面 | wiki/{category}/ |
| 遇到問題並解決 | 記錄問題 + 解法 | wiki/troubleshooting/ |
| 收到 Spec/Design 文件 | 存入 raw/ 作為參考 | raw/ |
| 每日結束（排程觸發） | 更新 overview.md 反映能力成長 | wiki/overview.md |

## Frontmatter 規範

```yaml
---
title: "頁面標題"
type: concept | entity | source | synthesis | comparison | overview | system
tags: [tag1, tag2]              # 必須在 schema.md 的白名單內
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: seedling | developing | mature | evergreen
trust: deterministic | llm-distilled   # 必填
approved: true | false          # trust: llm-distilled 時必填
aliases: [別名1, 別名2]          # 選填但強烈建議
---
```

> 對齊 `ark-wiki-engine` v3.1（`references/page-schema.md` 為權威）。
> `wiki_lint.py` 對必填欄位（`title`/`type`/`created`/`updated`/`trust`）缺一即 error。
> 兩層信任：腳本搬運 = `deterministic`；LLM 改寫/摘要 = `llm-distilled`（需 `approved`）。

## 操作規則

| 規則 | 說明 |
|------|------|
| raw/ 唯讀 | LLM 只讀不改 |
| 修改後同步 | 改 wiki → 必須更新 index.md + log.md |
| log append-only | 禁止刪除舊記錄 |
| 雙向連結 | 使用 `[[page_name]]` 建構圖譜 |
| 矛盾標記 | `> ⚠️ 矛盾：...` 只標記不解決 |
| 不確定標記 | 用 `(?)` 標記 |

## 禁止事項

- ❌ 不可直接寫入根目錄 `knowledge/`（由排程 LLM + 人類管理）
- ❌ 不可刪除 log.md 舊記錄
- ❌ 不可修改 raw/ 中的檔案
- ❌ 不可在私有知識中存放敏感 Token/密碼
