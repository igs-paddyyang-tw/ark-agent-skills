---
title: "機率規格書：Tiger and Dragon — Multiplier"
contract: "1"
kind: prob-spec
slug: tiger-and-dragon
game: "Tiger and Dragon — Multiplier"
mode: qt
odds_version: "1.0.0"
status: review
distribution: internal
date: 2026-10-13
author: paddyyang
source_skill: ark-game-prob
verdict: inconclusive
pending_params: 7
sources:
  qt-config: ../quicktest/qt-config.yaml
  odds: ../quicktest/odds/odds_1.0.0.json
  quicktest: ../quicktest/quicktest.yaml
  rtp-report: ../quicktest/qt-report/rtp-report.json
---

# 機率規格書：Tiger and Dragon — Multiplier

> 依機率規格書公版「製作方針」六段組成；**SPEC** = 規格書、**DECIDED** = 決議、**FROM_KB** = 知識庫、待決議 = 未決議（null）。人工填寫區可直接編輯，重產保留。
## 1. 規格簡述

- **UNKNOWN** 無 gdd-pack（qt-config.sources.gdd 未指定）；規格簡述待補。

### 機率人員簡述（競品分析模式）

<!-- human:summary -->
**定位**：IGT《Tiger and Dragon — Multiplier》競品反解。5×3 / 243 Ways，基礎押注 75 credits。
規則來源為公開影片 A（RandomSlots，Barona 2024-10）的 INFO 七頁 + 實機畫面，完整規則見
`docs/TigerAndDragon_規格書.md`（本機率規格書的規則母本）。

**三大特色**：
1. **倍數 WILD（主遊戲張力來源）**：神秘銅鑼只落第 2～5 軸，每手轉完全部變成 x2～x10 倍數 WILD；
   同一 Way 多顆 WILD 倍數**相加**（非連乘）。賠率表扁平（一般圖騰 3 連全是 15），主遊戲靠倍數 WILD 拉分。
2. **金幣鎖格 Bonus（三選一）**：Tiger（3 次重置）／Dragon（1 次）／Tiger & Dragon（5×8 解鎖列）。
   Bonus 中只出金幣、落下即鎖；結束時橫向相鄰 ≥2 顆成組，每顆翻 1～99 或箭頭，**由左至右連讀成一個數**＝該組贏分
   —— 組越長贏分是數量級跳升，是本作辨識度最高的結算機制。
3. **解鎖列＋彩金共用計數**：Tiger & Dragon Bonus 用同一累計金幣數推進 6 個門檻（6/9/14/19/25 列解鎖、32 顆得 JACKPOT）。

**與競品／設計差異（待我方定案）**：玩法概念（金幣鎖格、數字串接、倍數 WILD）可自由使用；
原廠美術、「Tiger and Dragon」名稱與 IGT MultiWay 商標須迴避（見規格書§十一）。

**本規格書數值狀態**：線賠 odds 為原廠 PAYS 頁觀察值（標 competitor_reference，75 credits 基準），
**非我方 Par Sheet 定案**；所有機率參數（觸發率、輪帶、權重、停入率、JACKPOT、MaxWin）原廠不公開，
一律待決議（P-002）。數值設計與 RTP 平衡待機率設計與快測（ark-game-quicktest C2 段）後回填。
<!-- /human -->

## 2. 數據資料

### 快測摘要

> 一表看完：總覽 KPI 與 RTP 組成圖由本表產生；值與下方各表相同來源。

| 指標 | 值 | 來源 |
|---|---|---|
| 總 RTP | 96.4852% | rtp-report.json |
| 主遊戲 RTP | 70.2929% | rtp-report.json |
| 免費遊戲 RTP | 26.1923% | rtp-report.json |
| 主遊戲命中率 | 24.58% | rtp-report.json |
| 主遊戲最大倍數 | 592.2 | rtp-report.json |
| FG 觸發率 | 0.1241% | rtp-report.json |
| FG 平均觸發局數 | 805.87 | rtp-report.json |
| FG 平均倍率 | 211.08 | rtp-report.json |
| FG 最大倍數 | 20,000 | rtp-report.json |
| 總手數 | 20,000,000 | rtp-report.json |
| 執行時間 | 2026-10-13 10:12 | rtp-report.json |
| 引擎版本 | 1.0.0 | rtp-report.json |
| 目標 RTP | 96% | quicktest.yaml |
| 容許誤差 | 1 pp | quicktest.yaml |
| 誤差 | +0.485 pp | 計算 |
| 三向 verdict | inconclusive | rtp-report.gate |

> 來源：`qt-report/rtp-report.json`（快測版本 1.0.0，20,000,000 手，2026-10-13 10:12:37.7997）；P-003 三向 verdict：**inconclusive**。

| 階段 | RTP | Hit % | 觸發率 | 平均觸發局數 | 平均倍率 | 最大倍率 | 平均局數 |
|---|---|---|---|---|---|---|---|
| MainGame | 70.29% | 24.58% | — | — | 2.86 | 592.2 | — |
| SpecialGameTotal | 26.19% | — | 0.12% | 805.87 | 211.08 | 20,000 | 6.67 |
| Ultra | 20.70% | — | 0.06% | 1,660.58 | 343.79 | 20,000 | 11.63 |
| Strong | 0.03% | — | 0.06% | 1,655.77 | 0.54 | 631.24 | 1 |
| Normal | 5.46% | — | 0.00% | 28,776.98 | 1,570.27 | 20,000 | 19.11 |
| Total | 96.49% | — | — | — | — | 20,000 | — |

