# 架構：雙軌與四段模組

> 來源：docs/designs/2026-10-22-web-game-client-architecture-plan.md（v1.1）、web-game-client-system-analysis.md、slot-network-play-design.md。知識頁：knowledge/webgame/wiki/W-001、W-002。

## 1. 雙軌

| | AI 產線（Stage） | 正式 Client |
|---|---|---|
| 給誰 | 企劃、機率、審核、QA | 玩家 |
| 程式位置 | `.kiro/skills/ark-game-proto/scripts/stage/`＋`data/slot/<slug>/game/pixi-client/game.js` | `data/web-game/pixi-game-platform/`（ND-3，入 git） |
| 建置 | 免建置、全域載入（D-1） | TypeScript＋Vite＋pnpm |
| 數學 | game.js 內含（LocalService；⑥ 對帳的 JS 實作） | **不含**；只在 dev-preview 注入 LocalService |
| 素材 | 單檔內嵌或資料夾；可加 `--bundles` | AssetPack 分包＋CDN |
| 結果來源 | Local／Http／Ws／Replay | Http／Ws |

兩軌只共用三樣東西，任何一樣改動都要兩邊同步：

1. SpinResult／GameInfo／Release Manifest 的 JSON Schema（正本在 ark-game-proto `scripts/stage/schema/`）。
2. GameService 介面（init／spin／action／balance／ack／debug.force）。
3. ark-go wire 協定與錯誤碼表（見 wire-protocol.md）。

## 2. 一局的四段模組

```
① 機率模組  internal/prob/<game>    讀 odds；用數學流算完一局 → RoundOutcome（倍數）；Build → SpinResult 本體
② 局服務    internal/round           押注檢查、數學流／演出流、局號、冪等、局紀錄、Wallet、pending
③ 網路模組  internal/ark-go＋api     ark-go WS（sys slot）、Stage HTTP、internal play；錯誤碼；分段
④ Client    WsService／HttpService → GameService → 遊戲模組（只演出）
```

依賴只能 ③ → ② → ①；① 不 import 其他段，所以 ④ 快測與 `cmd/sim` 可以直接用 ①。

## 3. 現況（2026-10-22 計畫 P0～P5 執行後）

| 元件 | 狀態 |
|---|---|
| huffnpuff go-server | prob.Game 註冊表（`internal/prob/huff`）、局服務 `internal/round`（Mem／Redis Store、先寫紀錄再結算、pending／ack、協定協商、局號不含 seed）、api HTTP API-101～107＋WS sys `slot`（init／balance／spin／ack／fetch／action／force、結果分段） |
| Go Server 範本 | `assets/go-server-template`（34 檔）＋`wg_server_init.py`；stage-demo 抽離演練以此產生 |
| Stage runtime（ark-game-proto 1.5.0） | Local／Http／Ws／Replay／Recorder；pending 續玩、ack；`--bundles` 分包；啟動指標；present-events/1 |
| 正式 Client | `pixi-game-platform` 垂直切片：shared-types、ark-wire、game-service、games/huffnpuff；範本 `assets/client-template`＋`wg_client_init.py`（見 client-vertical-slice.md） |

## 4. 部署拓撲（ND-5 暫定：試玩與 QA 用 A；正式依平台）

- A 直連：Client → Go Server（ark-go WS）；Go 內 PlatformWallet 轉接平台錢包，token 由平台 Redis 驗。
- B 經 slot-bot：Client → slot-bot → `/internal/v1/play`；Go 只算不結帳（PlayOnly）。
- 兩者共用 ①②，差在 ② 用 `Settle` 或 `PlayOnly`、③ 開哪些端點。

## 5. 子系統依賴（正式 Client）

啟動器 → 資源管理；遊戲模組 → Runtime、結果邊界（GameService）→ 網路。遊戲模組**不得**直接使用網路層。

## 6. 正式 Client 套件（pixi-game-platform）

| 套件 | 內容 | 對應 Stage |
|---|---|---|
| `@pgp/shared-types` | 由 schema 產生的型別、PROTOCOL、錯誤碼表、`validateSpinResult` | `schema/`、`service/result.js` |
| `@pgp/ark-wire` | codec（與 Go 黃金封包逐字相同）、ArkConn（auth、sn、ret＋sn、alive、自動重連、`ready()`）、`test/mock-ark.mjs` | `service/wire.js`、`arkconn.js`、`tests/mock_ws.js` |
| `@pgp/game-service` | GameService 介面、WsService、HttpService、ReplayService、Recorder、`serviceFromQuery` | `service/service.js` |
| `games/<game>` | runtime（Boot、Clock、Tween、Emitter）、GameController（一局流程、present-events）、ReelView、Presenter 對照、視窗掛勾 `window.__pgp` | `core/app.js`、`slot/module.js`、`features/*/present.js` |

依賴方向：games → game-service → ark-wire／shared-types；遊戲碼只透過 GameService 取結果。
