# 規格 ⇄ 設定檔 對照（彌勒佛）

- xlsx：`彌勒佛機率表_v3_1001A版.xlsx`（408fa27462d5b3a1）
- config：`a-standard.json`（e1ff3c8b1e535332）
- map：`config-map.fasttest.yaml`
- 結果：39 條規則｜一致 36｜**不一致 3**｜缺 0

| 規則 | xlsx 選擇器 | config 鍵 | 狀態 | xlsx 值 | config 值 | 備註 |
|---|---|---|---|---|---|---|
| bet_cost | `board.基本收費` | `Bet_Cost` | ✅ | 132 | 132 |  |
| bet_line | `board.線數` | `Bet_Line` | ✅ | 243 | 243 | All Ways → 243 |
| reelset_weight | `reelsets.weight` | `MainGameReelSetWeight` | ✅ | [40, 100, 100, 100, 100, 100, 115, 115, 115, 115] | [40, 100, 100, 100, 100, 100, 115, 115, 115, 115] |  |
| fake_sc_scores | `dual[M-2].0.values` | `FakeSCScores` | ✅ | [8, 18, 38, 68, 88, 188, 388, 688, 888] | [8, 18, 38, 68, 88, 188, 388, 688, 888] |  |
| fake_sc_weights | `dual[M-2].0.weights` | `FakeSCWeights` | ✅ | [18, 16, 14, 12, 10, 8, 8, 8, 6] | [18, 16, 14, 12, 10, 8, 8, 8, 6] |  |
| fake_ss_scores | `dual[M-2].1.values` | `FakeSSScores` | ✅ | [1288, 1888, 2888, 3888, 6888, 8888, -2, -3, -4] | [1288, 1888, 2888, 3888, 6888, 8888, -2, -3, -4] | *2/*3/*4 乘倍在設定檔以負值表示 |
| fake_ss_weights | `dual[M-2].1.weights` | `FakeSSWeights` | ✅ | [18, 16, 14, 12, 10, 8, 8, 8, 6] | [18, 16, 14, 12, 10, 8, 8, 8, 6] |  |
| fg_sc_scores | `dual[M-5].0.values` | `FGEnterSCScores` | ✅ | [8, 18, 38, 68, 88, 188, 388, 688, 888] | [8, 18, 38, 68, 88, 188, 388, 688, 888] |  |
| fg_sc_weights | `dual[M-5].0.weights` | `FGEnterSCWeights` | ✅ | [250, 40, 60, 100, 450, 40, 7, 3, 50] | [250, 40, 60, 100, 450, 40, 7, 3, 50] |  |
| fg_ss_scores | `dual[M-5].1.values` | `FGEnterSSScores` | ✅ | [1288, 1888, 2888, 3888, 6888, 8888, -2, -3, -4] | [1288, 1888, 2888, 3888, 6888, 8888, -2, -3, -4] |  |
| fg_ss_weights | `dual[M-5].1.weights` | `FGEnterSSWeights` | ✅ | [400, 90, 60, 20, 7, 3, 220, 120, 80] | [400, 90, 60, 20, 7, 3, 220, 120, 80] |  |
| fish_announce | `yesno[M-3-1]` | `FishAnnouncementWeights` | ✅ | [[100, 0], [50, 50], [0, 100], [0, 100]] | [[100, 0], [50, 50], [0, 100], [0, 100]] |  |
| fish_all_888 | `yesno[M-3-2]` | `FishAllMaxSCWeights` | ✅ | [[10, 90], [5, 95], [0, 100], [0, 100]] | [[10, 90], [5, 95], [0, 100], [0, 100]] |  |
| rainbow_listen | `weights[M-4].weight` | `RainbowListenWeights` | ✅ | [50, 50] | [50, 50] |  |
| fg_type_weight | `weights[F-1].weight` | `FreeGameTypeWeight` | ✅ | [1, 19, 70, 10] | [1, 19, 70, 10] |  |
| coin_times | `matrix[F-2].金幣・出現次數` | `CoinTimesWeights` | ✅ | [[100, 0, 0, 0, 0, 0], [0, 25, 50, 25, 0, 0], [0, 10, 30,… | [[100, 0, 0, 0, 0, 0], [0, 25, 50, 25, 0, 0], [0, 10, 30,… |  |
| coin_scores | `matrix_head[F-2].金幣・分數` | `CoinScores` | ✅ | [18, 38, 68, 88] | [18, 38, 68, 88] |  |
| coin_score_w | `matrix[F-2].金幣・分數` | `CoinScoreWeights` | ✅ | [[60, 30, 9, 1], [60, 30, 9, 1], [60, 30, 9, 1], [60, 30,… | [[60, 30, 9, 1], [60, 30, 9, 1], [60, 30, 9, 1], [60, 30,… |  |
| fish_times | `matrix[F-2].鯉魚・出現次數` | `FishTimesWeights` | ✅ | [[0, 0, 0, 0, 0, 50, 30, 10, 6, 3, 1], [0, 0, 0, 25, 35, … | [[0, 0, 0, 0, 0, 50, 30, 10, 6, 3, 1], [0, 0, 0, 25, 35, … |  |
| fish_scores | `matrix_head[F-2].鯉魚・分數` | `FishScores` | ✅ | [188, 388, 688, 888] | [188, 388, 688, 888] |  |
| fish_score_w | `matrix[F-2].鯉魚・分數` | `FishScoreWeights` | ✅ | [[0, 0, 0, 100], [60, 30, 9, 1], [60, 30, 9, 1], [60, 30,… | [[0, 0, 0, 100], [60, 30, 9, 1], [60, 30, 9, 1], [60, 30,… |  |
| gold_times | `matrix[F-2].金龍・出現次數` | `GoldDragonTimesWeights` | ✅ | [[0, 0, 0, 0, 0, 5000, 3000, 1000, 500, 300, 100, 50, 30,… | [[0, 0, 0, 0, 0, 5000, 3000, 1000, 500, 300, 100, 50, 30,… |  |
| color_times | `matrix[F-2].彩龍・出現次數` | `ColorDragonTimesWeights` | ✅ | [[0, 0, 0, 0, 0, 0, 5000, 3000, 1000, 500, 300, 100, 50, … | [[0, 0, 0, 0, 0, 0, 5000, 3000, 1000, 500, 300, 100, 50, … |  |
| bag_order_first2 | `series[F-3-1].前兩次抽取` | `BagOrderFirst2Weights` | ✅ | [80, 15, 5, 0] | [80, 15, 5, 0] | xlsx 末欄 Total 不比對 |
| bag_order_after2 | `series[F-3-1].第三次以後` | `BagOrderAfter2Weights` | ✅ | [60, 30, 7, 3] | [60, 30, 7, 3] |  |
| revive_threshold | `scalars[F-4-1]` | `ReviveThreshold` | 🔴 | 300 | 200 | 彌勒佛 v3：xlsx 300 vs config 200 → 待確認 |
| revive_weights | `weights[F-4-2].weight` | `ReviveWeights` | ✅ | [50, 50] | [50, 50] |  |
| revive_gold_keep | `series[F-4-3].保留金龍.權重` | `ReviveGoldDragonKeepWeights` | 🔴 | [0, 0, 45, 40, 10, 5] | [45, 40, 10, 5] | xlsx 以保留條數為索引（自 0 起）；設定檔索引起點待確認 |
| revive_color_keep | `series[F-4-3].保留彩龍.權重` | `ReviveColorDragonKeepWeights` | 🔴 | [0, 45, 40, 10, 5] | [45, 40, 10, 5] |  |
| reel_lens_set0 | `strips[main_strip].Reels_0.lens` | `MainGameReelData.0` | ✅ | [126, 188, 160, 112, 133] | [126, 188, 160, 112, 133] |  |
| reel_lens_set5 | `strips[main_strip].Reels_1.lens` | `MainGameReelData.5` | ✅ | [126, 188, 160, 112, 136] | [126, 188, 160, 112, 136] | 組 5 = R5 換無 SS 帶 |
| odds_M1 | `paytable.M1` | `Odds.11` | ✅ | [20, 60, 250] | [20, 60, 250] |  |
| odds_M2 | `paytable.M2` | `Odds.12` | ✅ | [15, 50, 200] | [15, 50, 200] |  |
| odds_M3 | `paytable.M3` | `Odds.13` | ✅ | [15, 25, 150] | [15, 25, 150] |  |
| odds_M4 | `paytable.M4` | `Odds.14` | ✅ | [10, 20, 100] | [10, 20, 100] |  |
| odds_M5 | `paytable.M5` | `Odds.15` | ✅ | [10, 15, 50] | [10, 15, 50] |  |
| odds_FA | `paytable.FA` | `Odds.21` | ✅ | [5, 8, 10] | [5, 8, 10] |  |
| odds_FK | `paytable.FK` | `Odds.22` | ✅ | [5, 8, 10] | [5, 8, 10] |  |
| odds_FQ | `paytable.FQ` | `Odds.23` | ✅ | [5, 8, 10] | [5, 8, 10] |  |

> 不一致項請回規格或設定檔改，不要只改本報告；改完重跑 ps_extract（xlsx 變了）或直接重跑 ps_diff（config 變了）。