- rtp：模擬 96.4852% vs 目標 96.00%（差 +0.4852%，容許 ±1.0%） [PASS]
- feel:SpecialGameTotal：SpecialGameTotal 觸發 1/805.9（0.12%）落在自訂區間 1/500~1/1250 [PASS]
- null：未提供 config-spec.yaml [SKIP]
- ⚠ 範本審查 F-5（SpecialGameTotal）：RetriRate 0.00% 為範本未記錄 retrigger 次數所致，不代表沒有 retrigger；改看 PlayTimes 是否大於初始手數
- ⚠ 範本審查 F-7（0 < x < 1）：Multiple Information 第一列「0倍以上」累計漏算 0<x<1 區間，數值等同「1倍以上」，實際應更小
- ⚠ 範本審查 F-2（maxwin統計）：maxwin 頻率被高估：範本在同一場 FG 截頂後每手都計次，且主遊戲不封頂；請以 FG 觸發頻率為上限解讀
- SD 43.83；P.I. 2.1；Pay Out Rate 90.70%

### 主遊戲符號命中率

| 符號 | x2 | x3 | x4 | x5 | TOTAL |
|---|---|---|---|---|---|
| 11 | 0% | 1.26% | 0.35% | 0.19% | 1.8% |
| 12 | 0% | 3.2% | 0.87% | 0.26% | 4.33% |
| 13 | 0% | 2.6% | 0.94% | 0.27% | 3.81% |
| 14 | 0% | 2.06% | 0.68% | 0.63% | 3.36% |
| 15 | 0% | 1.59% | 0.7% | 0.28% | 2.58% |
| 16 | 0% | 1.34% | 0.48% | 0.16% | 1.99% |
| 21 | 0% | 1.38% | 0.35% | 0.2% | 1.94% |
| 22 | 0% | 1.49% | 0.44% | 0.16% | 2.1% |
| 23 | 0% | 2.24% | 0.83% | 0.41% | 3.47% |
| 24 | 0% | 1.64% | 0.48% | 0.18% | 2.3% |
| TOTAL | 0% | 18.79% | 6.12% | 2.75% | 27.66% |

### 主遊戲符號 RTP 貢獻

| 符號 | x2 | x3 | x4 | x5 | TOTAL |
|---|---|---|---|---|---|
| 11 | 0% | 1% | 1.72% | 2.52% | 5.24% |
| 12 | 0% | 2.45% | 4.22% | 3.87% | 10.53% |
| 13 | 0% | 1.96% | 3.09% | 3.62% | 8.67% |
| 14 | 0% | 1.85% | 2.52% | 7.68% | 12.04% |
| 15 | 0% | 1.53% | 2.07% | 3.86% | 7.47% |
| 16 | 0% | 1.32% | 1.38% | 2.08% | 4.78% |
| 21 | 0% | 1.39% | 1.06% | 2.09% | 4.54% |
| 22 | 0% | 1.3% | 1.43% | 2.04% | 4.76% |
| 23 | 0% | 1.7% | 1.93% | 3.59% | 7.21% |
| 24 | 0% | 1.59% | 1.39% | 2.06% | 5.04% |
| TOTAL | 0% | 16.08% | 20.81% | 33.4% | 70.29% |

### 輪帶組 RTP（實測）

| 組 | 實測 Total RTP |
|---|---|
| 0 | 96.4852% |

### 贏分區間分布

| 贏分區間（倍） | 出現 Total | 出現 Main | 出現 Free | RTP Total | RTP Main | RTP Free |
|---|---|---|---|---|---|---|
| x = 0 | 75.36% | 75.42% | 42.59% | 0% | 0% | 0% |
| 0 < x < 1 | 14.18% | 14.16% | 21.33% | 4.99% | 4.99% | 0.01% |
| 1 <= x < 5 | 7.24% | 7.23% | 10.29% | 15.94% | 15.91% | 0.03% |
| 5 <= x < 10 | 1.53% | 1.53% | 2.99% | 10.93% | 10.9% | 0.03% |
| 10 <= x < 25 | 1.21% | 1.21% | 3.69% | 18.35% | 18.27% | 0.08% |
| 25 <= x < 50 | 0.34% | 0.34% | 2.95% | 11.43% | 11.29% | 0.13% |
| 50 <= x < 75 | 0.07% | 0.07% | 1.08% | 4.46% | 4.37% | 0.08% |
| 75 <= x < 100 | 0.02% | 0.02% | 0.37% | 2.04% | 2% | 0.04% |
| 100 <= x < 150 | 0.01% | 0.01% | 0.64% | 1.66% | 1.56% | 0.11% |
| 150 <= x < 200 | 0.01% | 0% | 2.94% | 1.16% | 0.54% | 0.62% |
| 200 <= x < 300 | 0% | 0% | 1.93% | 0.95% | 0.32% | 0.63% |
| 300 <= x < 500 | 0% | 0% | 3.22% | 1.69% | 0.13% | 1.56% |
| 500 <= x < 800 | 0% | 0% | 1.84% | 1.45% | 0.02% | 1.42% |
| 800 <= x < 1000 | 0% | 0% | 0.56% | 0.61% | 0% | 0.61% |
| 1000 <= x < 2000 | 0% | 0% | 1.03% | 1.87% | 0% | 1.87% |
| 2000 <= x < 5000 | 0% | 0% | 1.55% | 6.3% | 0% | 6.3% |
| 5000 <= x < 10000 | 0% | 0% | 0.58% | 4.87% | 0% | 4.87% |
| 10000 <= x < 20000 | 0% | 0% | 0.26% | 3.89% | 0% | 4.19% |
| 20000 <= x < 50000 | 0% | 0% | 0.15% | 3.9% | 0% | 3.6% |
| 50000 <= x < -1 | 0% | 0% | 0% | 0% | 0% | 0% |

