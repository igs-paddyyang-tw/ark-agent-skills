# 單局結果契約與抽選點對照表

> 來源：slot-network-play-design ADR-002、§5；ark-game-proto `scripts/stage/schema/spin-result.schema.json`。知識頁：W-003、W-007。

## 1. 兩層

| 層 | 名稱 | 產生者 | 單位 | 內容 |
|---|---|---|---|---|
| L0 | RoundOutcome | 機率模組 `Game.Play(rng, fx)` | 倍數 | 停輪、盤面、連線、觸發、玩法劇本（record）、fx |
| L1 | SpinResult `proto-stage-result/1` | 局服務呼叫 `Game.Build` 後加信封 | 整數 credit | L0 換算＋roundId、requestId、bet、balance、winType |

- 換算只有一處：`credits = floor(x × bet + 1e-6)`。
- `totalWin = base.win + feature.win`；`balanceAfter = balanceBefore − bet + totalWin`（Validate 必檢）。
- `feature.script`＝機率模組 `record:true` 的原樣輸出，各遊戲自訂；Presenter 只讀它。
- `fx` 是演出亂數種子；`seed` 在 Server 模式恆為 null。
- winType 門檻（倍數）：GOLDEN 100、SUPER 50、MEGA 25、BIG 10、SMALL 5、LIGHT 1、NORMAL 0、NO_WIN（win = 0）。

## 2. 抽選點對照表（trace-map）

每款遊戲在 `data/slot/<slug>/game/trace-map.md` 交一份，是 ⑧ 抽離的第一個產出，也是機率審核看「畫面上這個動作是哪個抽選點決定的」的入口。

格式（表頭必須完全相同，六欄都不可空白；不演出就寫「不演出」）：

```markdown
---
title: "<遊戲> 抽選點對照表"
type: trace-map
slug: <slug>
prob_spec: data/slot/<slug>/prob/prob-spec.md
schema: proto-stage-result/1
---

| # | 抽選點 | 參數 | Go | SpinResult 欄位 | 演出步驟 |
|---|---|---|---|---|---|
| M-① | 依權重抽轉輪組 | P-01／P-02 | `Engine.SpinGrid` | `reel.combo` | 不演出 |
```

規則：

- `#` 唯一；建議前綴：M（主遊戲）、玩法代號（HS、OH、FG…）、全局、演出。
- 「SpinResult 欄位」中以反引號包住的路徑會對 schema 檢查：`reel.stops`、`base.ways[]{sym,len}`、`feature.script.hands[]`。schema 未展開的物件（`base.extra`、`feature.draw`、`feature.script`）底下由遊戲自訂，不再往下檢查。
- 「參數」欄要涵蓋 prob-spec 第 3、4 節出現的所有 `P-xx`。
- 檢查：`python .kiro/skills/ark-web-game/scripts/wg_trace_check.py <trace-map.md> --prob-spec <prob-spec.md>`。

## 3. 演出事件 present-events/1（兩軌重播一致）

遊戲模組播放一份 SpinResult 時，在對應演出時點送出以下事件；**值只取自 SpinResult**，所以同一份結果在 Stage 與正式 Client 的事件序列必須完全相同。

| 順序 | type | 欄位（另含 `roundId`） | 時點 |
|---|---|---|---|
| 1 | `round-start` | `bet` | 開始播放 |
| 2 | `reels-stop` | `stops` | 最後一軸停妥 |
| 3 | `base-win` | `win`、`ways`（連線數） | `base.win > 0` 才有，連線演出前 |
| 4 | `feature-start` | `feature`（type）、`spinsPlayed` | 有 feature 才有 |
| 5 | `feature-end` | `win`（feature.win） | Presenter 播完 |
| 6 | `round-end` | `totalWin`、`balanceAfter` | 結算顯示前 |

- Stage：`Proto.app.events.on('present', fn)`（slot/module.js `play()`）；正式 Client：`GameController.events.on('present', fn)`，視窗掛勾 `window.__pgp.presentLog`。
- 對帳（trace-parity）：錄一份軌跡（Recorder，`proto-stage-trace/1`）→ Stage 逐局 `module.clearWins(); await module.play(r)`、正式 Client 用 ReplayService 逐局 spin → 兩邊事件 JSON 逐筆相同。
- 新增事件類型＝改契約：兩軌同版加入，版號升 `present-events/2`。
