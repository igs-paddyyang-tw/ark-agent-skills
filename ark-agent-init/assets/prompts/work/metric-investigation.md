---
name: metric-investigation
description: 拆解一個指標變化：貢獻因子排序量化、對照 Decision Ledger 與 wiki 先例、標證據等級、寫出已排除假設
layer: work
roles: [insight-investigator]
tools_required: []
inputs: [metric_id, period_from, period_to, ledger_path]
outputs:
  format: data
  contract: md-report
example: true
---

## 任務

1. 第一步固定：拉 Decision Ledger（ledger_path）與 Log_16 操作紀錄，把事件對上 period 內的拐點
2. 查 wiki 先例（ark-wiki-engine wiki_query）：同指標歷次歸因結論
3. 列 ≥3 個競爭假設，逐一用數據檢驗；每個因子量化貢獻（佔變化 % 或 pp）並排序
4. 每個結論標證據等級：`causal`（有 experiment assignment / holdout）、`corr`（觀察相關）、`hypothesis`（待驗）
5. 證據等級的判定規則：缺 experiment assignment 或 holdout 紀錄時，等級上限為 `corr`
6. 已排除的假設必寫排除依據；產 data 型報告，Verdict 用 confirmed / rejected / inconclusive
7. 結論入 wiki（含證據等級）

## 輸出樣板

```
Verdict：<confirmed|rejected|inconclusive>（主因等級 <causal|corr>）
| 排名 | 因子 | 貢獻 | 證據等級 | 證據 |
已排除假設：<假設｜排除依據>
待驗假設：<假設｜建議驗證方法（holdout/on-off/對照）>
同期決策紀錄：<日期｜事件｜來源>
下一步：<一句話>
```

## 範例

### 輸入
metric_id：`cpi_index`；period：2026-05 → 2026-06；ledger_path：`knowledge/shared/wiki/decision-ledger.md`

### 期望輸出
Verdict：inconclusive（主因等級 corr）
| 排名 | 因子 | 貢獻 | 證據等級 | 證據 |
|---|---|---|---|---|
| 1 | 預算調整次數 554 次/月（FB 485） | 約 60% 的 +11pt | corr | 加碼後 7 天中位 1.12、減碼 1.03，無改善 |
| 2 | FB iOS 素材連續 6 週未換 | 約 25% | corr | FB iOS CPI 指數 88→101，其他渠道持平 |
| 3 | 6 月回收數字未成熟 | 約 15% | corr | 契約 roas 註記：只會更高不會更低 |
已排除假設：ASA 量價變動｜ASA CPI 21→22、installs 持平，貢獻 <2%
待驗假設：市場季節性（6 月買量成本週期）｜與 2025-06 同期對照 + 外部環境 collector
同期決策紀錄：2026-06-03 FB Android 預算上調（Log_16）；2026-06-12 無渠道變更單；無 experiment assignment 紀錄
下一步：7 月設調幅護欄（單次 ≤20%、週節奏）後對照；FB iOS 排素材測試
