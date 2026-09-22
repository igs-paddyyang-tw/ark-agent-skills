---
name: nl2sql
description: 把自然語言問題翻成契約內的 SQL，先小樣本驗證再執行，回傳結果附 SQL 與契約版本
layer: work
roles: [query-analyst, aibi-manager]
tools_required: []
inputs: [question]
outputs:
  format: data
  contract: md-report
example: true
---

## 任務

1. 比對問題與語意契約：鎖定 metric_id 與 version；對不上 → 回「尚未定義」並列出最接近的契約項，轉 semantic-keeper，**不生成 SQL**
2. 依契約的 sources / join_keys / filters 生成 SQL；先 `LIMIT 20` 驗欄位意義，再跑正式查詢
3. 回傳：結果表 + 契約 id/version + 完整 SQL + 注意事項（時間窗、分母、口徑）
4. 比率必附分子與分母；不得回傳個別玩家可識別欄位
5. 查詢範本入自己的 `knowledge/wiki/`（問題 → SQL 對應）

## 輸出樣板

```
契約：<metric_id> v<version>（狀態 queryable）
| <維度> | <值> | 分子 | 分母 | 時間窗 |
SQL：
```sql
<完整 SQL>
```
注意：<口徑/時間窗/未含項>
```
契約外時：
```
尚未定義：「<問題>」對不上契約。最接近：<metric_id>（差異：<一句話>）。已轉 semantic-keeper 建契約。
```

## 範例

### 輸入
question：「2026-05 各渠道帶一個新玩家的成本指數」

### 期望輸出
契約：cpi_index v1.3（queryable）
| 渠道 | CPI 指數 | 花費（指數） | installs | 時間窗 |
|---|---|---|---|---|
| ASA 品牌詞 iOS | 21 | — | 1,842 | 2026-05 install_date |
| Google Android | 52 | — | 6,210 | 2026-05 |
| FB Android | 72 | — | 9,455 | 2026-05 |
| FB iOS | 93 | — | 4,120 | 2026-05 |
SQL：
```sql
WITH base AS (SELECT AVG(cost/installs) AS avg_cpi FROM ua_daily WHERE media_source!='organic' AND dt BETWEEN '2025-06-01' AND '2026-06-30')
SELECT channel, ROUND(SUM(cost)/SUM(installs)/b.avg_cpi*100) AS cpi_index, SUM(installs) AS installs
FROM ua_daily, base b WHERE dt BETWEEN '2026-05-01' AND '2026-05-31' AND media_source!='organic'
GROUP BY channel, b.avg_cpi ORDER BY cpi_index;
```
注意：基準=13 個月付費渠道平均 100；Google iOS 因歸因斷裂未列（契約 v1.3 排除）。
