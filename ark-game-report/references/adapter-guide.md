# Adapter 與實戰驗證

## 1. adapter 是什麼

adapter 把「平台的表與欄位」對應到標準資料集（見 data-contract.md）。一個平台一個檔，放在 `assets/adapters/<名稱>.yaml`。
gr_query 依 adapter 產 SQL；gr_probe 會列出還沒確認的欄位。

| 欄位 | 說明 |
|------|------|
| `engine` | 目前支援 `bigquery`（交 ark-db-query 執行）|
| `project`、`dataset`、`tables.game`、`tables.user`、`tables.hours` | 表位置 |
| `columns.date / uid / gid / bet / spins / win / vip / market / reg_date` | 欄位名稱；不確定就寫 `TODO: 說明` |
| `triggers` | 特色名稱 → 觸發次數欄位 |
| `hour_columns` | 時段表的 `bucket`、`bet` 欄位 |
| `gid_format` | report.yaml 的 game.ids 轉成平台 ID 的格式，例如 `Slot_{id}` |
| `slot_filter` | 「全虎機」的 SQL 條件 |

寫 `TODO:` 的欄位影響範圍：

- `uid`、`bet`、`spins` 這些必要欄位是 TODO 時，整個資料集都不會產。
- 選配欄位是 TODO 時，只會少一欄。例如 `win` 是 TODO，就沒有實際 RTP。

## 2. 回填 TODO 欄位

```bash
S=.kiro/skills/ark-db-query/scripts
python $S/bq_schema.py schema --table preprocessed_bklog.DailyUserGameMetrics --brief   # 看欄位
python $S/bq_schema.py preview --table preprocessed_bklog.DailyUserGameMetrics --limit 5
```

確認後改 adapter，再依序跑：

1. `gr_run.py query --dry-run`：看掃描量。
2. `gr_run.py query --run`：撈資料。
3. `gr_run.py probe`：看每節的狀態。

## 3. 實戰驗證清單（第一次在新平台用時）

挑一台已上線滿 30 天的機台，D+7、D+30 各跑一次：

| # | 項目 | 通過條件 |
|---|------|---------|
| V1 | 覆蓋 | probe 的每個 skip、partial 都能說出原因（拿不到，或 adapter 還沒填）|
| V2 | 對帳 | 押量、佔比、排名和現行看板同日數字一致（誤差 < 0.5%）|
| V3 | 子 ID 合併 | 多館別押量有合併；排名沒有重複 |
| V4 | 回訪率 | 抽 3 個首玩世代手算 D1，和報告一致 |
| V5 | RTP | 累計 RTP 和機率人員自算一致；σ 來源有標註 |
| V6 | 基準 | benchmark_games 清單與上線日正確，`--bench` 撈得到 |
| V7 | 燈號 | 拿 2～3 台公認成功與失敗的機台回測，燈號方向一致 |
| V8 | 侵蝕 | 前後窗口等長，避開大型活動；結果能解釋 |
| V9 | 閱讀 | 企劃、機率、營運各一人 5 分鐘內說得出結論與下一步 |
| V10 | 時間 | 從撈資料到出 HTML < 10 分鐘 |

驗證後要做的調整：

- 口徑問題：改 report.yaml 或 adapter。
- 判斷規則：改 `assets/playbook.yaml`。
- 版面：改 `assets/report_template.html`。
- 每次調整都在 SKILL.md 的版本與這份清單記一筆。

## 4. 本公司 BigQuery（bigquery-igs）已知事項

- 主表都設了分區必填：查詢一定要帶 `BQDate` 條件；gr_query 的 SQL 已內建日期區間。
- 資料約在隔日 00:20 到齊，排程建議 01:00 以後。
- 一般館與高分館是不同 GID，report.yaml 的 `game.ids` 要全部列出。
- `CountrySlotGrossRet`、`CountryFishGrossRet` 已停更，不要用。
- 待確認欄位見 adapter 檔的 `TODO:`，包括：
  - uid、bet、spins
  - win
  - market、reg_date
  - 觸發次數、時段表

## 5. 驗證紀錄

### 2026-10-19 吉屋出豬（617／618）D+7、D+30｜bigquery-igs 首次實戰

| # | 結果 | 說明 |
|---|------|------|
| V1 覆蓋 | ✅ | Q5 觸發率、健康觀察時段圖略過：平台查無觸發次數與時段表 |
| V3 子 ID 合併 | ✅ | 一般館 617 ＋ 高分館 618 合併；高分館佔押量 94%、上線早 4 天 |
| V5 RTP | ⚠️ 待確認 | 實際 RTP 90.57%（含 JP 90.78%）與同期新機 86～94% 一致；知識庫 V12 A 版快測 99.98% 不是線上版本 → Q5 改「資料不足」，待機率人員提供線上設定檔與目標 RTP |
| V6 基準 | ✅ | 2026 年上線、滿 30 日的同期新機 12 款（NewSlotOnlineDate 查上線日；同名新舊機 ID 不同） |
| V7 燈號 | ⚠️ 要校準 | 健康觀察「前 1% 玩家押量佔比 ≥ 40%」在本平台幾乎每台都觸發（同期 54～77%）→ 建議改同期分位數 |
| V10 時間 | ❌ | 撈資料約 40 分鐘（bq_export 偶發卡住、基準逐一排隊）；0.1.1 已加逾時與重試，平行化待做 |

調整：adapter 回填、`slot_users` 快照取法、匯出逾時重試、P50 窗口（見 SKILL.md 0.1.1）。
