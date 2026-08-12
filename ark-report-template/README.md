# ⚠️ DEPRECATED — ark-report-template

> **Deprecated since**: 2026-08-12
> **Remove after**: 2027-02-12
> **Migrated to**: `ark-md-report`（Content 軌）+ `ark-html-report`（View 軌）

本 skill 已被雙軌系統取代：
- 結構化報告 MD → `ark-md-report`
- HTML 渲染 → `ark-html-report`

## 為什麼移除

ark-md-report 提供更嚴謹的機制：
- frontmatter 契約（verdict/findings/severity/confidence）
- chunk 自足章節（RAG 友好）
- 受控詞彙（tags 白名單）
- 穩定 Finding ID（跨報告引用不斷鏈）