### 倍數出現頻率

| 贏分區間（倍） | 約每幾局 | 累計門檻 | 累計約每幾局 |
|---|---|---|---|
| 0 < x < 1 | 7.05 | ≥ 0 | 9.56 |
| 1 <= x < 5 | 13.81 | ≥ 1 | 9.56 |
| 5 <= x < 10 | 65.27 | ≥ 5 | 31.04 |
| 10 <= x < 25 | 82.45 | ≥ 10 | 59.19 |
| 25 <= x < 50 | 292.8 | ≥ 25 | 209.79 |
| 50 <= x < 75 | 1336.63 | ≥ 50 | 739.95 |
| 75 <= x < 100 | 4174.49 | ≥ 75 | 1657.55 |
| 100 <= x < 150 | 7176.18 | ≥ 100 | 2749.14 |
| 150 <= x < 200 | 14598.54 | ≥ 150 | 4456.33 |
| 200 <= x < 300 | 26385.22 | ≥ 200 | 6414.37 |
| 300 <= x < 500 | 22909.51 | ≥ 300 | 8474.58 |
| 500 <= x < 800 | 43103.45 | ≥ 500 | 13449.9 |
| 800 <= x < 1000 | 144927.54 | ≥ 800 | 19550.34 |
| 1000 <= x < 2000 | 78,125 | ≥ 1000 | 22598.87 |
| 2000 <= x < 5000 | 52083.33 | ≥ 2000 | 31796.5 |
| 5000 <= x < 10000 | 137931.03 | ≥ 5000 | 81632.65 |
| 10000 <= x < 20000 | 327868.85 | ≥ 10000 | 200,000 |
| 20000 <= x < 50000 | 512820.51 | ≥ 20000 | 512820.51 |
| 50000 <= x < -1 | — | ≥ 50000 | — |

### 100 手資產分布

| 100 手後剩餘資產 | 佔比 |
|---|---|
| x <= 50 | 34.01% |
| 50 < x <= 100 | 46.48% |
| 100 < x <= 200 | 16.61% |
| 200 < x | 2.9% |

### 十分位

| 分位 | Total | Main | Free | F_Spin |
|---|---|---|---|---|
| D1 | 0 | 0.2 | 0 | 1 |
| D2 | 0 | 0.2 | 0 | 1 |
| D3 | 0 | 0.2 | 0 | 1 |
| D4 | 0 | 0.4 | 0 | 1 |
| D5 | 0 | 0.6 | 0.1 | 3 |
| D6 | 0 | 1 | 0.5 | 7 |
| D7 | 0 | 1.6 | 2.9 | 10 |
| D8 | 0.2 | 3 | 19.1 | 13 |
| D9 | 1 | 7 | 283.7 | 16 |
| Maximum | 20,000 | 592.2 | 20,000 | 57 |
| Mean | 1 | 2.9 | 211.1 | 6.7 |
| S.D. | 43.8 | — | 1,221 | — |

- 目標 RTP：96.00%（容許 ±1.00%）；來源 quicktest.yaml。**RTP 是模擬結果不是輸入**（P-000）。

## 3. 機率流程圖

- **UNKNOWN** 無 dev-spec/state-machine.md；流程圖待補（`gs_run --stage dev` 產）。

<!-- human:flow-notes -->
### ✅ C2 已自行客製引擎並完成快測（2026-10-12，娜娜）

原本範本（3×3 線型 + 標準 Free Spin）不支援本款，已**自行客製 Go 快測引擎**完成四層改造，
引擎在 `data/slot/tiger-and-dragon/quicktest/engine/`（`engine.customized: true`）：

| 層 | 客製內容 | 檔案 |
|---|---|---|
| 1 | 盤面 5×3 | game/game_process.go（ReelAmount 5） |
| 2 | 243 Ways + 倍數 WILD（銅鑼變身、多顆倍數相加、逐 Way 列舉） | check/check.go、checkways/checkways.go |
| 3 | 基礎押注 75 | odds/odds_1.0.0.go（ConstBetCost 75） |
| 4 | 金幣鎖格 Bonus（落子鎖定／相鄰成組／翻值 1-99 箭頭／連讀成數／解鎖列 6-9-14-19-25／32 顆 JACKPOT／MaxWin 封頂） | game/game_process.go（freeGameProcess 重寫）、odds TigerDragonConfig |

**計分正確性**（go test 驗）：倍數 WILD 範例 15×7=105（規格書 A 0:42 ×100/75=140 ✓）；純 3 連 15（A 0:36 ×100/75=20 ✓）。

**快測結果（2000 萬手，high 信心）：**

| 階段 | RTP | 中獎率/觸發率 | 平均倍率 | 來源 |
|---|---|---|---|---|
| Main Game | 70.47% | 中獎率 24.59% | 2.87 | 我方快測 2026-10-12 |
| Special Game（三 Bonus） | 26.26% | 觸發 1/797 | 209.4 | 我方快測 2026-10-12 |
| **Total** | **96.73%** | — | — | 我方快測 2026-10-12 |

maxwin 約 62.5 萬手觸發一次。verdict：對目標 RTP 96%（±1%）**在容許範圍內**（96.73%）。

