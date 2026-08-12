---
name: ark-md-report
description: |
  產出「給 AI 看」的結構化分析報告 Markdown（Content 軌），與 ark-html-report（View 軌）成對。
  適用：skill/code review 報告、競品分析、事故分析、需求決策摘要（ark-grill-me 產出）、數據分析結論。
  報告含機器可解析的 frontmatter 契約（verdict/findings/severity/confidence）、穩定 Finding ID、
  chunk 自足章節，可直接被 ark-wiki-engine ingest 與日報 CollectorRunner 消費。
  使用此 skill 當使用者要求「產出分析報告」「review 報告」「給 AI 看的報告」「決策摘要文件」
  「報告要能入 wiki」「雙軌報告」，或任何分析結論需要被下游 agent/wiki/日報消費的場景。
metadata:
  author: paddyyang
  category: presentation-content
  outputs:
    - { format: md, audience: ai }
    - { format: html, audience: human, via: ark-html-report }
  depends_on: [ark-html-report]
---

# ark-md-report

產出 AI 可讀的分析報告 Markdown。核心原則：

- **MD 是 source of truth**（Content 軌），HTML 是渲染視圖（View 軌，由 ark-html-report 負責）
- **機器先於人**：frontmatter 契約讓下游 agent 不讀全文即可路由；人要看時才渲染 HTML
- **報告是時點快照（immutable）**，與 wiki 頁面（長期演化知識）分工：報告可被 wiki ingest 為 source，但不是 wiki 頁面本身

## 與 ark-wiki-engine 的分工

| | ark-md-report | ark-wiki-engine |
|---|---|---|
| 管什麼 | 文體：分析報告怎麼寫 | 庫：儲存、索引、檢索 |
| 生命週期 | 時點快照，產出後不改 | seedling → mature 持續演化 |
| frontmatter | verdict / findings / severity | type / status / related |
| 關係 | 報告 = wiki 的 ingest 素材（source） | wiki 蒸餾多份報告成 synthesis 頁 |

## 工作流程

### 1. 判斷報告類型

讀 `references/report-types.md`。五種類型：

| type | 場景 | 例 |
|------|------|-----|
| `review` | skill / code / 架構 review | ark-code-spec-validator 深度分析 |
| `competitive` | 競品 / 市場分析 | 競品日報的深度版 |
| `incident` | 事故 / 異常分析 | MCP stdio 污染事件復盤 |
| `decision` | 需求決策摘要 | **ark-grill-me 拷問後的產出** |
| `data` | 數據分析結論 | 留存分析、KPI 異常歸因 |

### 2. 寫 frontmatter 契約

讀 `references/frontmatter-contract.md`，填齊必要欄位。核心：`verdict`（枚舉結論）、`score`（如適用）、`findings_count`（按嚴重度統計）、`tags`（**只能用 wiki 受控詞彙表**，禁止自創）、`sources`（分析對象與證據路徑）。

### 3. 撰寫內文

嚴格遵循 `references/ai-writing-rules.md`。最重要的五條：

1. **結論先行**：第一個章節就是 verdict + 三句話內的依據，不做鋪陳
2. **Finding 有穩定 ID**（F-1、F-2…；decision 型用 D-1…），下游引用不因改寫而斷
3. **章節 chunk 自足**：每章可被單獨檢索取出而不失義 —— 不用「如上所述」「前者/後者」跨章指涉，主詞寫全名
4. **受控詞彙**：severity 只能是 P0/P1/P2/P3，confidence 只能是 high/medium/low，verdict 用類型對應枚舉
5. **主張—證據—信心三元組**：每個重要 finding 附證據（實測輸出/檔案路徑/數據）與 confidence，無證據的推測必須標 `confidence: low`

### 4. 存放與 wiki 相容性

