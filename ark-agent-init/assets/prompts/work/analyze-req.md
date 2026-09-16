---
name: analyze-req
description: 把模糊需求拆成可驗收的 AC，標出待確認的假設
layer: work
roles: [architect, leader, fullstack-coder]
tools_required: []
inputs: [requirement]
outputs:
  format: md
  contract: ac-table
example: true
---

## 任務

把使用者需求拆成可驗收條件（AC）：
1. 逐條列出「完成時使用者看到什麼」
2. 每條 AC 標可驗證的判準（輸入 → 期望輸出）
3. 無法確定的用假設列出，標「待確認」讓使用者推翻
4. 不確定範圍就先問，最多兩次；第三次自己做假設寫進表

## 輸出樣板

```
| AC-ID | 條件 | 驗收判準 | 狀態 |
|-------|------|---------|------|
| AC-1  | <條件> | <輸入→期望輸出> | 確定 / 待確認 |
```

## 範例

### 輸入
使用者：「幫我做一個每日 KPI 報表」

### 期望輸出
| AC-ID | 條件 | 驗收判準 | 狀態 |
|-------|------|---------|------|
| AC-1 | 每日 09:00 自動產出前一日 KPI | 排程觸發，artifacts/reports/ 出現當日檔 | 確定 |
| AC-2 | 含 DAU / 留存 / ARPU 三指標 | 報表三欄皆有數值且非空 | 待確認（指標清單需使用者確認） |
| AC-3 | 發送到指定頻道 | 收件人收到訊息 | 待確認（收件人未定） |
