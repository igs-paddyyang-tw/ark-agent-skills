# AI 可讀寫作規則

報告的第一讀者是 agent（RAG 檢索、日報蒸餾、下游決策），第二讀者才是人。
以下規則讓報告在「被切塊檢索」「被部分引用」「被程式解析」時仍然可靠。

## 1. 結論先行，倒金字塔

- 第一章節必是 `## Verdict`，三句話內給結論與依據
- 每個章節第一句是該章結論，細節往後排 —— 檢索只取回章節前半時仍不失義
- 禁止「經過深入分析後我們發現…」式鋪陳

## 2. Chunk 自足（最重要）

報告會被 bm25s/向量檢索切塊取用，單一章節必須獨立可讀：

- **不跨章指涉**：禁用「如上所述」「前述問題」「前者/後者」「該問題」——寫全名或 Finding ID
- **主詞寫全**：不寫「這個 skill 的檢查器」，寫「ark-superpowers 的 check_doc_completeness.py」
- **章節標題含檢索關鍵詞**：「## plan 模板與 spec-executor 的格式相容性」優於「## 問題二」——bm25s+jieba 靠標題詞命中
- 每章開頭可加一行 context 錨：`> subject: ark-superpowers · type: review · date: 2026-08-11`（長報告建議，短報告可省）

## 3. 受控詞彙（controlled vocabulary）

| 欄位 | 允許值 | 禁止 |
|------|--------|------|
| severity | P0 / P1 / P2 / P3 | 「嚴重」「很糟」「critical-ish」 |
| confidence | high / medium / low | 「應該吧」「大概」「99%」 |
| verdict | 依 type 枚舉（見 frontmatter-contract） | 自由文字結論 |
| tags | wiki 受控詞彙表 | 自創 tag |

嚴重度定義：P0 = 核心流程失效或資料錯誤；P1 = 準確性/可信度受損；P2 = 效率/維護性問題；P3 = 建議性改善。

## 4. 主張—證據—信心三元組

- 每個 P0/P1 finding 必須有對應 Evidence（E-x），內含：方法、可驗證的輸出（指令 + 結果、檔案路徑 + 行號、數據 + 查詢）、confidence
- 推測沒有實測 → 必標 `confidence: low`，且 Actions 中對應建議標「先驗證再執行」
- 引用外部資料標抓取日期；引用對話標題號（decision 型）

## 5. 穩定 ID 與引用

- Finding：F-1…；Action：A-1…；Evidence：E-1…；Decision：D-1…；Open Question：O-1…
- ID 一經發布不重排 —— 後續修訂新增用下一號，刪除標 `(withdrawn)` 不回收編號
- 跨報告引用格式：`{report-path}#F-3`

## 6. 表格為主要載體

- Findings / Decisions / Actions 一律表格 —— 下游以「表頭錨定 + 逐列解析」消費
- 表頭欄名固定（照 report-types.md），不增刪改名；額外資訊放表格後的補充段落
- 每格一個事實；需要兩句話的內容放到 Evidence

## 7. 邊界聲明是必要章節

AI 下游最危險的是把過期或範圍外的結論當現況。每份報告最後必有 `## 邊界聲明`：

- 分析基準（日期 / commit / 資料窗）
- 明確未涵蓋的範圍
- 結論不適用的情境
- 時效（如 frontmatter 有 expires）

## 8. 禁止事項

- 禁止在 Findings 裡混入建議（建議只在 Actions）
- 禁止孤立數字（一律附比較基準）
- 禁止用 emoji 承載語義（✅❌ 可作視覺輔助，但判定結果必須同時有文字枚舉）—— 下游可能在純文字管道消費
- 禁止「詳見上文」式的懶引用
