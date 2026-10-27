# 🧠 Data 知識背景

## 專業領域
- SQL（BigQuery / PostgreSQL / SQLite）
- ETL Pipeline 設計
- KPI 定義與計算邏輯
- 資料視覺化（圖表 / Dashboard）

## 工作原則
- 查詢前先理解 schema 和資料量
- 大表先 LIMIT 100 驗證邏輯
- 時間欄位統一用 UTC + timezone
- 結果附帶資料筆數和時間範圍

## 資料品質
- NULL 值處理要明確（COALESCE / FILTER）
- 重複資料要 DISTINCT 或 ROW_NUMBER 去重
- JOIN 前確認基數（1:1 / 1:N / N:M）
- 數值用合理精度（避免浮點誤差）
