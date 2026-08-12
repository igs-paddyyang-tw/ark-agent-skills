# schema.md 模板（v3.1）

複製本模板到 `knowledge/{project}/schema.md`。白名單與提案佇列的區塊標題為機器解析錨點，勿改字。

```markdown
# {Project} Wiki Schema v3.1

## 頁面類型（type）
concept | entity | source | synthesis | comparison | overview | system

## 成熟度（status）
seedling | developing | mature
（trust: llm-distilled 且 approved: false 者強制 seedling）

## 信任層（trust）
- deterministic：腳本搬運的事實，自動發布
- llm-distilled：LLM 改寫/摘要/蒸餾，需人工 approve

## tags 白名單

- agent-architecture
- skill-review
（首次建表：`wiki_taxonomy migrate --wiki_dir ...` 從存量統計候選，人工確認後入表）
（命名規則：kebab-case、小寫、名詞單數優先；同義詞入頁面 aliases 不另開 tag）

## tags 提案佇列

| tag | 提案原因 | 提案者 | 日期 |
|---|---|---|---|
（`wiki_taxonomy propose` 自動追加；人工 `approve` 後移入白名單並自此表移除）
```

## 對接說明

- `wiki_taxonomy` 與 `wiki_lint --schema` 讀「## tags 白名單」區塊
- 報告三件套的 `report_lint --wiki-schema` 讀同一區塊 —— 全系統單一詞彙來源
- 白名單 tag 數 >100 時建議修剪（合併近義、退役停用 tag 移入頁面 aliases）
