---
name: ark-api-doc-sync
description: |
  [DEPRECATED — 已由 ark-code-spec-validator 取代]
  保留本頁只為讓舊觸發詞（API 文件同步、route 變更同步、端點文件化）仍能導向遷移說明 ——
  **不要使用本 skill，改用 `ark-code-spec-validator` 的 --sync 模式。**
metadata:
  schema_version: 1
  status: deprecated
  superseded_by: ark-code-spec-validator
  updated: 2026-09-14
  author: paddyyang
  category: pipeline
  outputs:
    - format: md
      audience: ai
---

# ark-api-doc-sync（已棄用）

> 🗑️ **此 skill 已於 2026-09-14 併入 `ark-code-spec-validator`。**

FastAPI route → docs/ API 表格的反向同步能力，已整合為 validator 的 `--sync` 模式
（沿用同一套 route 解析邏輯，避免兩份實作漂移）。

## 遷移

| 舊用法 | 新用法 |
|---|---|
| ark-api-doc-sync（同步 route 到 docs 表格） | `python -m ark_team_agent.code_spec_validator --sync .` |

舊觸發詞「API 文件同步」「route 變更同步」「端點文件化」仍導向此頁，
請改用 `ark-code-spec-validator`。
