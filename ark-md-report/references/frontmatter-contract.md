# Frontmatter 契約（機器可解析）

下游消費者：日報 CollectorRunner、wiki-engine ingest、其他 agent 的路由判斷。
原則：**agent 只讀 frontmatter 就能決定要不要讀全文**。

## 必要欄位（所有類型）

```yaml
---
title: "ark-superpowers 深度分析"        # 人類可讀標題（可中文）
type: review                              # review | competitive | incident | decision | data
subject: "ark-agent-skills/ark-superpowers"  # 分析對象（repo 路徑 / 產品名 / 事件名 / 功能名）
date: 2026-08-11                          # 分析時點（快照日期）
author: claude                            # 產出者（agent 名或人名）
source_skill: ark-md-report               # 產出此報告的 skill
verdict: needs-work                       # 枚舉結論，見下表
confidence: high                          # high | medium | low（整體結論信心）
findings: { p0: 2, p1: 2, p2: 5 }        # 按嚴重度統計（decision 型改用 decisions: N）
tags: [skill-review, superpowers]         # 只能用 wiki 受控詞彙表，禁止自創
sources:                                  # 證據與分析對象路徑
  - ark-agent-skills/ark-superpowers/SKILL.md
  - 實測輸出（見內文 Evidence 區塊）
---
```

## verdict 枚舉（依 type）

| type | verdict 允許值 |
|------|----------------|
| review | `sound`（健康）/ `needs-work`（可用但需改）/ `broken`（核心功能失效）|
| competitive | `ahead` / `parity` / `behind` / `divergent`（不同賽道）|
| incident | `resolved` / `mitigated` / `open` |
| decision | `decided` / `partially-decided` / `blocked` |
| data | `confirmed`（假設成立）/ `rejected` / `inconclusive` |

## 選用欄位

```yaml
score: 72                    # 量化分數（如 validator drift score），無則省略
score_version: "v2"          # 評分公式版本（跨期比較用）
related_reports: []          # 前次同 subject 報告路徑（趨勢追蹤）
expires: 2026-11-11          # 結論時效（競品/數據類建議填，過期後下游應重驗）
loop_stage: post-validator   # 四段鏈場景：報告產生於鏈的哪一站
---
```

## 欄位規則

- `tags` 驗證：產出前對照 wiki 受控詞彙表（`knowledge/{project}/schema.md` 的 tags 白名單）；表中沒有的概念，用最接近的既有 tag，並在報告末尾「詞彙表建議」章節提議新增 —— 由人審核入表，不自動擴充
- `findings` 統計必須與內文 Finding 表格逐項一致（自檢項）
- `subject` 用可解析的穩定識別子（repo 相對路徑、產品正式名），不用口語稱呼 —— 這是跨報告聚合的 join key
- 日期一律 `YYYY-MM-DD`，不寫「今天」「上週」
