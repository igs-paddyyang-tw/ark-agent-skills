---
name: scaffold-api
description: 依需求產出 API 端點表（method/path/req/resp/錯誤碼）
layer: work
roles: [architect]
tools_required: []
inputs: [spec_path]
outputs:
  format: md
  contract: endpoint-table
example: true
---

## 任務

依規格設計 API 端點：
1. 列出每個端點的 method / path / 請求 / 回應 / 錯誤碼
2. 路徑用 RESTful 慣例；錯誤碼對齊專案既有規範
3. 標出需認證的端點
4. 不臆測業務欄位，缺的列「待規格補」

## 輸出樣板

```
| Method | Path | 請求 | 回應 | 錯誤碼 | 認證 |
|--------|------|------|------|--------|------|
| <GET>  | </resource> | <query/body> | <200 body> | <4xx/5xx> | 是/否 |
```

## 範例

### 輸入
規格：玩家查詢自己的餘額與最近 10 筆交易

### 期望輸出
| Method | Path | 請求 | 回應 | 錯誤碼 | 認證 |
|--------|------|------|------|--------|------|
| GET | /players/me/balance | — | `{balance: int, currency: str}` | 401 未認證 | 是 |
| GET | /players/me/transactions | `?limit=10` | `{items: [{id,amount,ts}]}` | 401, 400 limit 超上限 | 是 |
