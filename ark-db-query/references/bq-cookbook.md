# BigQuery 省 bytes 查詢範本

原則：BigQuery 按「掃描位元組」計費，LIMIT 不省錢，**選欄位 + 分區過濾才省錢**。

## 分區過濾（最重要）
```sql
SELECT date, SUM(revenue) AS daily_revenue
FROM `proj.dataset.daily_kpi`
WHERE date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE()
GROUP BY date ORDER BY date DESC
```

## 探索性分析用取樣（不確定資料長相時）
```sql
SELECT * FROM `proj.dataset.big_table` TABLESAMPLE SYSTEM (1 PERCENT) LIMIT 100
```
（更省：直接用 bq_schema.py preview，零費用）

## 只選需要的欄位
```sql
-- 差: SELECT * FROM events            -- 掃全表所有欄
-- 好: SELECT user_id, event_name, ts FROM events WHERE ...
```

## 去重最新一筆
```sql
SELECT * EXCEPT(rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY updated_at DESC) rn
  FROM `proj.dataset.player_profile`
  WHERE _PARTITIONDATE >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
) WHERE rn = 1
```

## 查表大小與分區欄（寫 SQL 前先跑，零費用）
```bash
python scripts/bq_schema.py tables --project proj --dataset dataset
```
