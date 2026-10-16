# Stage 架構（ark-game-proto 1.1：PixiJS 8 正式演出版型）

> 規格 / 設計 / 計畫：aidev `docs/specs|designs|plans/2026-10-16-ark-game-proto-stage-*.md`（ADR-001～007、CMP-xxx、API-xxx 編號以設計文件為準）

## 一句話

**演出層只向 GameService 要一份完整的 SpinResult 並播放**；結果來源可以是瀏覽器內引擎（LocalService）、slot-bot server（HttpService，後面接 Go 機率 Server）或錄好的軌跡（ReplayService）。換來源不改任何演出程式。

## 兩個參考範例怎麼合

| 取自 | 內容 |
|---|---|
| Proto 三層試玩模板（HuffNPuff 試玩 / 八尺 / 柏青共用模板）| 遊戲包契約 `Proto.game(設定物件)`、slot Logic 與玩法 logic（原封）、Timeline 演出 JSON、可控時鐘（倍速 / 暫停 / 跳過 / 取消）、除錯分頁、INFO 七語 |
| ark-game-proto 驗證雛型 | 結果先決、數學 / 演出 RNG 分流（fx = seed ^ 0x5bd1e995）、強制情境 = 搜尋真 seed、SpinResult 整數金額、PixiJS 8.6.6、go-rand.js |

## 分層（單向依賴）

```text
遊戲包 game.js ──spec/logic──▶ 引擎層（node 可跑）: slot/logic.js · features/*/logic.js · service/result.js
       │                                   ▲
       └─layout/presentation/info──┐       │ SpinResult（proto-stage-result/1）
                                   ▼       │
演出層（Pixi）: core/stage · tween · assets · hud · timeline · slot/reels · slot/module · features/*/present.js
DOM 疊層: core/ui（除錯分頁）· INFO（module.buildInfo）
                                   ▲
GameService（service/service.js）: LocalService | HttpService | ReplayService | Recorder（錄製）
```

- 引擎層不碰 Pixi / DOM；演出層只讀 `Proto.slotLogic.prepare / feature`（符號、賠付表、盤面尺寸），不呼叫任何抽值函式（`stage_test --only layering` 守門）。
- 演出亂數：`app.rng`（Timeline random）、`mod.fx`（填充符號、粒子、照轉盤面）都是 fx 流。

## 一局的流程（Flow，slot/module.js）

`SPIN` → 轉輪立刻起轉（DD-001，掩蓋延遲）→ `service.spin({ bet })` → Schema 驗證（失敗不播放）→ ReelView 依 `reel.grid` 停輪（聽牌延長 `presentation.stage.tease` 或預設 Scatter 規則）→ `presentation.stage.afterReels` → 連線（壓暗 / 脈動 / 輪播）→ 報獎階梯 → 有 `feature` 時：觸發音效 / 演出 → `declare`（有設定才顯示）→ `features[type].Stage` 依 `feature.script` 播放 → 結算 → HUD 餘額改用 `balanceAfter`（權威值）。

## 檔案

| 路徑 | 元件 | 來源 / 改動 |
|---|---|---|
| `scripts/stage/runtime/core/core.js` `sim.js` `audio.js` `timeline.js` `ui.js` | 時間 / 亂數 / 事件、統計、音效、演出 JSON、除錯面板 | Proto 原檔沿用 |
| `core/tween.js` | 補間（ADR-007），`Proto.tick(dtMs)` 由 Pixi ticker 推進 | 新 |
| `core/stage.js` | PixiStage：7 層 Container、縮放、DOM 疊層 `stage.dom`；方法與 Proto stage.js 同名同參數 | 重寫 |
| `core/assets.js` | 圖片 → `PIXI.Texture.from(img)`；缺檔佔位；熱替換；file:// 偵測；`window.__STAGE_INLINE` 內嵌對照 | 重寫 |
| `core/hud.js` | Pixi HUD（餘額 / 押注 / 贏分 / 按鈕；`layout.hud.art` 透明熱區）| 新 |
| `core/app.js` | 啟動、`Proto.createService`（網址參數）、服務分頁（錄製 / 重播 / 統計 / FPS）| 改寫（除錯分頁沿用）|
| `service/result.js` | ResultBuilder + 驗證器 | 新 |
| `service/service.js` | Local / Http / Replay / Recorder、goFloatRng | 新 |
| `slot/logic.js` `features/鎖格重轉/logic.js` | 數學（原封切出，`document` 判斷以前）| 搬移 |
| `slot/reels.js` | ReelView（帶面 + 遮罩 + 模糊 + outBack 回彈）| 新 |
| `slot/module.js` | Flow、連線、報獎、宣告、INFO、強制 / 歷史分頁 | 重寫 |
| `features/鎖格重轉/present.js` | 鎖格重轉 Pixi Presenter | 新 |
| `schema/spin-result.schema.json` | SpinResult JSON Schema（給 Go / slot-bot 共用）| 新 |
| `runtime/manifest.json` | 載入順序（`@src/` = scripts/src，例 go-rand.js）| 新 |
| `stage_build.py` `index.template.html` | 組裝：資料夾模式 / `--single` 單檔 / `--serve` | 新 |
| `tests/stage_test.js` `load.js` `mock_server.js` `test_stage_build.py` `smoke.js` | 引擎 / 契約 / 分層 / Http / 建置 / 冒煙 | 新 |
| `golden/stage-demo/game.js` | 無版權示範遊戲包（佔位美術）| 新 |

## 驗證

| 指令 | 驗什麼 |
|---|---|
| `node scripts/stage/tests/stage_test.js [--game <game.js> --orig <原檔>]` | 結果一致（LocalService vs Proto Logic 10 萬局 0 差異）、Schema、冪等、Replay、Tween、Stage API、分層、Http（mock）、go-rand、試點邏輯逐字相同 |
| `pytest scripts/stage/tests/test_stage_build.py` | 資料夾 / 單檔建置、素材複製與缺檔、預算守門 |
| `node scripts/stage/tests/smoke.js --html <index.html> --scenes '[…]'` | Playwright 開頁 → 強制情境 → 截圖、0 console error、FPS |

## 落點（佈局契約 v3：`.kiro/skills/ark-game-spec/references/game-layout-contract.md` ⑦）

| 位置 | 內容 | 入 git |
|---|---|---|
| `data/slot/<slug>/game/pixi-client/` | `game.js`（遊戲包）、`stage.yaml`（建置設定）、`stage-build.json`（清冊）、`build.sh / build.ps1`、`README.md` | ✅（< 1 MB，不放圖）|
| `output/slot/<slug>/game/pixi-client/single/index.html` | 單檔（素材 WebP 內嵌，可雙擊）| ❌ 重產物 |
| `output/slot/<slug>/game/pixi-client/folder/` | 資料夾版（http 服務；`--folder` / `--serve`）| ❌ |
| `data/slot/<slug>/game/go-server/` | Go Server 原始碼（雛型或正式；接 Stage HTTP 契約）| ✅ |
| `output/slot/<slug>/game/go-server/` | Go 二進位、執行記錄 | ❌ |

ark-game 系列分工：① analysis / ② spec（ark-game-spec）· ③⑤ prob（ark-game-prob）· ④ quicktest（ark-game-quicktest）· ⑥ proto（ark-game-proto 驗證台）· ⑦ game（Stage 用戶端 + Go Server）。舊 `proto/stage/` 一版內相容讀取。