> 數值為我方快測調校的**設計決議值**（D-TD-xx，非競品觀察、非原廠 Par Sheet）。
> 完整報告 `quicktest/engine/report_1.0.0.txt`；輪帶/參數在 `quicktest/odds/odds_1.0.0.json`。
> 工程交接 `docs/reports/handoff/2026-10-12-tiger-and-dragon-engine-gap.md`（已標已實作）。

### verdict = inconclusive 的意思（非失敗）

P-003 三向：**rtp PASS**（96.49% vs 目標 96%，差 +0.49% 在 ±1%）、**feel PASS**（Bonus 觸發 1/806 落在設計區間）、
**null SKIP**（本款走 ark-game-prob qt 設計局，無 ark-game-spec 的 config-spec.yaml，第三向無從檢查）。
→ 兩個實質向都通過，僅因缺 config-spec 使 verdict 最高只能到 inconclusive（有 SKIP）。**RTP 與體感已達標**。
要升到 confirmed 需補 config-spec（屬 ark-game-spec gs_dev 產物；設計局款可視需要補）。

### §2 分型列（Ultra/Strong/Normal）是範本統計殘留，勿誤讀

本款金幣鎖格 Bonus **不使用**範本的「超強/強/中/弱」四型 FG 機制（`free_game_type_weight` 僅佔位 [0,0,1,0]）。
§2 的 Ultra/Strong/Normal 列是範本 recorder 把三個 Bonus（Tiger/Dragon/Tiger&Dragon）記進那些統計格造成的，
**不對應本款的三個 Bonus**。看 Bonus 整體請以 **SpecialGameTotal 列**為準（RTP 26.19%、觸發 1/806）。
（同範本審查 F-1 類：分型統計未對應實際玩法。）
<!-- /human -->

## 4. 參數表

> 值來自 `odds/odds_1.0.0.json`；來源欄為 qt-config.yaml.provenance（D-id = 決議、gdd.symbols = 規格書、template = 範本示範值、competitor_reference = 競品觀察）。**待決議** = null，依 P-002 未決議不得帶值。

### 基本資訊

| 項目 | 值 | 來源 |
|---|---|---|
| 盤面（軸 × 列） | 5 × 3 | competitor_reference(規格書§一·5軸×3列·A 0:26) |

### Odds 表（k-of-a-kind 單線賠付）

| 符號 | sym_id | 名稱 | 組 | x1 | x2 | x3 | x4 | x5 | 來源 |
|---|---|---|---|---|---|---|---|---|---|
| M1 | 11 | 貔貅龜 | normal | 0 | 0 | 15 | 60 | 120 | competitor_reference(規格書§二·貔貅龜·INFO PAYS A 5:16) |
| M2 | 12 | 錦鯉 | normal | 0 | 0 | 15 | 60 | 120 | competitor_reference(規格書§二·錦鯉·INFO PAYS A 5:16) |
| M3 | 13 | 銅錢 | normal | 0 | 0 | 15 | 45 | 105 | competitor_reference(規格書§二·銅錢·INFO PAYS A 5:16) |
| M4 | 14 | 聚寶盆 | normal | 0 | 0 | 15 | 45 | 105 | competitor_reference(規格書§二·聚寶盆·INFO PAYS A 5:16) |
| M5 | 15 | 寶石玉珮 | normal | 0 | 0 | 15 | 30 | 90 | competitor_reference(規格書§二·寶石玉珮·INFO PAYS A 5:16) |
| M6 | 16 | 摺扇 | normal | 0 | 0 | 15 | 30 | 90 | competitor_reference(規格書§二·摺扇·INFO PAYS A 5:16) |
| A | 21 | A | normal | 0 | 0 | 15 | 30 | 75 | competitor_reference(規格書§二·A·INFO PAYS A 5:16) |
| K | 22 | K | normal | 0 | 0 | 15 | 30 | 75 | competitor_reference(規格書§二·K·INFO PAYS A 5:16) |
| Q | 23 | Q | normal | 0 | 0 | 15 | 30 | 75 | competitor_reference(規格書§二·Q·INFO PAYS A 5:16) |
| J | 24 | J | normal | 0 | 0 | 15 | 30 | 75 | competitor_reference(規格書§二·J·INFO PAYS A 5:16) |
| WILD | 1 | 倍數 WILD（x2～x10） | special | 待決議 | 待決議 | 待決議 | 待決議 | 待決議 | — |
| SC_T | 2 | 虎（Tiger 觸發） | special | 待決議 | 待決議 | 待決議 | 待決議 | 待決議 | — |
| SC_D | 3 | 龍（Dragon 觸發） | special | 待決議 | 待決議 | 待決議 | 待決議 | 待決議 | — |
| MY | 4 | 神秘銅鑼（轉後變 WILD） | special | 待決議 | 待決議 | 待決議 | 待決議 | 待決議 | — |
| COIN | 7 | 金幣（Bonus 唯一圖騰） | fg | 待決議 | 待決議 | 待決議 | 待決議 | 待決議 | — |
| ARROW | 8 | 藍箭頭（結算揭曉） | fg | 待決議 | 待決議 | 待決議 | 待決議 | 待決議 | — |

### 觸發與上限參數

