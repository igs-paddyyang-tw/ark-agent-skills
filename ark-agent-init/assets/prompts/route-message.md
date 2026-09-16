---
name: route-message
description: 收到使用者訊息後判斷意圖並路由到對的 agent 或自處理
layer: ops
roles: [admin, manager]
tools_required: [send_to_instance, reply]
inputs: [user_message]
outputs:
  format: none
  contract: none
example: true
---

## 任務

收到使用者訊息後，判斷意圖並路由：

- 分析/業務需求 → `send_to_instance("{{leader_name}}", 訊息)`
- 服務問題/技術決策 → 自己處理
- 不確定 → 詢問使用者意圖

最後用 `reply` 回報處理結果。

## 輸出樣板

```
意圖：{分析|技術|不確定}
動作：{已轉交 {{leader_name}} | 自處理 | 詢問}
回覆：（給使用者的一句話）
```

## 範例

### 輸入
使用者：「幫我分析上一版的留存為什麼掉」

### 期望輸出
意圖：分析
動作：已轉交 {{leader_name}}（留存分析屬業務需求）
回覆：已請團隊分析留存下降原因，有結果回報你。
