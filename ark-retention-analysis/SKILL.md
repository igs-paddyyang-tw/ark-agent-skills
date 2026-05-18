---
name: ark-retention-analysis
description: |
  玩家留存與 LTV 分析：Cohort 分析、留存曲線、LTV 預測、流失預警。
  使用此 Skill 當使用者提及留存分析、retention、LTV、流失率、
  cohort、玩家生命週期、D1/D7/D30、或任何需要分析玩家留存的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-16
---

# ark-retention-analysis

玩家留存與 LTV 分析 — Cohort / 留存曲線 / LTV 預測 / 流失預警。

## 觸發條件

- 「留存分析」「retention」「LTV」
- 「流失率」「cohort」「玩家生命週期」
- 「D1/D7/D30」「留存曲線」

---

## 核心指標

| 指標 | 公式 | Slot 業界基準 |
|------|------|-------------|
| D1 留存 | Day1 活躍 / Day0 新增 | 35-45% |
| D7 留存 | Day7 活躍 / Day0 新增 | 15-20% |
| D30 留存 | Day30 活躍 / Day0 新增 | 5-8% |
| LTV | Σ(ARPDAU × 留存率) | 依產品 |
| Churn Rate | 1 - 留存率 | — |
| Stickiness | DAU / MAU | 20-30% |

---

## Cohort 分析 SOP

### 1. 建立 Cohort 表

```
         Day0  Day1  Day3  Day7  Day14  Day30
Week 1   1000  420   280   180   120    60
Week 2   1200  480   310   200   130    65
Week 3   800   360   240   160   100    50
```

### 2. 計算留存率

```python
retention_rate = active_users[day_n] / cohort_size[day_0]
```

### 3. 繪製留存曲線

- X 軸：天數（0, 1, 3, 7, 14, 30, 60, 90）
- Y 軸：留存率（%）
- 分群比較（付費 vs 免費、管道 A vs B）

### 4. 找出關鍵流失點

- D0→D1 流失 > 60% → 首日體驗問題
- D1→D3 流失 > 50% → 內容深度不足
- D7→D14 流失 > 40% → 缺乏長期目標

---

## LTV 預測

### 簡易公式

```
LTV = ARPDAU × (1 / (1 - 留存率))
```

### 進階：Cohort-based LTV

```python
def predict_ltv(cohort_retention: list[float], arpdau: float) -> float:
    return sum(rate * arpdau for rate in cohort_retention)
```

### LTV/CAC 健康度

| 比率 | 判斷 |
|------|------|
| LTV/CAC > 3 | 健康，可加大投放 |
| LTV/CAC 1-3 | 需優化 |
| LTV/CAC < 1 | 虧損，停止投放 |

---

## 流失預警

### 預警信號

| 信號 | 閾值 | 動作 |
|------|------|------|
| 連續 3 天未登入 | D3 inactive | 推播提醒 |
| Session 時長下降 50% | vs 前 7 天均值 | 個人化推薦 |
| 付費頻率下降 | vs 歷史均值 | 限時優惠 |
| 社交互動歸零 | 0 次/週 | 好友邀請活動 |

### 自動化流程

```
監測 → 標記風險玩家 → 分群 → 觸發對應策略 → 追蹤回流率
```

---

## 與 OceanKing 整合

- 📈 小櫻：BigQuery 查詢 + Python 分析
- 📊 鹿丸：營運指標追蹤 + A/B 測試
- 🧠 佐助：數值調整建議

## 注意事項

- 留存數據需等足天數才有意義（D30 需等 30 天）
- 不同管道的 cohort 要分開看
- LTV 預測有不確定性，需定期校準
- 流失預警需要即時數據管線（非批次）
