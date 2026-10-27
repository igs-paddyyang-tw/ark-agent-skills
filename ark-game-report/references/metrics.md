# 指標字典與燈號規則

口徑：日粒度；本機所有子 ID（多館別、多房間）先合併；分母「全虎機」排除魚機等非虎機遊戲。

## 指標

| 代號 | 指標 | 公式 | 資料集 | 出現在 |
|------|------|------|--------|-------|
| S1 | 押量 | Σ bet | game_user_daily | Q1 KPI |
| S2 | 押注佔比 | S1 ÷ slot_bet（同切分、同日）| + slot_daily | Q1 趨勢、燈號 |
| S3 | 排名 | game_rank | slot_daily | Q1 KPI |
| S4 | 遊玩人數 | 不重複 uid（spins > 0）| game_user_daily | Q1 KPI |
| S5 | 試玩率 | 當日 S4 ÷ slot_players | + slot_daily | Q1 KPI、insight |
| R2 | 回訪率 Dn | 首玩日 f 的玩家中，f+n 日有玩的比例；只算 f+n ≤ 資料最後一天的玩家 | game_user_daily | Q3 |
| C | 組成 | 玩家（期末屬性）落在各組的比例；本機 vs slot_users | + slot_users | Q2 |
| D1 | 人均手數 | Σ spins ÷ 人數 | game_user_daily | Q4 |
| D2 | 平均押注 | Σ bet ÷ Σ spins | game_user_daily | Q4 |
| D3 | 深度玩家比例 | 單日 spins ≥ deep_spins 的人日 ÷ 總人日 | game_user_daily | Q4、燈號 |
| P1 | 累計 RTP | Σ win ÷ Σ bet（從上線日累計）| game_user_daily.win | Q5 |
| P2 | 信賴帶 | target ± 1.96·σ／√累計 spins | spec | Q5 |
| P3 | 觸發偏離 | 實際次數 ÷ 期望次數 − 1；期望 ＝ spins ÷ Freq | trig_* 欄位 + spec.triggers | Q5 |
| I1 | 侵蝕率 | Σ（本機玩家在其他機台的押量減少）÷ 本機上線後押量 | erosion | Q6 |
| I2 | 虎機總押量變化 | 上線後窗口 ÷ 上線前窗口 − 1 | erosion.__ALL_SLOTS__ | Q6 |
| H1 | 集中度 | 押量前 1%、前 10% 玩家的佔比 | game_user_daily | 健康 |
| H2 | 高強度比例 | 任一天 spins ≥ intense_spins 的人 ÷ 遊玩人數 | game_user_daily | 健康 |
| H3 | 深夜佔比 | late_buckets 的押量佔比 | hours | 健康 |

## 歷史基準

兩種來源擇一：

- **benchmark.csv**：直接提供分位數，欄位 `metric, day, p30, p50, p60`，可再加 `view` 欄。metric 為以下之一：
  - `share`：day 為第幾天。
  - `trial`：day 為第幾天。
  - `deep`：day 為第幾天。
  - `ret`：day 為回訪天數 n。
- **bench/<遊戲>/**：每款歷史新機一個資料夾，放 `game_user_daily.csv` 與 `slot_daily.csv`。gr_build 會自己算各指標，再取分位數。至少要 3 款，建議 8～12 款。

## 燈號

| 問題 | D+7 | D+14 / D+30 | 規則 |
|------|-----|-------------|------|
| Q1 | 平均佔比 | 最後 7 日平均佔比 | ≥ 基準 P60 綠、≥ P30 黃、其餘紅 |
| Q2 | 第一個組成維度最高組：本機佔比 ÷ 全虎機佔比 | 同左 | `lights.q2_top_group_ratio` |
| Q3 | D1 回訪率 | D7 回訪率 | 分位數 |
| Q4 | 平均深度玩家比例 | 同左 | 分位數（沒有基準就是資料不足）|
| Q5 | RTP 最長連續帶外天數、觸發率異常 | 同左 | ≥ `q5_out_streak` 或有觸發異常 → 紅；曾帶外 → 黃 |
| Q6 | 侵蝕率 | 同左 | `q6_erosion` |
| H | 集中度、高強度比例 | 同左 | 一項超標黃、兩項超標紅 |

缺資料或缺基準時一律「資料不足」，不猜。