| 參數 | 值 | 來源 |
|---|---|---|
| 額外押注倍率（Extra Bet） | 6 | D-TD-01(隨機觸發基準·萬分率/顆·快測調校) |
| 進免費遊戲門檻（Scatter 顆數） | 3 顆 | D-TD-02(虎或龍≥3觸發·規格書§三-3) |
| 免費遊戲手數 | 3 手 | D-TD-03(Bonus初始spin·規格書Tiger/TD=3) |
| 免費遊戲 retrigger 門檻 | 99 顆 | D-TD-04(金幣鎖格不走SC-retrigger·設99停用) |
| retrigger 加手數 | 0 手 | D-TD-05(同上·0) |
| 最大贏分倍數（MaxWin） | 20000 倍 | D-TD-06(單Bonus封頂·我方慣例) |
| 道具卡 | 0 0/1 | default(0) |
| Jackpot 基底倍數（MINI→GRAND） | 2500 | D-TD-07(範本JP欄位·金幣鎖格JP走tiger_dragon.jackpot_multiple_td) |
| Jackpot 累積率 | 0 | D-TD-08(固定JP不累積·0) |

### 輪帶組與權重（K-022 輪帶組權重混合）

**主遊戲**

| 組合 | R1 用組 | R2 用組 | R3 用組 | R4 用組 | R5 用組 | 權重 | 來源 |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 1 | 1 | 1 | 1 | 1 | D-TD-10(單一輪帶組·快測調校) |

**免費遊戲（權重欄 = 超強/強/中/弱 四型）**

| 組合 | R1 用組 | R2 用組 | R3 用組 | R4 用組 | R5 用組 | 權重 | 來源 |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 0 | 1/1/1/1 | D-TD-14(同上·佔位) |

- 免費遊戲四型權重（超強/強/中/弱）：0, 0, 1, 0；來源 D-TD-12(金幣鎖格Bonus不走範本強中弱FG·佔位[0,0,1,0])

### 輪帶符號顆數（Strip 統計；完整輪帶見 odds.json）

**主遊戲**

| 組 | 軸 | 長度 | M1 | M2 | M3 | M4 | M5 | M6 | A | K | Q | J | WILD | SC_T | SC_D | MY | COIN | ARROW |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | R1 | 160 | 13 | 20 | 14 | 21 | 15 | 15 | 17 | 11 | 15 | 15 | 0 | 2 | 2 | 0 | 0 | 0 |
| 0 | R2 | 160 | 18 | 18 | 16 | 15 | 19 | 14 | 9 | 10 | 20 | 17 | 0 | 2 | 2 | 0 | 0 | 0 |
| 0 | R3 | 160 | 15 | 11 | 15 | 17 | 14 | 14 | 21 | 20 | 14 | 15 | 0 | 2 | 2 | 0 | 0 | 0 |
| 0 | R4 | 160 | 13 | 19 | 14 | 13 | 21 | 10 | 15 | 18 | 11 | 22 | 0 | 2 | 2 | 0 | 0 | 0 |
| 0 | R5 | 160 | 13 | 16 | 13 | 15 | 23 | 15 | 14 | 19 | 11 | 17 | 0 | 2 | 2 | 0 | 0 | 0 |
| 1 | R1 | 160 | 16 | 15 | 14 | 12 | 17 | 16 | 20 | 11 | 13 | 18 | 0 | 2 | 2 | 4 | 0 | 0 |
| 1 | R2 | 160 | 13 | 16 | 19 | 17 | 15 | 13 | 13 | 18 | 15 | 13 | 0 | 2 | 2 | 4 | 0 | 0 |
| 1 | R3 | 160 | 9 | 17 | 21 | 12 | 18 | 13 | 10 | 15 | 20 | 17 | 0 | 2 | 2 | 4 | 0 | 0 |
| 1 | R4 | 160 | 15 | 11 | 13 | 18 | 20 | 15 | 13 | 17 | 18 | 12 | 0 | 2 | 2 | 4 | 0 | 0 |
| 1 | R5 | 160 | 17 | 10 | 11 | 27 | 14 | 11 | 18 | 13 | 17 | 14 | 0 | 2 | 2 | 4 | 0 | 0 |

- 免費遊戲：待決議（free_game_reel_data 為 null）

### 客製玩法參數（範本 schema 以外）

> 本款玩法超出範本固定欄位，以下為 odds.json `extra_odds` 的客製機率參數（generic 渲染）。

**tiger_dragon**

| 參數 | 值 |
|---|---|
| bonus_reels | 5, 5, 5 |
| bonus_rows | 3, 8, 8 |
| bonus_spins | 3, 1, 3 |
| bonus_reset | 1, 0, 1 |
| coin_rate | 700, 1090, 655 |
| flip_arrow_weight | 15 |
| flip_two_weight | 25 |
| flip_one_weight | 960 |
| flip_one_dist | 500, 250, 130, 60, 30, 15, 8, 4, 3 |
| flip_two_min | 10 |
| flip_two_max | 99 |
| flip_arrow_add_min | 1 |
| flip_arrow_add_max | 40 |
| unlock_thresholds | 6, 9, 14, 19, 25 |
| jackpot_threshold | 32 |
| jackpot_multiple_td | 1200 |

- 來源：D-TD-11(金幣鎖格Bonus全套·coin_rate/翻值分布/解鎖門檻/JP·快測調校RTP 96.73%)

<!-- human:param-notes -->
**待決議參數的設計起點（參考值，非定案）**

下列數字**全部來自規格書〈附錄 E〉的試玩假設值**（來源：`docs/TigerAndDragon_規格書.md` 附錄 E，
標明「試玩用假設值、原廠 Par Sheet 不公開」），僅供機率設計起手參考，**未經決議、不得填入上方參數欄**（P-002）：

