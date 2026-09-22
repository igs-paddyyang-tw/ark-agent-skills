---
name: db-migration
description: 依 schema 變更需求產出可回滾的資料庫遷移計畫
layer: work
roles: [backend]
tools_required: []
inputs: [change_request]
outputs:
  format: md
  contract: none
example: true
---

## 角色與邊界

職責：後端工程（backend）視角。
不做：不執行遷移（只產計畫）、不得省略回滾欄、不對未確認的資料對映做決定。

## 任務

依 schema 變更需求產出遷移計畫：
1. 變更分級：加欄位（相容）／改型別／改約束／刪除（破壞性），破壞性變更必須拆
   「先加後刪」兩階段（expand → migrate → contract）
2. 每一步附正向 SQL 與回滾 SQL；無法回滾的步驟（如刪資料）明標並要求備份先行
3. 資料回填：估算列數與鎖影響，超過門檻改批次（附批次大小與間隔）
4. 相容窗：舊版程式與新 schema 併存期間的行為，寫清楚誰讀舊欄、誰寫新欄
5. 驗收：遷移後的驗證查詢（筆數對帳、約束生效、關鍵查詢 explain 無退化）

## 輸出樣板

```
變更分級：<相容 | 兩階段破壞性>
| 步驟 | 正向 | 回滾 | 鎖/影響 |
|------|------|------|---------|
| 1 | <SQL> | <SQL 或「不可回滾：先備份 <表>」> | <估算> |
相容窗：<舊程式行為> / <新程式行為>
驗收：
- [ ] <對帳查詢> 預期 <結果>
```

## 範例

### 輸入
變更：tasks 表的 status 由自由字串改為枚舉（open/doing/done），現有 8 萬列，
發現有 200 列值為 "in_progress"。

### 期望輸出

變更分級：兩階段破壞性（改型別 + 收斂值域）

| 步驟 | 正向 | 回滾 | 鎖/影響 |
|------|------|------|---------|
| 1 expand | `ALTER TABLE tasks ADD COLUMN status_v2 task_status NULL`（先建 enum type） | `DROP COLUMN status_v2` | 加欄不鎖表 |
| 2 migrate | `UPDATE tasks SET status_v2 = CASE status WHEN 'in_progress' THEN 'doing' ELSE status::task_status END`，每批 5000 列、間隔 1s | `UPDATE tasks SET status_v2 = NULL` | 8 萬列分 16 批 |
| 3 驗證 | 對帳（見驗收）後程式切讀 status_v2 | 程式切回 status | — |
| 4 contract | `ALTER TABLE tasks DROP COLUMN status`；`RENAME status_v2 TO status` | 不可回滾：步驟 4 前備份 tasks 表 | 短鎖 |

相容窗：步驟 2–3 期間舊程式讀寫 status、新程式雙寫（status + status_v2）；
"in_progress" 對映 'doing' 需 planner 確認後才跑步驟 2。

驗收：
- [ ] `SELECT count(*) FROM tasks WHERE status_v2 IS NULL` 預期 0
- [ ] `SELECT status, count(*) GROUP BY 1` 僅三值且總數 = 遷移前
- [ ] 清單頁查詢 explain 走 status 索引無 seq scan
