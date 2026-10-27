# 網路：ark-go wire、slot 指令、錯誤碼、協定協商

> 來源：huffnpuff go-server `internal/ark-go/{wire,dispatch,session}`、`internal/api/ws.go`；slot-network-play-design §4.4、§4.5。知識頁：W-004、W-005、W-006。

## 1. 封包（ark-go wire，相容 Python GameSocket2）

- 格式：`[長度 4 位數十進位補零][JSON]`。指令 `{"cmd","data","sn","sys"}`；回應 `{"ret","data","sn","sys"}`，`ret` = 原指令名，`sn` 原樣回傳。
- 長度是**字元數**。送出時非 ASCII 一律跳脫成 `\uXXXX`，讓字元數＝位元組數。
- 單包上限 9,999 字元；超過 Server 拒送（`ErrTooLarge`）。
- `sys` 省略＝default system：`auth`（`{ark_id, ark_token}`）、`alive`（無回應）、`close`（回 "Bye"）。
- 未認證送其他指令回 `{status:-999, msg:"not authed"}`。
- sn 要嚴格遞增（Server 可設 enforce）；**重送同一局用新 sn、同 requestId**。
- Server 預設：認證逾時 10 秒；20 秒沒收到封包以 408 關閉。Client 每 8 秒送 `alive`。

## 2. sys `slot` 指令

| cmd | data | 回應 data | 狀態 |
|---|---|---|---|
| `init` | `{protocol, runtimeApi, gameVersion}` | `{status:0, info}`；info 含 `pending`、`supported` | protocol 欄位待 P3 |
| `balance` | — | `{status:0, balance}` | 已有 |
| `spin` | `{bet, requestId}` | `{status:0, result}` 或 `{status:0, roundId, chunks, chars}` | 已有（chars 待 P3） |
| `result`（推播） | `{roundId, i, n, part}` | — | 已有 |
| `ack` | `{roundId}` | `{status:0}` | 待 P3 |
| `fetch` | `{roundId}` | 同 spin | 待 P3 |
| `action` | `{roundId, choice, requestId}` | 同 spin | 待 P3 |
| `force`（dev） | `{scene, bet, requestId}` | 同 spin | 已有 |

分段：結果 JSON 超過 `MaxInline`（9,999 − 256）時，先推 n 段（每段 4,000 字元），再回 `chunks`。同連線 FIFO，回應到時分段必已全到；依 `i` 串接、驗 `chars`，缺段呼 `fetch`。格式待平台確認（OQ-102）。

## 3. 錯誤碼（HTTP 狀態碼＝WS status）

| code | 值 | Client 行為 | 可重試 |
|---|---|---|---|
| INVALID_BET、BAD_REQUEST、NOT_SUPPORTED | 400 | 提示／隱藏功能 | 否 |
| SESSION_EXPIRED（含 -999） | 401 | 換 token 重連 | 換 token 後 |
| INSUFFICIENT_BALANCE | 402 | 提示 | 否 |
| NOT_FOUND | 404 | 錯誤畫面 | 否 |
| ROUND_IN_PROGRESS | 409 | 先播 pending | 否 |
| PROTOCOL_MISMATCH | 426 | 請更新 | 否 |
| SERVER_ERROR | 500 | 同 requestId 重試 | 是 |
| TIMEOUT、NETWORK、RESULT_INCOMPLETE、SCHEMA_INVALID | Client 端 | 前三者重試或 fetch；SCHEMA_INVALID 停止 | 視碼 |

## 4. 冪等與續玩

- 局紀錄狀態：computed →（Wallet.Settle 成功）settled →（Client ack）acked；結算失敗 failed（不扣款）。
- **先寫紀錄、再結算**；Wallet 以 roundId 去重。
- 未 ack 的 settled 局放 `pending`，init 帶回；Client 先播 pending 再開放 SPIN。
- 局號格式 `R<毫秒 base36>-<16 位 hex 隨機>`，不含 seed（2026-10-22 已改）。
- **下一局 spin 視為上一局的隱含 ack**（DR-1）：舊 Client 不送 ack 也不會卡；`ROUND_IN_PROGRESS`（409）保留不用。
- 同 requestId 重送 → 回同一局（不重複扣款）；e2e 以「結算後斷線」驗證：Server 只結算 1 次。

## 5. 協定協商

- Client init 帶 `protocol = {result:"proto-stage-result/1", info:"proto-stage-info/1", wire:"ark-wire/1"}`。
- 主版號不同即不相容 → 426；Server 灰度期間同時支援新舊兩個主版號。

## 6. Client 常數

逾時 10,000 ms；3,000 ms 顯示連線中；重試 2 次（退避 200 ms × 次數，給自動重連時間）；alive 8,000 ms；重連退避 0.5／1／2／4／8 秒；背景下載併發 2。

## 7. 實測事實與易錯處（2026-10-22）

| 事實 | 影響與做法 |
|---|---|
| ark-go 防洪：每秒 40 包，連續 3 秒超限以 509 關閉 | 一般玩家不會碰到；對帳、壓測 Server 加 `-flood-limit 100000`（只測試用）。vendored 程式不改 |
| KickSameID：同一 ark_id 第二條連線會把第一條踢掉 | Client 重送前用 `ArkConn.ready()` 等自動重連完成，**不另開連線**；否則兩條連線互踢 |
| node 22 的 WebSocket 連不上時只發 `error`、不發 `close` | `onerror` 也要把狀態設為 closed 並 reject；工具（parity.js）沒跑完要 exit 2，不可靜默 exit 0 |
| 正式 odds 6 萬局最長結果 7,551 字元 < 單包上限 9,743 | 分段幾乎不會發生，但保留；測試用 `-ws-max-inline` 調小門檻強制走分段與缺段 fetch |
| 分段 `part` 是 `\uXXXX` 轉義後的 JSON 文字 | 依 i 排序接起來、檢查段數與 chars 後直接 `JSON.parse`；缺段 → `fetch(roundId)` 補拿一次，再缺回 `RESULT_INCOMPLETE` |
| 協定不相容回 426 `PROTOCOL_MISMATCH` | 不重試；啟動停在 error 並顯示錯誤碼（正式 Client e2e「protocol」情境） |