- 押注選項：75（基準）/150/300/500/750/1500/3000；賠率＝odds × way 倍數 × 押注 ÷ 75。
- 銅鑼：第 2～5 軸各約 2 顆/60 格；倍數 x2～x10 權重假設 46/24/11/7/4/3/2/1/1。
- 虎、龍：每軸各約 2 顆/60 格；同視窗最多一顆 T/D/銅鑼。
- 隨機觸發（MYSTERY）：1～2 虎 → 0.2%/1.2%；龍同；虎龍並存 → 0.4% 龍虎。
- 停入率（假設）：Tiger 7.2%、Dragon 34%（僅 1 手）、Tiger&Dragon 8.5%（每未鎖空格每手）。
- 翻開分布（假設）：箭頭 2.5%、兩位數 1.5%、其餘一位數 1～9（小數字多）。
- JACKPOT：試玩用固定 2,500 × 押注（原廠為累積彩金）；MaxWin：試玩封頂 10,000 × 押注。
- 試玩模擬總 RTP ≈ 96.1%（主 59.1%／Tiger 16.6%／Dragon 9.6%／Tiger&Dragon 7.4%／JP 3.4%）。

**需機率設計 + 快測決議的關鍵項**：① 目標 RTP ② 三個 Bonus 的觸發率與停入率
③ 倍數 WILD 權重分布 ④ Bonus 金幣翻開值（1~99/箭頭）分布與位數上限 ⑤ 解鎖列與 JACKPOT 的實際命中率
⑥ 主遊戲與 Bonus 輪帶帶（reel strips）。這些決議後回填 odds.json，`verdict` 由快測（ark-game-quicktest）判定。

> 🔴 **決議前提**：上述參數的快測驗證需引擎先客製（範本不支援金幣鎖格 Bonus）——
> 見 §3 flow-notes 與 `docs/reports/handoff/2026-10-12-tiger-and-dragon-engine-gap.md`。引擎好之前先不決議（避免決了也驗不了）。
<!-- /human -->

## 5. 競品資料／手法對應

- **UNKNOWN** 無 run 的 kb-refs.yaml / game-analysis.yaml；手法對應待補。

<!-- human:competitor -->
（選用：競品收錄目的、參考機台與差異）
<!-- /human -->

## 6. 隱性規則

> 更改需與編導規格書同步；每條須有設計目的（公版製作方針 §4）。

| 編號 | 情況（topic） | 說明（值） | 設計目的 | 來源 |
|---|---|---|---|---|
| — | — | — | — | 尚無已定案決議（defer 0 筆） |

<!-- human:hidden-rules -->
以下隱性規則萃取自規格書〈§十 工程注意事項〉與〈§四 共通結算〉（來源：`docs/TigerAndDragon_規格書.md`），
數字為規則定義值（非機率參數決議，須與編導規格書同步）：

- **銅鑼軸限制**：神秘銅鑼只能落在第二至第五軸（第一軸不出）；先完成所有銅鑼→WILD 變身，再結算 Ways（順序不可反）。來源：規格書§三-2 / INFO MULTIPLIER FEATURE。
- **多 WILD 倍數相加**：同一 Way 內多顆倍數 WILD 時，倍數取總和而非連乘。來源：規格書§三-2 / INFO。
- **虎、龍不參與連線**：虎、龍為觸發用 scatter，不連線、不被 WILD 替代。來源：規格書§二 / INFO。
- **Bonus 結算字串串接**：金幣翻開值由左至右連讀成一個數；箭頭先變 0 再加到該組最左位，順序不可反；箭頭不可出現在組的最左邊。來源：規格書§四-0 / INFO Bonus Rules。
- **成組門檻**：Bonus 結算時橫向相鄰 2 顆以上才成組給分，落單金幣（推測）不給分（待逐幀確認，見規格書附錄 B#7）。
- **解鎖列計數只算已解鎖列**：Tiger & Dragon Bonus 的累計金幣數只計已解鎖列；鎖住列出現的金幣不計入（推測，A 1:22）；達標那一手該列當下解鎖並保持到結束。
- **寶箱純裝飾**：上方紅、綠寶箱的金幣數量不影響遊戲，不可做持久化或 RTP 分配。來源：規格書§三-4 / INFO RULES。
- **斷線重連需還原**：剩餘旋轉次數、已鎖金幣位置、已解鎖列、累計金幣數。來源：規格書§十。

> ⚠️ 上述含數字條目會觸發 ps_lint PS-HUMAN（warn）——這是「人工區數字須標來源」的提醒，非錯誤；
> 數字均為規則定義值且已標規格書出處，可回溯。
<!-- /human -->

## 輪帶 Strip（附錄）

> 來源：`odds/odds_1.0.0.json`（sym_id → 符號 code 依 qt-config.structure.symbols）；顆數由帶面逐格計數，帶面每軸一行、由上而下。

### 主遊戲 組 0

| 組 | 軸 | 長度 | M1 | M2 | M3 | M4 | M5 | M6 | SC_D | SC_T | A | J | K | Q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 主遊戲 組 0 | R1 | 160 | 13 | 20 | 14 | 21 | 15 | 15 | 2 | 2 | 17 | 15 | 11 | 15 |
| 主遊戲 組 0 | R2 | 160 | 18 | 18 | 16 | 15 | 19 | 14 | 2 | 2 | 9 | 17 | 10 | 20 |
| 主遊戲 組 0 | R3 | 160 | 15 | 11 | 15 | 17 | 14 | 14 | 2 | 2 | 21 | 15 | 20 | 14 |
| 主遊戲 組 0 | R4 | 160 | 13 | 19 | 14 | 13 | 21 | 10 | 2 | 2 | 15 | 22 | 18 | 11 |
| 主遊戲 組 0 | R5 | 160 | 13 | 16 | 13 | 15 | 23 | 15 | 2 | 2 | 14 | 17 | 19 | 11 |

