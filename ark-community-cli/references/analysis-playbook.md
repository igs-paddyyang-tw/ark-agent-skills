# 分析手冊：從 records 到痛點候選

腳本產「候選」，analyst 才下「結論」。每一步輸出都可重跑、可解釋、有數字。

## 統一 record schema（assets/schema-record.json）

| 欄位 | 說明 |
|---|---|
| `record_id` | `{source}:{原始 id}` 的 sha1 前 16 碼 |
| `source` | `discord` / `x` |
| `surface` | 沿用 player-voice schema：`discord` / `x`（外部）|
| `ts` | ISO8601 UTC |
| `author_key` | HMAC-SHA256(salt, 原始 author id) 前 16 碼 |
| `player_key` | 有對照表才有；X 永遠 null |
| `text` | 遮罩後原文 |
| `lang` | Discord 用簡單偵測（ja／zh／en／other）；X 用 API 回的 lang |
| `reply_to` | 上一則 record_id 或 null |
| `metrics` | Discord：reactions 總數；X：like／reply／repost／quote |
| `channel` / `query` | 來源頻道名或 query 名 |
| `duplicate_of` | 近似重複時指向原 record_id |
| `raw_ref` | raw 檔路徑 + 行號，只有這個能回到 PII |

## classify 三層

1. **feedback_type**（規則）：`assets/lexicon.yaml` 三語關鍵詞，命中最多者勝；頻道 `feedback_hint` 當先驗；平手或零命中 → `uncategorized`
2. **sentiment**（規則）：lexicon 正負詞計分 → `neg / neu / pos`；有 `oseti` 就換它（日文更準）。反諷、「神アプデ（笑）」抓不到 —— 這是已知限制，寫在報告 caveat
3. **cluster**：同 feedback_type 內，字元 3-gram Jaccard ≥ 0.35 連通分群；每群取 metrics 最高者為代表句，輸出 `cluster_id`、`size`、`distinct_authors`、`representative`、`members`

`uncategorized` 與 cluster size ≥ 3 但 feedback_type 混雜者 → `classify/llm-queue.jsonl`，交 agent 用 LLM 判。**LLM 只跑這批**，理由：省錢、可重現、規則層先把八成常見句吃掉。

## digest 週摘結構（ark-md-report 契約）

```yaml
---
report_type: analysis
title: "社群週摘 2026-W39"
verdict: watch                # ok | watch | act（由頻次門檻自動給，analyst 可改）
severity: P2
confidence: medium
trust: deterministic          # 統計是 deterministic；解讀段落由 analyst 補時改 llm-distilled
sources: [records/2026-09-15.jsonl, ...]
tags: [player-voice, weekly]
---
```

段落固定：
1. 摘要三句（則數／最大 cluster／與上週差）
2. 來源統計表（Discord／X 分開；則數、distinct authors、uncategorized%）
3. feedback_type × sentiment 表
4. Top 5 clusters：`F-{week}-{n}` 穩定 ID、size、distinct_authors、來源分布、代表句 ≤3 則（≤140 字）、對應 case 檔
5. 與上週比較：新出現 cluster、消失 cluster、頻次變化 > 50%
6. caveat：規則分類限制、抽樣率、預算未拉滿的 query

`verdict` 自動規則：任一 cluster `distinct_authors ≥ 10` 且 sentiment neg → `act`；≥ 5 → `watch`；否則 `ok`。analyst 可覆寫，覆寫要留原因。

## 案件卡（cases/{week}/F-*.md）

沿用 hoyeah player-voice 的 case 格式：`case_id / 時間窗 / 來源 / feedback_type / status: open / distinct player_key 數 / author_key 清單 / 代表句 / 全部 record_id`。沒有暱稱、沒有原始 ID。

## 給 analyst 的交叉分析入口

`records/*.jsonl` 的 `player_key` 可直接 join data-engineer 的分群表 → 「這個痛點是 whale 在喊還是 free-active 在喊」。本 skill 不做 join，只保證 key 穩定。

## 已知限制（寫進每份週摘 caveat）
- 規則情感對日文反諷、顏文字、「w」語尾無效
- X 抽樣受預算限制，則數不代表母體；報 distinct_authors 比報則數誠實
- Discord 與 X 不可合併計數（來源信任度不同）
- 遮罩後文本可能失去部分語意（序號、金額被遮）
