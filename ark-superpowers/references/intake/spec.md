# intake/spec.md — spec 訪談題庫（ADR-005）

每題對應一個章節鍵與 ID 前綴。**不知道的答案一律寫成 `OQ-`（blocking），不要腦補。**

| # | 章節鍵 | 問題 | 產出 |
|---|--------|------|------|
| 1 | summary | 一句話說明這份 spec 要解決什麼問題？ | 摘要 |
| 2 | motivation | 為什麼現在要做？不做的代價是什麼？ | 動機 |
| 3 | goals | 這次要達成哪些目標（≥2）？哪些明確不做（≥1）？ | 目標與非目標 |
| 4 | stories | 誰用、要做什麼、怎麼算成功（EARS：WHEN…THE SYSTEM SHALL…）？ | FR-x |
| 5 | nfr | 效能/可用性/安全等維度的量化目標值？怎麼驗證？ | NFR-x |
| 6 | constraints | 有哪些外部約束（來自決策摘要 D-x、技術/法規/相容性）？ | C-x（source: D-x） |
| 7 | metrics | 上線後看哪些指標判斷成功？目標值多少？ | SC-x |
| 8 | open | 現在還不確定、需要之後釐清的事項？ | OQ-x（blocking） |

> one-pager 場景只用 #1/#3/#7/#8 精簡四題。
> from-decision 已把 D-x 填入 C-x、未決事項填入 OQ-x，其餘題目逐一補洞。