```strip
# 主遊戲 組 0
R1: J A M4 M2 SC_D M4 M6 M6 A A Q Q M4 A K J A M4 K K A M1 A M6 M3 M3 M6 M5 M6 M2 M5 M2 M1 M2 Q M4 M2 M3 M4 M4 M4 Q M2 M6 M1 M3 K Q M2 Q M3 M5 Q M4 M5 A J M2 M4 M5 M1 J M1 M3 M6 M4 M1 M5 M5 Q M2 M3 M3 Q M6 M4 M4 M6 A A Q M3 J J M1 K SC_T M6 M4 M3 A M2 Q J J J M4 Q M4 M1 A M2 M6 M4 M1 K SC_D K M2 M5 M5 M4 M6 K M2 M5 M3 M5 M3 M2 M5 M4 A M2 A SC_T M3 M1 K M5 A M2 J M2 M2 Q Q M2 M3 Q M4 M5 J A M1 K M4 M1 M6 M2 K J J J M6 M5 J M1 A M6
R2: M4 M4 M2 M4 K M2 M1 A J Q K M1 M5 M4 J Q M6 A J M5 M1 M3 M1 A Q M1 J J M3 M3 SC_T M1 M1 M5 M2 M4 M5 M2 K Q M3 M4 M5 M4 SC_T Q M6 M1 M6 J J A M3 Q M2 Q M6 M5 A A M3 J Q Q M6 M3 K Q M5 M6 J M4 Q M1 M1 M6 J M5 M6 M3 A M3 M3 Q M1 Q J K M1 M1 M5 M4 M2 SC_D Q M6 M1 M2 M6 M4 M6 M3 M5 Q M5 M3 M6 M5 M2 M2 M5 K SC_D M5 M5 M2 Q Q M1 K Q J K M6 K M4 M5 M6 J M2 K Q M3 J M2 M5 M2 M5 M3 M2 M4 M4 M2 J M1 M2 M4 A M1 M3 M3 J M1 J A M4 M5 M2 M2 Q
R3: M3 A M2 M3 M3 M4 M2 M4 M2 M6 M6 Q M4 SC_D M4 M4 K M6 A A Q J M1 M3 M2 M3 M5 M1 M4 M2 J M5 M2 J J A M6 J M1 M5 A M4 K M5 A M5 K M3 M5 M6 J M1 J K K K M3 M1 A K M1 A Q K M2 M5 Q J J M1 M1 M3 A M6 M1 K Q K M4 M3 Q Q M1 A M1 A M1 M6 SC_D A M1 M2 K M4 M2 M4 Q M5 K A A A M5 Q M5 Q M4 M3 SC_T Q M6 K M6 K K M5 M6 K M3 M5 A M4 K J M4 M4 J M3 J K K Q A M2 M6 J M2 M6 A M6 M4 M1 M6 M5 M4 J SC_T M1 Q Q A M5 A M4 M3 M3 M3 K J A
R4: M3 M5 M2 J SC_D M5 M2 M4 M5 K M4 M4 J K A A M4 M1 J J M2 M5 A K A M5 J K M6 M5 K M5 M6 M5 M1 M4 A A M5 M3 A M3 Q Q M1 K M5 K Q Q A Q M4 J M1 M5 M2 M5 J M5 M4 M3 J M1 M6 M2 M4 A M3 M5 M6 K M2 A A M6 M6 M3 K M2 M1 K M3 J M4 Q K M6 M1 A M2 M2 A K M3 Q M1 M2 M2 M4 J M2 M1 J M3 J M3 M6 M3 J J Q M4 A Q J M3 M1 M6 M5 K M2 M2 M5 M3 Q M5 A J SC_T M5 J M5 K M2 M2 M1 M5 J M3 SC_T J K M1 SC_D M6 M4 K M2 M2 J M4 K J M5 K J M2 M1 Q
R5: M5 A K K M4 M3 M2 M3 M5 M5 J M3 M2 K M2 J M4 M5 M4 K M5 K Q M4 M2 M2 J K Q M4 J M6 M6 M1 K J M2 M4 M5 Q K A M1 M1 Q A M2 K M4 M3 M3 M6 M4 M5 M4 K A M5 M5 M2 M1 M6 M3 M6 J M6 M2 A M3 M6 K K J A J M4 J M5 J A M1 M5 A M1 K M6 M6 M2 M3 SC_D M6 M1 M4 A SC_T M5 M1 Q M2 M4 M5 K M3 K M5 M6 M2 A M1 M1 M2 A A K J M5 M2 J J M5 J M5 Q A Q A M3 SC_D K J M5 M2 J K M3 SC_T M5 M5 M4 M6 K M6 M1 M4 M1 M4 M3 M2 M5 M6 M3 M1 M6 Q Q Q J M5 M5 Q
```

### 主遊戲 組 1

| 組 | 軸 | 長度 | M1 | M2 | M3 | M4 | M5 | M6 | MY | SC_D | SC_T | A | J | K | Q |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 主遊戲 組 1 | R1 | 160 | 16 | 15 | 14 | 12 | 17 | 16 | 4 | 2 | 2 | 20 | 18 | 11 | 13 |
| 主遊戲 組 1 | R2 | 160 | 13 | 16 | 19 | 17 | 15 | 13 | 4 | 2 | 2 | 13 | 13 | 18 | 15 |
| 主遊戲 組 1 | R3 | 160 | 9 | 17 | 21 | 12 | 18 | 13 | 4 | 2 | 2 | 10 | 17 | 15 | 20 |
| 主遊戲 組 1 | R4 | 160 | 15 | 11 | 13 | 18 | 20 | 15 | 4 | 2 | 2 | 13 | 12 | 17 | 18 |
| 主遊戲 組 1 | R5 | 160 | 17 | 10 | 11 | 27 | 14 | 11 | 4 | 2 | 2 | 18 | 14 | 13 | 17 |