- 路徑：`docs/reports/{type}/{date}-{slug}.md`（kebab-case，中文標題留 frontmatter title）
- 產出後自檢：frontmatter 欄位齊全、tags 都在受控詞彙表內、Finding ID 連續不重複
- 若專案有 wiki：報告路徑加入 wiki 頁面的 `sources` 欄位由 wiki-engine 蒸餾，**不要**直接把報告複製進 `wiki/` 目錄

### 5. 需要給人看時（View 軌）

讀 `references/html-mapping.md`，用 ark-html-report 的 token 系統與元件渲染。映射表定義了每個 MD 結構對應的 HTML 元件（verdict → KPI 卡片、findings 表 → 資料表格 + severity badge…），**渲染時只做視圖裁剪，禁止改寫任何 finding 內容或新增 MD 沒有的結論**（composer 不改寫原則）。

## 內容原則

- 一份報告只回答一個分析問題；範圍蔓延就拆兩份
- Finding 描述格式：「現象 + 位置 + 影響」，不寫「建議」在 finding 裡 —— 建議集中在獨立的 Actions 章節並帶 A-1 編號，與 finding 用 ID 互相引用
- 數字給比較基準（vs 上週 / vs 目標 / vs 同類），孤立數字對 AI 和人都無意義
- 反例與例外明寫：「本結論不適用於 X 情況」比讓下游 agent 自行推斷安全

---

## Deterministic 守門腳本

報告產出後**必須通過以下三步**才能宣告完成（不可跳過、LLM 自評不算數）：

```
scripts/
├── report_lint.py      # 契約驗證（frontmatter/枚舉/ID/統計/禁詞/章節）
├── report_pair.py      # 雙軌漂移檢查（MD↔HTML 配對 + sha256 戳記）
└── report_register.py  # 索引註冊（_index.md + log.md + wiki source 建議）
```

### report_lint.py — 契約守門

```bash
# 單檔驗證
python scripts/report_lint.py docs/reports/review/2026-08-11-xxx.md

# 全庫 lint
python scripts/report_lint.py docs/reports/**/*.md

# 加 wiki tags 白名單驗證
python scripts/report_lint.py --wiki-schema knowledge/proj/schema.md report.md
```

驗證項目：frontmatter 必要欄位 / verdict 枚舉合法 / confidence 合法 / severity 合法 / Finding ID 連續不重複 / findings 統計與表格行數一致 / chunk 自足禁詞 / 必要章節存在 / 檔名格式

### report_pair.py — 雙軌漂移防護

```bash
# 渲染後寫入戳記（html-report 渲染最後一步呼叫）
python scripts/report_pair.py stamp report.md report.html

# 檢查配對狀態
python scripts/report_pair.py check report.md
# → OK / STALE（MD 已改 HTML 未重渲染）/ NO-HTML / NO-STAMP

# 掃描整個目錄
python scripts/report_pair.py scan docs/reports/
```

### report_register.py — 索引與日報

```bash
# 註冊（更新 _index.md + 追加 log.md + wiki source 建議）
python scripts/report_register.py docs/reports/review/2026-08-11-xxx.md

# 含 wiki 建議
python scripts/report_register.py report.md --wiki knowledge/myproj
```

log.md 行格式（日報 CollectorRunner 解析契約）：
```
date|type|subject|verdict|p0|p1|p2|score|path
```

### Agent 交付流程

```
1. 產出 MD（ark-md-report 契約）
2. python scripts/report_lint.py {report.md}     → 必須 PASS
3. （需要 HTML）ark-html-report 渲染
4. python scripts/report_pair.py stamp {md} {html}
5. python scripts/report_register.py {report.md}
6. reply「報告已落盤 {path}｜verdict: {x}｜P0:{n}｜lint: PASS」
```

---

## 運作指南

完整三件套運作說明見 `references/agent-operating-guide.md`，涵蓋：
- 職責分工表（md-report / html-report / wiki-engine）
- 路由決策樹（lead-agent 用）
- 四條鐵律（貼入 SOUL.md）
- 各 Agent 提詞片段（insight / report / dev / grill-me）
- 目錄與命名約定
- 與 wiki 的邊界（三個常犯錯誤）
