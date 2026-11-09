# Canvas／WebGL 遊戲（PixiJS）怎麼測

> 實測：aidev pixi-game-platform（PixiJS Client ＋ Go Server），Docker Desktop 部署的豬來蓋福 `http://localhost:3030`、神燈 `http://localhost:3031`（2026-11-09）。範例劇本 `assets/examples/pgp-slot-smoke.yaml`。

## 和一般網頁的差別

| | DOM 頁面 | Canvas 遊戲 |
|---|---|---|
| 找按鈕 | selector | **座標**（先 `shot` 量）|
| 讀數值 | `inner_text` | **頁面掛勾**（優先）→ 沒有才 OCR |
| 等待 | `wait_for` selector | `wait_until` 遊戲狀態、`wait_stable` 畫面停住 |
| 瀏覽器 | 預設即可 | `browser: {gl: true}`（headless 沒有 GPU，要軟體 GL）|

## pixi-game-platform 的觀測點

| 觀測點 | 內容 |
|---|---|
| `#boot[data-state]` | `idle → … → playable`；`error` 時文字含錯誤碼。可玩後元素被隱藏，`wait_for` 要用 `state: attached` |
| `window.__pgp.hud` | `balance`、`bet`、`bets`、`win`、`busy`、`auto`、`message` |
| `window.__pgp.presentLog` | 演出事件：`round-start`、`reels-stop`、`base-win`、`round-end{totalWin, balanceAfter}`… |
| `window.__pgp.info` | 遊戲設定（reels、rows、symbols、bets、balance…）|
| 網址參數 | `?speed=30` 加速演出；`?dev` 開 dev 功能（強制情境，需 Server `-dev`）|

> 這是 Client 的**除錯掛勾**：只拿來讀與等待。用 `__pgp.spin()` 代替點擊會略過 UI，冒煙測試請點真的按鈕。

## 標準斷言

- **資產守恆**：`hud.balance === 前餘額 − bet + round-end.totalWin`
- **前後端一致**：`hud.balance === round-end.balanceAfter`（Server 結算）
- **押注鈕**：點 ＋／− 後 `hud.bet` 變大／變回
- **頁面健康**：0 個 page error、0 個 console error、0 個 4xx／5xx（素材缺圖會在這裡抓到）

## 座標校準（540×960，豬來蓋福）

| 按鈕 | 座標 |
|---|---|
| 旋轉 | (270, 832) |
| 減注 | (370, 840) |
| 加注 | (470, 840) |
| AUTO | (82, 843) |

換遊戲、改版面、換 viewport 都要重量：`browser_tool.py shot <url> --viewport 540x960 --gl --wait-ms 5000` → 看圖 → 寫進劇本 `vars`。

## 踩雷

- headless 截圖預設隱藏捲軸（看不到不代表沒有）；要驗捲軸改用 `--headed` 執行
- 演出有動畫，讀數字前要等 `busy=false` 或 `wait_stable`
- Server `-dev` 局紀錄在記憶體，容器重啟餘額會重置 —— 斷言用「相對前一局」，不要寫死絕對餘額
- 同一個 Docker 部署多人同時測會共用 DevWallet；要隔離就加 `?arkId=<自己的 id>`
