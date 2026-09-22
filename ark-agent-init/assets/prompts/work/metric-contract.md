---
name: metric-contract
description: 新增或升版一個指標的語意契約（四件套 + 同義詞 + join key + 版本），並檢查與資料表欄位的漂移
layer: work
roles: [semantic-keeper]
tools_required: []
inputs: [metric_request, table_schema_path]
outputs:
  format: data
  contract: md-report
example: true
---

## 任務

為一個指標建立或升版語意契約：
1. 寫定義四件套：分子、分母、時間窗、過濾條件——缺一項不得發布
2. 業務用語進 `synonyms`，指標 id 用 snake_case；口徑基準（如指數基準=100 的母體）寫進 `baseline`
3. 列出計算所需 join key（player_id / campaign_id / experiment_id / activity_id）與來源表欄位
4. 改動任一項即升版；舊版標 `deprecated`，不刪
5. 狀態一律 `draft`；轉 `queryable` 需 golden questions ≥3 題（另用 golden-questions 提詞）
6. 若給了 table_schema_path，比對契約引用的欄位是否仍存在／型別是否變更，產 drift 清單

## 輸出樣板

```yaml
metric_id: <snake_case>
version: <major.minor>
status: draft | queryable | deprecated
definition:
  numerator: <一句話 + 欄位/條件>
  denominator: <一句話 + 欄位/條件>
  time_window: <以哪個日期欄位、窗長>
  filters: [<條件>]
baseline: <基準說明或 null>
synonyms: [<業務用語>]
join_keys: [<key>]
sources: [{ table: <表>, fields: [<欄位>] }]
golden_questions: <數量>
changelog: [{ version: <v>, date: <YYYY-MM-DD>, change: <一句話> }]
```
drift 清單（有 table_schema_path 時）：`| 契約引用欄位 | 表 | 狀態（存在/缺失/型別變更） |`

## 範例

### 輸入
metric_request：「隔天回來率，付費渠道加權，行銷月報在用的那個」；table_schema_path：`knowledge/aibi/raw/schema_installs.md`

### 期望輸出
```yaml
metric_id: d2_return_rate
version: 1.2
status: draft
definition:
  numerator: 安裝隔日（install_date+1）有 ≥1 session 的玩家數，installs JOIN sessions ON player_id
  denominator: 安裝日玩家數（installs，media_source != 'organic'）
  time_window: install_date，逐日 cohort，月報用月彙總
  filters: [media_source != 'organic']
baseline: 付費渠道加權（以各渠道 installs 為權重）
synonyms: [隔天回來率, D2, 次日留存（付費）]
join_keys: [player_id, campaign_id]
sources: [{ table: installs, fields: [player_id, install_date, media_source, campaign_id] }, { table: sessions, fields: [player_id, session_date] }]
golden_questions: 0
changelog: [{ version: 1.2, date: 2026-09-21, change: 改為付費渠道加權；1.1（未加權）deprecated }]
```
| 契約引用欄位 | 表 | 狀態 |
|---|---|---|
| media_source | installs | 存在 |
| session_date | sessions | 型別變更 DATE→TIMESTAMP（需 CAST） |
