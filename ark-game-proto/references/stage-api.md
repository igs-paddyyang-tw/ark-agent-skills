# Stage ⇄ slot-bot server HTTP 契約（草案 v1，待 slot-bot dev 評審：spec OQ-001～OQ-004）

帳務、session、身分由 slot-bot server 負責；Go 機率 Server 只算結果。每局一次 request（ADR-005）；選擇型玩法另加 action。

| ID | 端點 | 方法 | 請求 | 回應 |
|---|---|---|---|---|
| API-101 | `/api/slot/:gameId/init` | POST | header `Authorization: Bearer <session>` | `proto-stage-info/1`：bets、defaultBet、betBase、balance、reels、rows、symbols、feature、pending（斷線未播完結果，OQ-004）；**不含 seed、輪帶、權重** |
| API-102 | `/api/slot/:gameId/spin` | POST | `{ bet, requestId }` | SpinResult（`schema/spin-result.schema.json`）；`seed: null`；`balanceAfter` 為權威值 |
| API-103 | `/api/slot/:gameId/action` | POST | `{ roundId, choice, requestId }` | 續算結果（script、totalWin、balanceAfter）|
| API-104 | `/api/slot/:gameId/balance` | GET | — | `{ balance }` |
| API-105 | `/api/slot/:gameId/dev/force` | POST | `{ scene, bet, requestId }`（scene = 條件物件或 `{ label }`）| SpinResult；**正式環境 404** |

錯誤：HTTP 4xx / 5xx + `{ code, message }`；code ∈ INVALID_BET（400）、INSUFFICIENT_BALANCE（402）、SESSION_EXPIRED（401）、NOT_FOUND（404）、SERVER_ERROR（5xx）。

## 前端行為（HttpService）

- `requestId` 冪等：同一個 requestId 重送必須回同一結果、不重複扣款（Server 去重）；前端重試沿用同 requestId。
- 逾時：預設 10 秒（abort → NETWORK）；3 秒顯示「連線中」；5xx / 網路錯誤自動重試 2 次；4xx 不重試。
- 回應先過 Schema 驗證，不合格不播放、不改餘額。
- 網址啟用：`index.html?service=http&base=<server>&game=<gameId>&token=<session>[&dev=1]`。

## 本機 mock

`node scripts/stage/tests/mock_server.js --game <game.js> --port 8787` → 用 LocalService 實作上表；header `X-Mock-Fail: n`（前 n 次 503）、`X-Mock-Delay: ms`（延遲）測重試與逾時。`stage_test --only http` 驗 Http 與 Local 同 seed 300 局逐局相同、冪等、重試不重複扣款、錯誤碼、逾時、dev/force。

## WebSocket（1.5.0，ark-go wire）

`WsService` 與 `HttpService` 同介面（init／spin／action／balance／ack／fetch／debug.force），指令、錯誤碼、分段、續玩規則的正本在 **ark-web-game `references/wire-protocol.md`**，這裡只列用法：

| 項目 | 用法 |
|---|---|
| 選擇 | `?service=ws&url=ws://host:8787/ws&ark_id=<玩家>&token=<token>&dev=1`；或 stage.yaml `service: {kind: ws, url: /ws}`（stage_build 注入 `window.__STAGE_SERVICE`）；token 正式由宿主注入 `window.ARK_SESSION` |
| 協定 | init 帶 `protocol = Proto.svc.PROTOCOL`；不相容 → `PROTOCOL_MISMATCH`（HTTP 426／WS status 426） |
| 續玩 | init 回 `pending`（未 ack 的局）→ `Proto.playPending(app)` 先播、校正餘額、ack；module 每局演完 `service.ack(roundId)`；下一局 spin 也視為隱含 ack |
| 分段 | 結果 > 單包上限時 Server 先推 `result` 分段，回應帶 `chunks、chars`；缺段自動 `fetch` |
| 重試 | 同 requestId、新 sn；NETWORK／TIMEOUT／SERVER_ERROR 才重試（間隔 200 ms 起） |
| 防洪 | ark-go 每秒 40 包、連續 3 秒超限 509 斷線；工具壓測要節流 |
| 指標 | `Proto.app.metrics.time_to_playable_ms`（自頁面開始到可玩，不含按「開始」的等待） |

## 與 Go 對帳

LocalService `rng: 'go'`（網址 `&rng=go`）改用 Go `math/rand` Float64 數學流（go-rand.js 逐位元移植；`Float64 = float64(Int63()) / 2^63`，=1.0 重抽——Go 1 值流；1.1.0 誤寫為 `Int63n(1<<53)/2^53`，1.1.1 修正）。當 Go 引擎與 JS 引擎以相同順序、相同方式（Float64）抽值時，同 seed 結果逐局相同；ReplayService 可直接重播 Go Server 錄下的 SpinResult 軌跡。

## Go Server 雛型（試點）

`data/slot/huffnpuff-open-house/game/go-server/`：ark-go 網路層（WebSocket wire 協定）＋ 上表 HTTP 契約 ＋ `/internal/v1/play`（給 slot-bot server 的純算結果端點）。引擎讀 odds JSON（quicktest 範本欄位 ＋ `huff` 區塊）；`tools/parity.js` 驗 Go 引擎與用戶端 `?rng=go` 同 seed 整份 SpinResult 逐局相同（`--via ws` 經 WebSocket 對帳）；`tools/smoke_ws.js` 端到端。2026-10-22 起為 ark-web-game Server 範本的首例（`internal/prob`、`internal/round`）。

