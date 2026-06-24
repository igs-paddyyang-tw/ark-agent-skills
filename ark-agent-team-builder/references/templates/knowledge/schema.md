---
title: "Team Knowledge Schema"
type: system
created: {{TODAY}}
updated: {{TODAY}}
---

# Wiki Schema v3.0

> 團隊共享知識庫的格式規範。所有 wiki 頁面必須遵守。

## 目錄結構

```
knowledge/shared/
├── raw/          → 唯讀原始資料（LLM 不得修改）
├── wiki/         → 結構化知識頁面
├── schema.md     → 本文件（規則定義）
├── index.md      → 索引目錄（每次 wiki 變更必須同步）
└── log.md        → 操作日誌（append-only，禁止刪除）
```

## Frontmatter 必要欄位

所有 wiki/ 下的 .md 檔案必須有：

```yaml
---
title: "頁面標題"
type: concept | entity | source | synthesis | overview
tags: [tag1, tag2]
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: seedling | developing | mature
---
```

### type 定義

| type | 用途 | 範例 |
|------|------|------|
| concept | 概念解釋 | 系統架構、設計原則 |
| entity | 實體描述 | Agent 角色、工具規格 |
| source | 外部來源摘要 | 文章摘要、API 文件 |
| synthesis | 綜合分析 | 比較報告、決策分析 |
| overview | 總覽索引 | 首頁、分類頁 |

### status 定義

| status | 含義 | 規則 |
|--------|------|------|
| seedling | 初稿、佔位 | 可大幅修改 |
| developing | 有實質內容但未完善 | 可補充、修正 |
| mature | 穩定版 | 僅修 typo 或更新日期 |

## 操作規則

| 規則 | 說明 |
|------|------|
| raw/ 唯讀 | LLM 只讀不改，人工或 ingest 工具處理 |
| wiki/ 可寫 | 新增/修改後必須更新 index.md + log.md |
| log append-only | 禁止刪除或修改舊記錄 |
| 雙向連結 | 頁面間用 `[[page_name]]` 互連 |
| 一頁一主題 | 不要把多個主題混在同一頁 |

## 連結語法

```markdown
相關：[[team-architecture]] | [[mcp-tools-reference]]
```

## index.md 格式

```markdown
# 知識庫索引

| 頁面 | 類型 | 狀態 | 標籤 |
|------|------|------|------|
| [[team-architecture]] | concept | mature | architecture, system |
| [[mcp-tools-reference]] | concept | mature | mcp, tools |
```

## log.md 格式

```markdown
# 操作日誌

| 日期 | 操作 | 頁面 | 操作者 |
|------|------|------|--------|
| 2026-06-24 | 建立 | team-architecture | system |
| 2026-06-24 | 建立 | mcp-tools-reference | system |
```