```strip
# 主遊戲 組 1
R1: M5 Q M1 M2 M1 M6 J M1 M6 M4 A J K SC_T M6 M2 Q M5 J M6 J M6 SC_T M5 A K M1 MY M1 A M5 M5 Q M3 J K M2 M2 M6 A M4 M6 A M5 K M4 A Q SC_D M3 J M5 M6 M1 J M1 M1 K M3 K M2 J K M5 M5 A M3 M4 Q M6 Q Q A M3 M3 M5 K M3 M4 J MY J M3 M2 K M2 M6 J J M6 M3 M1 MY A M4 M2 M5 M3 M3 M1 A A M1 Q M3 M1 M2 A M2 A Q M5 M2 J J M2 M3 A M4 J M5 M1 K M3 M1 Q SC_D Q Q M4 MY M5 M6 M4 M1 A M4 A M6 M4 M6 A A M1 A M6 M2 A Q J M4 K M5 M5 J M2 M2 M5 J M6
R2: J M4 J M4 K A MY M5 SC_D M6 M4 M3 K M2 SC_T M6 M6 M5 Q M5 M3 M6 M2 M1 M5 A M3 M3 M4 M1 M6 Q M4 J M5 M2 M5 M4 M6 M1 J M4 J A Q M2 J A M6 K M1 Q M4 A A M2 M3 Q M5 M5 M6 J M3 M4 M5 J M6 M3 M2 M1 M2 M3 Q J M4 M6 MY M6 M3 M1 J Q K M4 SC_D M3 A Q M1 M3 M4 M2 A A Q MY M5 A M1 M3 Q K M1 M5 M4 M3 A K M2 K K K M4 K M3 J M3 K Q K A Q M5 J A M1 SC_T M3 Q M3 K K M6 M1 M4 M2 M2 M2 M4 M1 M5 Q M6 M5 K K M2 M3 M2 K J M1 M4 Q MY M3 M5 K M2 M2
R3: Q K M5 M5 J M2 M5 M3 M2 M5 K M2 M6 K Q M4 M6 MY J Q J M2 M1 Q M5 M1 Q M3 M2 A K J Q A M1 M4 MY M3 M4 J M2 M3 J J J A K M3 M5 M6 J M3 Q SC_D M3 Q M2 J Q M3 K M3 K M3 M1 M6 M4 MY K M5 M5 M4 Q M4 J M5 M2 M4 Q Q M2 J M4 K M1 M6 K M5 M1 M3 M6 M6 M2 M3 M1 Q J Q M3 M5 M2 M1 SC_T M2 M5 K M4 M1 M5 K M5 M6 M5 M5 M3 M2 M3 K A M3 J A J A M3 M2 Q J A K M4 M5 Q A Q M3 M6 SC_T Q M2 M4 J Q M2 SC_D M3 A K M6 MY M5 M2 M6 M4 M3 M3 Q M6 A M6
R4: A M2 M2 M6 M1 M1 M4 A K J M3 K M1 A M3 M5 K M5 M4 M5 M3 Q Q M3 Q M4 M3 M5 M4 Q M3 M5 Q M2 M4 M1 M2 J M1 M6 M2 Q M2 M6 M4 M5 M1 MY K Q J M3 J A M4 A SC_D M2 M5 M5 A M5 K K M4 M1 K K Q M1 M2 M5 M4 M4 M6 M3 Q M4 M5 SC_T J M6 Q J M1 M3 M4 M6 A A M6 M4 M5 M5 Q MY K M5 J M5 Q Q K M5 J A J K M6 Q M3 K M2 M3 J SC_D M6 M4 A M5 M1 M1 M4 M5 M1 Q SC_T M2 M6 M1 M3 M6 M6 MY K Q K K K K M3 M4 M6 J Q M5 M2 A Q M4 M4 M6 J A M5 M1 A MY M1 M6
R5: M5 J M1 J J K M6 MY M3 M5 M5 M4 M1 M5 Q Q M4 A M2 Q M4 M2 M1 A SC_T A A M5 M3 Q J M4 Q M2 SC_T Q Q M4 M5 M1 K Q M5 M1 M3 A M6 Q M2 K M2 M5 M4 M6 M4 M2 M5 M6 A SC_D M5 A M5 K A K M4 MY MY K Q M3 Q M4 M1 Q M1 M6 M2 M4 J M1 M4 M4 K J M1 A M3 J M4 M4 J M1 M3 M5 M4 K M4 M3 M3 A K M4 A K M6 K A A Q K M2 M1 M4 A M1 M6 M1 M6 SC_D A Q M4 M6 K M1 J J M4 M4 M3 M1 M3 M3 M4 M2 MY J M4 A M6 J M4 J A Q M4 M4 M6 M1 M1 M4 M5 M5 A Q Q J M2
```

## 邊界聲明

- 本檔由 ps_probspec 自來源檔 deterministic 組出（重產覆蓋，人工區保留）；來源 sha 記於 `prob-spec.meta.json`，ps_lint 擋 STALE。
- 不產 xlsx 公版、不畫 drawio；兩者為 View 軌，由本檔與 odds.json 另產。
- RTP / 觸發率只引用快測結果，不在本檔定案；參數 null 依 P-002 顯示 待決議。
