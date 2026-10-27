# ⑧ 抽離 SOP：game.js 數學 → Go prob.Game

> 狀態：**定版 1.0**（2026-10-22 以 stage-demo 演練：第一次移植即通過黃金比對，經 WS 對帳 2 seed × 5 萬局＋壓力版 2,000 局 0 不一致）。
> 來源：一致性報告 §六；ark-game-proto references/go-parity.md；演練紀錄 knowledge/webgame raw `2026-10-22-extraction-drill-stage-demo`。知識頁：W-007、W-009。

## 0. 先判斷局型

| 局型 | 數學正本 | 要做什麼 |
|---|---|---|
| 設計局（例：Huff N' Puff、stage-demo） | ⑦ game.js＋odds（或 game.js 的 spec） | 本 SOP：產生 Go 第二實作，逐局對帳 |
| 還原局（例：神燈寶藏） | 線上 Server 或 ④ 快測 Go | 線上 Server 可直接連（經 slot-bot）時不產新 Go；要網頁正式版時走**第 5 節 Go → Go**：把 ④ 快測引擎整理成 `prob.Game`，與原引擎同 seed 逐局對帳 |

## 1. 七步（指令都在 aidev 根目錄執行）

| 步 | 做什麼 | 指令／產出 | 守門 |
|---|---|---|---|
| 1 | 掃抽值點：一局內向數學流取值的位置、順序、是否有條件 | `node .kiro/skills/ark-web-game/scripts/wg_draw_scan.js --game <game.js> [--odds <odds>] --n 20000 --out <草稿.md> --dump-spec <設定.json>` → 補齊成 `game/trace-map.md` | `wg_trace_check.py`（有 prob-spec 時加 `--prob-spec`） |
| 2 | 產 Server 骨架 | `python .kiro/skills/ark-web-game/scripts/wg_server_init.py --slug <slug> --engine <名稱>` → `game/go-server/`（機率模組為待移植 stub） | `go build ./...`、`go test ./internal/ark-go/`（vendored 守門） |
| 3 | 逐函式移植＋黃金比對：game.js 的 LocalService（`rng=go`）同 seed 跑 N 局存成 testdata，Go 測試同 seed 逐局比整份 SpinResult | 黃金產生器範例：`output/web-game/stage-demo-server/tools/golden.js`；測試範例：`internal/prob/stagedemo/game_test.go` | `go test ./internal/prob/<engine>/` |
| 4 | 經網路逐局對帳：起 `-dev -seed <s>`，WsService ⇄ LocalService | `node <go-server>/tools/parity.js --via ws --url ws://… --seed <s> --n 50000`（壓力版加 `--force '"feature"'`）；Server 加 `-flood-limit 100000` | ≥ 2 seed 共 ≥ 10 萬局＋壓力版，0 不一致 |
| 5 | GT 驗收：prob-spec 可解析的數字寫成 Go 測試 | `*_test.go` | 全過 |
| 6 | 接 ④：`cmd/sim` 輸出範本報告格式（路線 B） | `go run ./cmd/sim … -check <基準報告>` | rtp-report 三向 verdict confirmed |
| 7 | 交付單 | `game/handoff.md`（設定檔 sha、prob-spec 版本、rtp-report sha、P-xx → Go 映射、trace-map sha、待決） | 指紋與實檔一致 |

`wg_draw_scan --compare <trace-map.md> --alias 'JS 名=Go 名,…' --strict`：檢查每個 JS 抽值點都在 trace-map 的 Go 欄有對應。huffnpuff 的對照：`pickCombo=Engine.SpinGrid, afterGrid=Engine.trigger, groupRate=playHS, drawValue=Engine.valueOf, (匿名)@game.js:328=playOH`（8/8）。

## 2. 對齊要點（演練中確認過的易錯處）

| 項目 | 要求 |
|---|---|
| 亂數 | Go `math/rand`：`Float64() = float64(Int63()) / 2^63`（為 1.0 時重抽）。JS 用 `go-rand.js`（ark-game-proto 1.1.0 曾誤用低 53 位元） |
| 權重抽法 | Proto 通用邏輯：`r = rng × 總和`，逐項累加，`r < 累計` 即選；**只有一個選項也會抽一次**（stage-demo 的起始手數 spins: 3 也消耗一個亂數） |
| 抽值順序 | 只在條件成立時才抽，順序與 game.js 相同；不得為了好寫先抽後判 |
| 演出流 fx | LocalService 在「判獎之後、玩法之前」抽 fx（演出流，不在數學流）；Go 的 `Play(rng, fx)` 要在同一點呼叫 `fx()` |
| 取整 | 只在 Body 換算一次：`floor(x × bet + 1e-6)`；浮點加總順序與 JS 相同（payIds 順序） |
| 劇本格式 | 對帳比整份 SpinResult：`feature.script` 欄位名、`null` 與空陣列 `[]`、物件鍵為字串（例 `landed: {"7": 2}`）都要相同；`clean()` 會丟掉 `undefined` 欄位（例 `draw.group`），Go 端就不要輸出該鍵 |
| `feature.draw`／`feature.group` | JS 的 draw 物件原樣（stage-demo：`{spins, gi: null}`）；`group` 只有 draw.group 有值才是字串，否則 `null` |
| 封頂 | 照 game.js 實際行為移植，不照 spec 字面：通用鎖格重轉只讀 `feature.maxWin`，spec 頂層 `maxWin` 不會套用 → 若是 bug，回 ③／⑦ 修 game.js，兩邊一起改 |
| 設定正本 | 沒有 odds 檔的遊戲包，用 `wg_draw_scan --dump-spec` 把 game.js 的 spec 原樣輸出成 Go 設定檔；不手抄數值 |
| 不支援就拒絕 | Go 的 Parse 遇到沒移植的設定（lines、reelSets、custom、groups…）直接回錯誤，不默默近似 |

