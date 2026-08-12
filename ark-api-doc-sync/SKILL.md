---
name: ark-api-doc-sync
description: "當使用者需要將 FastAPI route 定義同步到 docs/ 目錄下的 API 文件表格時使用此技能。觸發條件包括：提及「API 文件同步」「route 變更同步」「端點文件化」，或在新增/修改 route 後要求更新對應文件。目標是消滅 extra_in_code drift（程式碼有但文件沒有的端點）。不適用於驗證 drift 或規格偏差——該場景請用 ark-code-spec-validator。"
metadata:
  author: paddyyang
  category: pipeline
  outputs:
    - format: md
      audience: ai
---

# ark-api-doc-sync

> FastAPI route → docs/ API 表格自動同步。消滅 extra_in_code drift。

## 觸發條件

- 使用者提及「API 文件同步」「route 變更同步」「端點文件化」
- 新增或修改 FastAPI route 後需要更新文件
- 要求產出或刷新 API 端點清單

## Negative Trigger

- 驗證 drift（程式碼 vs 規格偏差）→ 請用 `ark-code-spec-validator`
- API 設計或規格撰寫 → 不在本 skill 範圍

## 工作流程

1. 掃描指定目錄下所有 FastAPI router 檔案
2. 解析 route decorator（method / path / summary / response_model）
3. 比對現有 docs/ 下的 API 表格
4. 產出差異報告 + 自動更新 Markdown 表格
5. 輸出同步結果摘要

## 產出格式

- Markdown 表格（method / path / summary / status_code / auth）
- 差異摘要（新增 / 移除 / 變更）
