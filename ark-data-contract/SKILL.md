---
name: ark-data-contract
description: "當使用者需要驗證管線元件間的 schema 契約時使用此技能。觸發條件包括：提及「資料契約」「schema 驗證」「管線契約」，或需要確保上下游元件的輸入/輸出格式一致。適用於 ETL 管線、agent 間訊息傳遞、API 回應格式的契約定義與驗證。不適用於資料庫查詢——該場景請用 ark-db-query。"
metadata:
  schema_version: 1
  status: active
  author: paddyyang
  category: pipeline
  outputs:
    - format: md
      audience: ai
---

# ark-data-contract

> 管線元件間 schema 契約驗證。

## 觸發條件

- 使用者提及「資料契約」「schema 驗證」「管線契約」
- 需要定義或驗證上下游元件的資料格式
- 管線元件整合時的格式一致性檢查

## Negative Trigger

- 資料庫查詢 → 請用 `ark-db-query`
- ETL 管線建構 → 請用 `ark-etl-pipeline`

## 工作流程

1. 定義契約 schema（JSON Schema / Pydantic model / TypedDict）
2. 標記生產者（producer）與消費者（consumer）
3. 驗證實際輸出是否符合契約
4. 偵測 breaking change（欄位移除 / 型別變更 / 必填新增）
5. 產出契約驗證報告

## 產出格式

- 契約定義文件（schema + 版本 + owner）
- 驗證結果（pass / fail + 違規明細）
- Breaking change 警告與遷移建議
