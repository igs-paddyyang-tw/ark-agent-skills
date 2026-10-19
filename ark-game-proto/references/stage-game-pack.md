# Stage 遊戲包契約與遷移指南

遊戲包 = 一支 `game.js`，呼叫一次 `Proto.game(設定物件)`。格式與 Proto 三層試玩模板相同；Stage 只**新增** `presentation.stage` 與 `features[type].Stage` 兩個 Pixi 掛勾。

## 設定物件

| 鍵 | 用途 | Stage 差異 |
|---|---|---|
| `name` | 頁面標題 | — |
| `seed` | LocalService 數學流種子（null = 隨機）| 網址 `?seed=` 優先 |
| `stage` | `{ width, height, background }`（預設 1080×1920）| Pixi 畫布 |
| `volume` | `{ master, bgm, se, voice }` | — |
| `assets` | `images / videos / sounds`：代號 → 路徑 | 路徑相對 `--assets-base`；`sym_<代號>` 自動當圖騰圖 |
| `spec` | 盤面、符號、賠付表、押注、輪帶、`custom`、`feature` | **數學，零修改**；Http 模式時只用來顯示 |
| `layout` | `decor`（fill 可寫 CSS 漸層 / image）、`jackpots`、`reels { x,y,w,h,cellW,colX }`、`hud { balance, bet, betSub, win, buttons, art }` | 座標沿用；`hud.art = true`（或 decor 有 bar 圖）時按鈕為透明熱區 |
| `presentation` | `startBalance`、`reelFeel`、`sounds`、`trigger`、`winTiers`、`declare`、`featureIntro / featureOutro`、`featureAutoSpin` | 新增 **`stage: { afterReels(mod, g, ev, result), tease(mod, result, ev), scenes: [[名稱, 條件]] }`** |
| `performances` | 演出 JSON 步驟 | 沿用（image / text / video 改由 Pixi 畫）|
| `info` | 七語 INFO（`langs / rows / icons`）| DOM 疊層 |

## 玩法

| 物件 | 用途 |
|---|---|
| `Proto.features[type].logic = { prepare, draw, play }` | 數學（原封）；`play(..., { record: true, prng })` 回傳的劇本 = SpinResult `feature.script` |
| `Proto.features[type].Stage = class { constructor(mod, fp); run(res, draw, ctx, ev, g, result); exit(); references() }` | **Pixi Presenter**；`res` = `feature.script` 加上 `x`；只能用演出亂數 `mod.fx` |
| `Proto.features[type].debugTabs(mod)` | 除錯分頁（DOM）|

沒有 `Stage` 的玩法會顯示摘要畫面（不中斷），設定檢查列出警告。

## Presenter 可用的模組 API（與 Proto 同名）

`tf()`（快速模式 0.35）`cell(r,row)` / `cellEl(r,row)`（Pixi Sprite）`cellCenter(r,row)` `playSound(id)` `setInfoLine(t)` `symName(id)` `featureHud(o)` `waitSpinPress()` `spinReels({ grid })` `showWins(ev)` `clearWins()` `countBox(v,dur)` `winLadder(v)` `setMode(m)` `bet` `stage`（PixiStage：`layer / add / remove / showText / flash / shake / texture`）`view`（ReelView）`tween`（`Proto.tween`）`fx`（演出亂數）`state` `p` `pres` `layout` `app`

## 遷移一款 Proto 試玩（以 HuffNPuff 為例）

1. 複製 `game.js` 到 `data/slot/<slug>/game/pixi-client/game.js`；**`CFG` 到 `// === 演出` 之前、`runSim` 一字不改**（`stage_test --only parity-src` 比對）。
2. 演出段改寫：DOM 元素 → `PIXI.Container / Sprite / Text / Graphics`；`el.animate` / CSS keyframes → `Proto.tween`（`loop` 做呼吸 / 脈動）；`st.add(key, el, …)` → `mod.stage.layer(…).addChild` 並記在 `stage.items` 以便 `remove(key, fadeOut)`。
3. `Present` 改名為 `Stage` 類別並掛到 `features[type].Stage`；`presentation.afterReels` 移到 `presentation.stage.afterReels`。
4. 演出中任何「照轉盤面」改用 `mod.fx` 產生（**不得呼叫 `Proto.slotLogic.spinGrid`**）。
5. 除錯的「強制下一手」（改 FORCE / mod.force）改成 `presentation.stage.scenes`：條件物件（`{ feat: 'OH' }`）或函式 `(m) => …`（m = `{ g, ev, draw, res }`），由 `service.debug.force` 沿數學流搜尋，不改結果。
6. 建置：在 `data/slot/<slug>/game/pixi-client/stage.yaml` 寫 `game`、`assets_base`（原試玩夾）、`max_side`，再跑 `python scripts/stage/stage_build.py --slug <slug> [--folder | --serve]`；產物在 `output/slot/<slug>/game/pixi-client/`（不入 git），清冊 `stage-build.json` 留在 data。
7. （1.1.2）**正式機率**：`stage.yaml` 加 `odds: <相對路徑>/odds_<ver>.json` → stage_build 在 game.js 之前注入 `globalThis.HUFF_ODDS`（單檔內嵌、資料夾版另產 `odds.js`；壞 JSON 擋下，清冊記 odds 路徑與 sha16）。遊戲包要讀到它得自己實作 **odds 模式**：有 `globalThis.HUFF_ODDS` 時數學依 odds（與 Go 引擎同抽值順序），沒有時退化為原試玩行為——並以「不給 odds 的對帳 0 不一致」守門。範例：`data/slot/huffnpuff-open-house/game/pixi-client/game.js`（轉輪組改用 `spec.reelSets`、安全帽組別、K-019 封頂、重玩遞減、獎項池）。
7. 驗：`node scripts/stage/tests/stage_test.js --game <新> --orig <原>`、`node scripts/stage/tests/smoke.js --html <index.html> --scenes all`（無 Playwright 時自動改用系統 Chrome / Edge）；送審前 `py scripts/review_build.py --slug <slug> --run-checks` 發布拍板包 `data/slot/<slug>/review/`。

HuffNPuff 實測：演出段約 480 行改寫，數學 272 行逐字相同；LocalService 與原 Proto Logic 10 萬局 0 差異；單檔 2.1 MB（44 張圖 WebP 內嵌）。

## 金額

引擎內部仍以「總押注倍數」計；SpinResult 一律整數 credit：`floor(倍數 × bet + 1e-6)`。原 Proto 浮點顯示（`Math.round(x*bet*100)/100`）在押注非基準值時可能差 1 credit 以內；以 SpinResult 為準。