## 3. 演練數據（stage-demo，2026-10-22）

| 項目 | 數字 |
|---|---|
| 抽值點 | 3（停輪、起始手數、鎖格重轉面額／停入） |
| Go 機率模組 | 543 行（不含註解與空行 487；含設定解析、評估、玩法、Body、情境） |
| 黃金比對 | seed 7、42 各 3,000 局（玩法 16、18）第一次即 0 不一致 |
| 經 WS 對帳 | seed 7、42 各 50,000 局（玩法 300、316；分段 165、202）0 不一致；壓力版（每局強制玩法）2,000 局 0 不一致 |
| 端到端 | smoke_ws 7/7（啟動指標、一般局、玩法、分段、續玩、重連） |

## 4. 不做的事

- 不在 Go 端修 game.js 的規則；發現規則可疑時回 ③ 規格決議，兩邊一起改。
- 不改 `internal/ark-go`。
- 不在 Server 回應或局號放 seed。

## 5. 還原局：④ 快測 Go 引擎 → prob.Game（Go → Go，0.9.0）

> 首例：神燈寶藏（2026-10-23，ND-ML-2）。數學正本是 ④ 快測引擎（線上參數）；不從 ⑦ game.js 抽，避免浮點亂數與 Go 不同流。

| 步 | 做什麼 | 指令／產出 | 通過條件 |
|---|---|---|---|
| 1 | 產骨架 | `wg_server_init.py --slug <slug> --engine <pkg> --game-id <id>`（含 Dockerfile、.dockerignore、tools/smoke_ws.js） | `go build ./...` |
| 2 | odds 檔 | 引擎加 `cmd/dump` 傾印 ProbSetting → `tools/gen_odds.py` 包 `_meta`（引擎 odds.go sha16）＋`client`（符號碼、押注、玩法名、JP 名）→ `configs/odds_<profile>.json` | `Load` 擋掉道具卡、保底、未實作開關 |
| 3 | 移植 | 照引擎 `GameProcess` 一行一行搬：抽值函式與順序完全相同（`GetIndexByWeight`＝`Intn(總和)+1` 後 `SearchInts`；停輪＝`Intn(len)`）；拿掉 recorder、全域狀態；數學流用 `*rand.Rand` 的 `Intn`（prob.Rand 只宣告 Float64，於 Play 內型別斷言） | — |
| 4 | 參考軌跡 | 引擎副本加 `cmd/trace`（`rand.Seed(seed)`、每局輸出 總贏分／主遊戲贏分／停輪／FG 組別／手數；需 `GODEBUG=randseednop=0`，Go 1.24 起 Seed 預設無效）；Server 加 `cmd/parity` 同格式 | `cmp` 逐位元相同：2 seed × 10 萬局＋FG ≥ 2,000 次 |
| 5 | 回歸 | `cmd/sim -n 20000000 -check`（RTP 在 ④ ± 3 SD/√n） | 通過 |
| 6 | 劇本 | `feature.script` 欄位照 ⑦ game.js record（Stage Presenter 可直接播 Server 結果）；金額以 Bet_Cost 為基準、用戶端 × bet ÷ Bet_Cost | `smoke_ws` 全過 |
| 7 | 測試 | golden（前 3,000 局參考軌跡）、record 不改亂數流、劇本加總、SpinResult 驗證、每個開發情境找得到；局服務與 HTTP／WS 測試由參考 Server 複製後改押注 | `go test -race ./...` |

神燈寶藏數據：同 seed 60 萬局（FG 2,900 次）0 不一致；2,000 萬局 RTP 99.91%（④ 100.05% ± 0.85%）；Stage 經 WS 冒煙 10／10。

易錯：引擎在新最大倍數時 `fmt.Println`（參考軌跡要把 stdout 換掉）；SC 升框掃描順序是「列外層、軸內層」（只影響 ups 順序，不影響數學）；`GuarenteeSpinNum` 與計數器關閉時不會觸發，但要在 Load 擋掉開啟狀態。
