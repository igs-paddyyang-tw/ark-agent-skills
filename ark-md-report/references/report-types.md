# 報告類型結構（五種）

所有類型共享骨架：**Verdict（結論先行）→ Findings/主體（帶 ID）→ Evidence（證據）→ Actions（建議，帶 ID）→ 邊界聲明**。
以下為各類型的章節模板。章節標題固定（下游以標題錨定），內容依 ai-writing-rules 撰寫。

---

## 1. review（skill / code / 架構 review）

```markdown
## Verdict
{verdict 枚舉} — 三句話內說明依據。例：needs-work — 骨架健康，但 P0 兩項
（鏈級交接斷點、預設模式驗證必敗）使核心流程無法端到端跑通。

## Findings

| ID | 嚴重度 | 現象 | 位置 | 影響 |
|----|--------|------|------|------|
| F-1 | P0 | plan 模板任務表欄位與 spec-executor 解析格式不相容 | references/templates/zh-TW/plan-full.md | superpowers 產出的 plan 無法被 executor 執行 |
| F-2 | P0 | type: one-pager 不在 checker 字典 | scripts/check_doc_completeness.py | 預設模式產出 100% 驗證失敗 |

## Evidence

### E-1（支持 F-2）
- 方法：以 skill 自帶 checker 實跑自帶模板
- 輸出：`❌ FAIL: onepager.md — 未知的文件類型：one-pager`
- confidence: high

## Actions

| ID | 對應 Finding | 建議 | 估時 |
|----|--------------|------|------|
| A-1 | F-1 | plan 模板改為 executor 相容七欄格式 | 60min |

## 邊界聲明
- 本分析基於 {date} 的 main 分支快照（commit {sha}），此後的改動不在結論範圍
- 未涵蓋：{明確列出沒分析的部分}
```

## 2. competitive（競品分析）

```markdown
## Verdict
{ahead|parity|behind|divergent} — 依據。

## 比較矩陣

| 維度 | 我方 | 競品 A | 競品 B | 差距評估 |
|------|------|--------|--------|----------|

## Findings
（同 review 表格，「位置」欄改「來源」）

## Evidence
（每個 finding 的資料來源 + 抓取日期 + confidence；二手來源必標 medium 以下）

## Actions

## 邊界聲明
- 資訊時效：{expires}，競品資料截至 {date}
- 未驗證項：{哪些是公開資訊推斷而非實測}
```

## 3. incident（事故分析）

```markdown
## Verdict
{resolved|mitigated|open} — 一句話根因。

## 時間軸

| 時間 | 事件 | 來源 |
|------|------|------|
（絕對時間戳，不用「稍後」「隨即」）

## 根因鏈
觸發 → 傳播 → 影響，每一環附 Evidence ID。

## Findings
（根因、放大因素、防護缺口各為獨立 finding）

## Evidence

## Actions
（區分：立即修復 / 防再發 / 監測補強）

## 邊界聲明
- 未排除的替代假設：{列出並附排除或保留原因}
```

## 4. decision（需求決策摘要 — ark-grill-me 產出適用）

```markdown
## Verdict
{decided|partially-decided|blocked} — 本輪拷問覆蓋 N 題，形成 M 項決策。

## Decisions

| ID | 決策 | 選項與取捨 | 依據（拷問題號） | 狀態 |
|----|------|------------|------------------|------|
| D-1 | 採用 AC-ID 純字串匹配 | vs jieba 斷詞：deterministic 優先 | Q3, Q7 | decided |
| D-2 | Schema 維度 v2 範圍 | — | Q12 | blocked（待 O-1） |

## 需求邊界
- 範圍內：…
- 明確排除（非目標）：…

## Open Questions

| ID | 問題 | 阻塞哪些決策 | 建議解法 |
|----|------|--------------|----------|
| O-1 | … | D-2 | … |

## Evidence
（關鍵決策引用拷問對話中的原始回答，標註題號）

## 邊界聲明
- 本摘要反映 {date} 拷問時點的認知；O-x 解決後應產新版本並在 related_reports 連結
```

規則：grill-me 完成拷問後，以此結構落盤決策摘要，frontmatter `type: decision`。
下游 superpowers 寫 spec 時，`related_reports` 指回此摘要，Decisions 的 D-x 可被 spec 章節引用。

## 5. data（數據分析結論）

```markdown
## Verdict
{confirmed|rejected|inconclusive} — 假設一句話 + 結論一句話。

## 假設與方法
- 假設：…
- 資料範圍：{時間窗、樣本數、來源}
- 方法：{查詢/統計方式，可重現}

## Findings
（每個 finding 附效應大小與比較基準，不只方向）

## Evidence
（查詢語句或腳本路徑 + 原始輸出摘錄）

## Actions

## 邊界聲明
- 混淆因素：{未控制的變因}
- 不可外推範圍：{結論不適用的情境}
```
