# 正式 Client：骨架、Stage → TS 移植對照、兩軌重播一致

> 狀態：0.7.0（2026-10-22，計畫 P5 垂直切片：Huff N' Puff 經 WS 可玩、e2e 全過；接上原創素材與共用音效）。
> 來源：pixi-game-platform（aidev `data/web-game/pixi-game-platform/`，ND-3：Paddy 2026-10-22 決定放 data；素材打包產物放 output，不進 data）；演練紀錄 knowledge/webgame raw `2026-10-22-client-vertical-slice-notes`。知識頁：W-010。

## 1. 產骨架

```bash
# 新 repo（共用套件＋一款遊戲）
python .kiro/skills/ark-web-game/scripts/wg_client_init.py --out <repo 資料夾> --game <npm 名> --key <game key> --name "<顯示名>"
# 既有 repo 加一款遊戲
python .kiro/skills/ark-web-game/scripts/wg_client_init.py --out <repo> --game <npm 名> --add-game
# 參考 Client 的共用部分改了之後，更新範本
python .kiro/skills/ark-web-game/scripts/wg_client_init.py --sync-template --from <pixi-game-platform 根> --ref-game huffnpuff
```

產出後：`pnpm install && pnpm -r typecheck && pnpm -r test && pnpm -r build`。遊戲要改的只有 `src/game.config.ts`（符號、聽牌、贏分門檻）、`src/presenters/`（專屬 Presenter 與 `index.ts` 對照）、`e2e/`（從參考遊戲複製後改情境）。

版本基線（DR-5）：pixi.js 8.6.6、TypeScript 5.9.3（strict、noUncheckedIndexedAccess）、Vite 6.4.5、Vitest 3.2.7、pnpm 10.28.0、Playwright 1.56。根 `package.json` 要有 `pnpm.onlyBuiltDependencies: ["esbuild"]`，否則 pnpm 10 略過 esbuild 安裝腳本並出警告。

## 2. Stage → TS 移植對照

| Stage（ark-game-proto runtime） | 正式 Client | 差異 |
|---|---|---|
| `service/wire.js`、`arkconn.js` | `@pgp/ark-wire` codec、ArkConn | 同一組 Go 黃金封包（`fixtures/wire-golden.json`）；`ready()` 同行為 |
| `service/service.js` 五個 Service | `@pgp/game-service` | 沒有 LocalService（正式 Client 不帶數學）；trace 格式相同，可互播 |
| `service/result.js validate` | `@pgp/shared-types validateSpinResult` | 同規則；型別由 schema 產生，`schema:sync-check` 守門 |
| `core/app.js` 啟動 | `runtime/boot.ts` Boot 狀態機 | idle → connecting → loading → core_ready → playable／error；`time_to_playable_ms` 送遙測 |
| `Proto.time.speed`、`Proto.wait` | `runtime/clock.ts`（RealClock／ManualClock） | 測試用 ManualClock 手動推進，不靠真時間 |
| `Proto.tween` | `runtime/tween.ts` Tweener | 屬性路徑、緩動、loop 同語意 |
| `slot/module.js spin()／play()` | `game/controller.ts` GameController | 流程與 View 分離：Controller 可在 node 測；View（Pixi）只負責畫 |
| `slot/reels.js` | `scenes/reels.ts` ReelView | 按 SPIN 立刻空轉；依 `reel.grid` 逐軸停 |
| `features/*/present.js`、game.js `Stage` 類別 | `presenters/*.ts`＋`presenters/index.ts` | 只讀 `feature.script`；依 `script.type` 選 Presenter，沒對到用通用版 |
| `playPending(app)` | `GameController.start(info)` | init 帶 pending → 先播、以 balanceAfter 校正、ack，之後才開放 SPIN |

## 3. 必守規則（實作中確認）

- 按 SPIN：先樂觀扣押注並開始空轉（掩蓋延遲）；拿不到結果 → 退回押注、`abortSpin()`、顯示錯誤碼，不播放。
- 結算後餘額一律改用 `balanceAfter`；ack 失敗不擋遊戲（下次 init 會帶回 pending）。
- 交給 View 之前必驗 SpinResult；驗證失敗回 `SCHEMA_INVALID`，不播放。
- 演出亂數不碰數學：轉輪空轉的假符號用獨立序列（正式版改用 `fx`）。
- 視窗掛勾 `window.__pgp`（boot、hud、presentLog、spin、play、force、trace、setSpeed）只給 e2e 與除錯，不放 seed、token。

## 4. e2e 情境（`games/<game>/e2e/e2e.mjs`＋`e2e.config.json`，真 Go Server）

