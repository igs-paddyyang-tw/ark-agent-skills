---
name: ark-file-export
description: |
  [DEPRECATED — 已由 ark-etl-pipeline 取代]
  保留本頁只為讓舊觸發詞（匯出檔案、存成 CSV、輸出 JSON、產生 Markdown 檔、資料備份）
  仍能導向遷移說明 —— **不要使用本 skill，改用 `ark-etl-pipeline` 的 Load/匯出 章節。**
metadata:
  schema_version: 1
  status: deprecated
  superseded_by: ark-etl-pipeline
  updated: 2026-09-14
  author: paddyyang
  category: pipeline
  outputs:
    - format: md
      audience: ai
---

# ark-file-export（已棄用）

> 🗑️ **此 skill 已於 2026-09-14 併入 `ark-etl-pipeline`。**

「記憶體資料（dict/list/str）→ 磁碟檔案（.md/.csv/.json）」的匯出能力，
已成為 ETL 管線的 **Load** 階段（Extract → Transform → Load）。

## 遷移

| 舊用法 | 新用法 |
|---|---|
| ark-file-export（存成 MD/CSV/JSON） | `ark-etl-pipeline` 的「Load / 匯出（Sink 步驟）」章節 |

舊觸發詞「匯出檔案」「存成 CSV」「輸出 JSON」「產生 Markdown 檔」「資料備份」
仍導向此頁，請改用 `ark-etl-pipeline`。複雜格式（PDF/Word/Excel/PPT）
請用對應的 `ark-docx-tool` / `ark-pdf-tool` / `ark-xlsx-tool` / `ark-pptx-tool`。
