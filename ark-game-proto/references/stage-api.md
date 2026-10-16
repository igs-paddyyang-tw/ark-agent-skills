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

## 與 Go 對帳

LocalService `rng: 'go'`（網址 `&rng=go`）改用 Go `math/rand` Float64 數學流（go-rand.js 逐位元移植；`Float64 = Int63n(1<<53) / 2^53`）。當 Go 引擎與 JS 引擎以相同順序、相同方式（Float64）抽值時，同 seed 結果逐局相同；ReplayService 可直接重播 Go Server 錄下的 SpinResult 軌跡。