| 情境 | 做法 | 通過條件 |
|---|---|---|
| main | `-dev -seed 7` 起 Server，`?service=ws&url=…&dev&speed=30` 開頁，連轉 N 局 | 全部有結果；HUD 餘額＝最後 balanceAfter＝Server 餘額；0 頁面錯誤；`time_to_playable_ms > 0` |
| features | `window.__pgp.force({feat})` 每種玩法一次；Server `-ws-max-inline 2000` | 玩法種類相符、事件含 feature-start／end；`stats.chunked > 0`（真 Server 分段） |
| pending | 頁 A 直接 `service.spin` 不播不 ack 就關；頁 B 同帳號開 | B 第一個 round-start 是該局；餘額＝其 balanceAfter；再 init 不帶 pending |
| protocol | `?proto_result=proto-stage-result/9` | 啟動停在 error，錯誤碼 PROTOCOL_MISMATCH 顯示在畫面 |
| trace-parity | main＋features 錄下的軌跡，Stage（stage_build 資料夾版）與正式 Client（ReplayService）各播一次 | present-events 逐筆相同（result-contract.md §3） |

遊戲差異只放 `e2e.config.json`：`game`、`arkIdPrefix`、`serverDir`（相對 aidev 根）、`serverArgs`、`scenes[{scene, expect}]`（expect＝feature.script.type）、`expectChunked`、`stage{game, odds}`。範本產的新遊戲已帶這兩個檔。

執行：`node e2e/e2e.mjs --aidev <aidev 根> [--server-bin <執行檔>] [--grep main|features|pending|protocol|trace-parity] [--out report.json] [--shots <資料夾>]`。Stage 端素材不在本機只會缺圖，不影響事件。trace-parity 時間主要花在 Stage 播 Open House（數分鐘），日常只跑前四項。

## 5. 不做的事

- 正式 Client 不放 LocalService、不放 odds；dev 預覽需要本機結果時用 ReplayService 播軌跡。
- 不在 Client 端修正 Server 的金額；不符就是 Server 或契約的 bug。
- 不直接在遊戲碼用 ArkConn；一律經 GameService。
- 不把競品裁圖、影片截圖、平台樣圖（含真人頭像）放進正式 Client；不美化、不臨摹它們。

## 6. 素材（0.7.0）

| 項目 | 做法 |
|---|---|
| 來源 | 原創美術：遊戲自帶產生器（例 `games/huffnpuff/art/gen_art.py`，程式繪製 SVG）；音效：公司共用音效庫（原檔不進 repo，`--set sfx=<資料夾>` 或環境變數）。美術組交圖：同名 PNG／WebP 放 override 資料夾即取代，程式不改 |
| 設定 | `games/<game>/assets.yaml`（pgp-assets/1）：sources、image（WebP 品質）、audio（ogg＋m4a）、bundles（required、images 別名 → 來源、sounds） |
| 打包 | `python .kiro/skills/ark-web-game/scripts/wg_pack_assets.py --config games/<game>/assets.yaml --out <aidev>/output/web-game/<game> --set sfx=<資料夾> [--svg-engine auto／cairo／browser]` → `assets/<bundle>/<別名>.<雜湊8>.webp`、`manifest.json`、`release.json`（打包後立即 verify）。需要 Pillow、SVG 轉圖（cairosvg，或 node＋playwright 走瀏覽器）、ffmpeg（m4a）。cairosvg 不支援 paint-order 與文字漸層；兩種方式尺寸相同、字形略有差異 |
| 建置 | `PGP_ASSETS_DIR=<--out 資料夾> pnpm --filter <game> build`（Vite publicDir，dist 帶 `assets/`；程式 chunk 在 `js/`） |
| 執行 | Boot 載入步驟：讀 manifest → 必要 bundle 載完才可玩（失敗 → `ASSET_LOAD_FAILED`）；可玩後背景載其餘 bundle 與音效；抽到玩法時 `Art.ensureFor(featureArt)` 先確保玩法素材；沒載到的圖退回佔位圖形 |
| 音效 | WebAudio；首次點擊或按鍵後才出聲（瀏覽器規定）；依 `canPlayType` 挑 ogg 或 m4a（iOS Safari）；`?mute` 靜音 |
| 驗證 | e2e 每頁收 HTTP 4xx 當錯誤；main 情境檢查遙測 `assets`（core_bundle_ms、background_done_ms、audio_failed = 0） |

畫面認得的別名：`bg_main`、`logo`、`reel_frame`、`reel_bg`、`ui_panel`、`ui_spin`、`ui_auto`、`ui_plus`、`ui_minus`、`sym_<符號>`、`win_big／win_mega／win_super`；音效 `sfx_spin`、`sfx_stop`、`sfx_prewin`、`sfx_alarm`、`sfx_board_start`、`sfx_board_end`、`sfx_fast_on`、`sfx_fast_off`、`sfx_info`。遊戲專屬（例 huff：`frame_／room_／house_<建材>`、`key_badge`、`wolf_huff`）寫在 Presenter 與 `game.config.ts featureArt`。

Huff N' Puff 實測（2026-10-22，原創素材 45 張＋音效 9 個）：必要包 huff-core 27 檔 217,516 B；huff-feature 18 檔 98,658 B；huff-audio 9 個 × 2 格式 458,257 B。本機 e2e：必要包 244 ms、背景與音效載完約 1 秒。
