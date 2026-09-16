---
name: service-check
description: 查詢團隊服務狀態並回報在線數與異常
layer: ops
roles: [admin]
tools_required: [query_team_status, reply]
inputs: []
outputs:
  format: none
  contract: none
example: true
---

## 任務

用 `query_team_status()` 查詢團隊狀態，回報：
1. 在線 agent 數量（X/N running）
2. 有無異常或待處理事項

用 `reply` 回報結果，不超過 100 字。

## 輸出樣板

```
在線：<X>/<N> running
異常：<無 | 描述>
待處理：<無 | 項目>
```

## 範例

### 輸入
（管理員觸發服務檢查，無額外輸入）

### 期望輸出
在線：10/11 running（第 11 個 lazy spawn，用到才起）
異常：無
待處理：無
