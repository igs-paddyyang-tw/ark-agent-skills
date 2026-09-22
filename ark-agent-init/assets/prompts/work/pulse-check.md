---
name: pulse-check
description: 排程巡檢契約內指標，比常態波動區間、對照同期決策紀錄，只發附脈絡的告警並產每日脈搏
layer: work
roles: [pulse-monitor]
tools_required: []
inputs: [metric_list, ledger_path]
outputs:
  format: data
  contract: md-report
example: true
---

## 任務

1. 對 metric_list 每個 queryable 指標查當期值、基準與契約定義的常態波動區間
2. 超出區間才算異常；同指標同日已告警則去重不重發
3. 異常對照 ledger_path 同期事件（±3 天）：對上寫事件，對不上寫「無決策紀錄」
4. 每則告警固定五欄：指標｜當期 vs 基準｜偏離｜同期決策紀錄｜建議接手（investigator / semantic-keeper / 無需）
5. 產每日脈搏摘要（正常項一行帶過），推送 Telegram

## 輸出樣板

```
🚨 <metric_id> v<ver>｜<當期> vs <基準>｜<偏離>（常態 ±<x>）｜同期：<事件或無>｜建議：<角色>
✅ 正常：<指標清單>
```

## 範例

### 輸入
metric_list：[cpi_index, d2_return_rate, roas_30d_index]；ledger_path：`knowledge/shared/wiki/decision-ledger.md`

### 期望輸出
🚨 cpi_index v1.3｜6 月 75 vs 5 月 64｜+17%（常態 ±8%）｜同期：預算調整 554 次、無渠道變更單｜建議：insight-investigator
✅ 正常：d2_return_rate 38.1%（基準 38.8%，常態 ±1.5pp）、roas_30d_index（6 月未成熟，跳過）
