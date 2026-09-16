# id-scheme.md — Ark 文件鏈 ID 前綴（ADR-002 單一定義）

下游（executor / validator）以這些 ID 追溯每一條需求。本 skill 是**產生端**。
`build_docs.py` 集中配號，避免 LLM 手配重號。`doc_lint` 的 SP-010 驗唯一/連號。

| 前綴 | 用途 | 擁有者 | 出現於 |
|------|------|--------|--------|
| `FR-NNN` | 功能需求（使用者故事列） | superpowers | spec |
| `NFR-NNN` | 非功能需求 | superpowers | spec |
| `C-NNN` | 約束條件（`source: D-x`） | superpowers | spec |
| `SC-NNN` | 成功指標 | superpowers | spec |
| `OQ-NNN` | 開放問題（可標 `blocking`） | superpowers | spec / design |
| `DD-NNN` | 設計決策（非架構級，隨 design 版本化） | superpowers | design |
| `CMP-NNN` | 元件 | superpowers | design |
| `API-NNN` | API 表格每列 | superpowers | design |
| `ADR-NNN` | 架構決策（MADR 4 單一編號空間） | superpowers | adr（獨立檔） |
| `CF-NNN` | Confirmation 機檢規則（validator 依賴維度輸入） | superpowers | adr |
| `AC-NNN` | 驗收條件 | **ark-spec-executor** | plan（本 skill 不配號，委派） |
| `D-x` | 決策點（來自 grill-me 決策摘要） | **ark-grill-me** | decision（`from-decision` 逐字進 C-x） |

## 格式規則

- 三位數零填充：`FR-001`（`SP-010 id_sequence` 驗連號、`id_unique` 驗不重號）
- 同前綴在單一文件內唯一；跨文件參照用完整 ID（`C-001 source: D-1`）
- `--chain` 驗參照完整性：`C-x` 的 `source` D-x 須在 `related_reports` 的決策摘要找得到（SP-014）；
  `related_*` 路徑存在且型別正確（SP-020）

## 與 executor 的分工（附錄 B）

- superpowers 擁有上表除 AC/D-x 外的全部；`ark-spec-executor` 的 `plan-contract.md` 擁有 `AC-`；
  兩邊以 `depends_on` 互引，定義只寫一次。
- `backfill-ids` 對既有文件一次性補號（保留舊文字，只加前綴）。
