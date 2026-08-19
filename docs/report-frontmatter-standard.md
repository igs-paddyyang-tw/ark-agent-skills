# 報告類 Markdown Frontmatter 標準

> 所有報告類 skill 產出的 `.md` 檔案必須遵守此 frontmatter 標準。

## Schema

```yaml
---
type: report
title: string
date: YYYY-MM-DD
tags: []
source_skill: ark-xxx
audience: human | ai | both
render: html | none
---
```

## 欄位定義

| 欄位 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `type` | string | ✅ | 固定為 `report` |
| `title` | string | ✅ | 報告標題，應有資訊量 |
| `date` | string | ✅ | 產出日期，格式 `YYYY-MM-DD` |
| `tags` | list | ✅ | 分類標籤，用於搜尋與過濾 |
| `source_skill` | string | ✅ | 產出此報告的 skill 名稱（如 `ark-report-template`、`ark-news-daily`） |
| `audience` | enum | ✅ | 目標受眾：`human`（人類閱讀）/ `ai`（機器消費）/ `both`（雙用） |
| `render` | enum | ✅ | 是否需要渲染為 HTML：`html`（由 ark-html-report 渲染）/ `none`（純 MD 即可） |

## 範例

```yaml
---
type: report
title: "2026-08-11 科技日報"
date: 2026-08-11
tags: [daily, news, tech]
source_skill: ark-news-daily
audience: human
render: html
---
```

```yaml
---
type: report
title: "Q3 營收分析報告"
date: 2026-08-10
tags: [quarterly, revenue, analysis]
source_skill: ark-report-template
audience: both
render: html
---
```

## 適用 Skill

以下 skill 產出報告類 MD 時必須遵守此標準：

- `ark-report-template` — 標準化報表模板引擎
- `ark-news-daily` — 科技日報
- `ark-html-report` — HTML 報告（當以 MD 為中間產物時）
- 任何其他產出 `type: report` 的 skill

## 與 Wiki 的關係

報告類 MD 若需歸檔到 Wiki，由 `ark-wiki-engine` 的 ingest 流程處理。
Wiki ingest 時會檢查此 frontmatter 標準，並將 `type: report` 的頁面歸入對應分類。
