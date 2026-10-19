---
name: ark-game-proto
description: |
  機率規格書 → 可玩 H5 slot 驗證雛型（PixiJS 8）executor：遊戲開發製程 C 段的「演出驗證」，接在 ark-game-prob（prob-spec.md）之後。
  deterministic：① proto_build 把 prob-spec.md（ark-game-prob 1.4+ 格式）經玩法 adapter 編成 game-config.json（每個參數帶表編號來源、規格缺口 gaps、§2 驗證目標）；
  ② 產單檔 index.html：PixiJS 轉輪 / 連線 / FG 或 Bonus 演出 + 驗證台（L1 精算對 §2、L2 Web Worker 蒙地卡羅、規格缺口回驗、Go 對照、單局抽表軌跡、seed 重現、情境搜尋）；
  ③ --go-config 規格書 ⇄ Go 快測設定檔逐鍵對照並補規格書缺的值；④ go_parity 以 Go math/rand 逐位元移植與 Go 快測引擎同 seed 逐局對照。
  內建玩法模型：collect-mult（彌勒佛）、coin-lock（金幣鎖格、JACKPOT）。
  1.1 起附「正式演出版型」Stage（scripts/stage）：Proto 遊戲包 game.js（數學零修改）→ PixiJS 8 演出 + Pixi HUD，結果只經 GameService 取得
  （Local 瀏覽器內引擎 / Http 經 slot-bot 接 Go 機率 Server / Replay 重播），SpinResult JSON Schema、整數金額。
  使用此 skill 當提及：機率雛型、slot 雛型、H5 雛型、PixiJS slot、演出驗證機率、規格書做成可玩版本、試玩機率、
  規格缺口、規格書對 Go 引擎、逐局對照、seed 重現、FG 演出、Bonus 演出、驗證台、正式演出版型、Stage、試玩改 PixiJS、GameService、SpinResult、接 Go Server。
  不適用於：寫機率規格書本身（→ ark-game-prob）、跑 Go 快測 / 三向 verdict（→ ark-game-quicktest）、正式上線前端或美術、
  一般網頁 / dashboard（→ ark-html-dashboard）；Stage 不含帳務 / session（slot-bot server 負責）。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "1.1.2"
  updated: 2026-10-19
  outputs:
    - { format: data, audience: ai }
    - { format: html, audience: human }
  render: html
  depends_on: [ark-game-prob, ark-game-quicktest]
---

# ark-game-proto — 規格書直接編成可玩雛型，同一顆引擎演出給人看、精算給機器驗

一句話：**雛型是「第二個實作者」**——只讀 prob-spec.md 重做一次引擎；算得回 §2 快測數字、和 Go 引擎同 seed 逐局一致，
才代表規格書寫得夠完整；算不回來的地方就是規格缺口（gaps），雛型把它標出來、推定、回驗、附 Go 證據。

> 製程位置：ark-game-prob（C1 prob-spec.md）⇄ ark-game-quicktest（C2 Go 快測）→ **ark-game-proto（C3 演出驗證雛型）**。
> 試點：彌勒佛（xlsx 模式）精算總 RTP 99.85% vs 規格 99.94%、Go 逐局 4,020 萬手 0 差異；Tiger and Dragon（qt 模式）約 96.3%（Bonus 抽樣估計）vs 96.49%、2,030 萬手 0 差異。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| ark-game-prob 1.4+（其 ps_mdview）| proto_build 讀 md | 找不到即退出；設 `ARK_GAME_PROB_SCRIPTS` 或從 repo 根目錄執行 |
| prob-spec.md 含附錄 ```strip 帶面 | proto_build | 舊格式會明確報錯：先用 ark-game-prob `ps_run` 重產（人工區保留）|
| node 18+ | tests、go_parity | 只影響測試與逐局對照 |
| go 1.20+ + 該款 Go 快測引擎 | go_parity | 只影響逐局對照 |
| 瀏覽器 | index.html | PixiJS 走 jsDelivr，失敗退 `vendor/pixi.min.js`；`--inline-pixi` 產離線單檔 |

## 資產地圖（先讀這張表再動工）

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/proto_build.py` | md → `game-config.json` → `index.html`；`--go-config` 逐鍵對照 + 補缺值；`--go-parity` 內嵌逐局對照結果；`--config-only`；`--inline-pixi`；`--strict`（不一致 exit 3）| 平常只跑這支 |
| `scripts/proto_common.py` | 讀 md（ps_mdview）、通用段（盤面 / Pay table / Strip）、§2 驗證目標、表格小工具 | 改通用解析 |
| `scripts/adapters/<adapter>.py` | 玩法語意：`build()` 表格 → config、`GAPS`（推定 + 回驗 + Go 證據）、`targets_extra()`、`go_rules()` / `go_fill()` | 新玩法加一支；見 `references/adapter-guide.md` |
| `scripts/src/slot-core.js` | 數學核心（純函式，瀏覽器 / Worker / node 共用）：RNG 分流、`spin`、`exact`（L1）、`simulate/report`（L2）、`findSeed`；玩法模型 `MODELS[...]` | 改規則或加模型 |
| `scripts/src/go-rand.js` | Go math/rand（rngSource + Intn）逐位元移植 | 逐局對照 |
| `scripts/src/app.js`、`art.js`、`template.html` | 驗證台 + PixiJS 演出層；SVG 佔位美術（名稱 = 規格符號代碼，`cfg.art` 選套）| 改演出 / 換美術 |
| `scripts/go_parity.py` + `scripts/goparity/<model>_trace.go` + `scripts/tests/go_parity.js` | 暫存複本注入 trace → go run → JS 同 seed 逐局比 | 規格書或引擎改版後 |
| `scripts/tests/` | `test_proto_build.py`（兩款 golden、Go 對照、單檔 html）、`core_test.js`（決定性 / 演出不改結果 / 模型一致性 / 精算對 §2）| 改腳本後 |
| `references/architecture.md` | 四層架構、三原則、SpinResult / config 契約、驗證三層 | 第一次用或改架構 |
| `references/adapter-guide.md` | 寫 adapter / 加玩法模型 / 加 Go trace 的步驟與檢查表 | 新遊戲 |
| `references/go-parity.md` | 逐局對照原理（RNG 移植、抽值順序、封頂語意）與排錯 | 對照出差異時 |
| `assets/slot-proto-arch.svg` | 架構圖 | 文件 / 簡報 |
| `scripts/stage/` | **Stage 正式演出版型（1.1）**：`runtime/`（core / service / slot / features，載入順序見 `runtime/manifest.json`）、`schema/spin-result.schema.json`、`stage_build.py`（資料夾 / `--single` 單檔 / `--serve`）、`tests/`（stage_test.js、test_stage_build.py、mock_server.js、smoke.js）| 做正式演出、遷移 Proto 試玩、接 Server；先讀 `references/stage-architecture.md` |
| `references/stage-architecture.md`、`stage-game-pack.md`、`stage-api.md` | Stage 分層與檔案、遊戲包契約與遷移指南、slot-bot HTTP 契約 | 對應工作 |
| `golden/stage-demo/game.js` | Stage 無版權示範遊戲包（Ways + 鎖格重轉、佔位美術）| Stage 回歸基準 |
| `golden/milefo/`、`golden/tiger-and-dragon/` | 兩種模型的輸入 md、Go 設定檔、parity 記錄、期望 config | 回歸測試基準 |

## 決策樹

```
手上有什麼？
├─ prob-spec.md（1.4+）且玩法已有 adapter（milefo / tiger_dragon）
│   python scripts/proto_build.py --md <prob-spec.md> --adapter <a> --out output/slot-proto/<slug> [--go-config <Go 設定檔>]
│   └─ 開 index.html：L1 全 PASS → 規格書數學完整；有 FAIL → 看「規格缺口」分頁
├─ 新遊戲、玩法近似既有模型 → 照 references/adapter-guide.md 寫 adapters/<slug>.py（只寫表格語意 + GAPS）
├─ 新玩法機制（既有模型裝不下）→ slot-core.js 加 MODELS['<model>']（play / present / statsAdd / groupReport）+ EXACT_FG + goparity/<model>_trace.go
├─ 有 Go 快測引擎 → python scripts/go_parity.py --engine … --go-config … --game-config … --seed 42 --n 200000 --out parity.json
│   └─ 差異 ≠ 0 → references/go-parity.md 排錯（多半是抽值順序或封頂語意）；0 差異 → proto_build --go-parity parity.json 內嵌
└─ 舊 md（無 ```strip）→ 先 ark-game-prob ps_run 重產
```

### Stage（正式演出版型）

```
手上有 Proto 試玩模板的 game.js（或新遊戲照 stage-game-pack.md 寫）
├─ 遷移：複製 game.js → 數學段不動、演出段改 Pixi（features[type].Stage、presentation.stage）
├─ data/slot/<slug>/game/pixi-client/{game.js, stage.yaml} → python scripts/stage/stage_build.py --slug <slug> [--folder | --serve]
│   → output/slot/<slug>/game/pixi-client/single/index.html（單檔）＋ data/.../stage-build.json 清冊（佈局契約 v3 ⑦；任意路徑用 --game --out）
│   └─ 開 index.html：?seed= 重現、?rng=go 用 Go Float64 流；除錯「強制」分頁 = 搜尋真 seed；「服務」分頁錄製 / 重播軌跡
├─ 驗：node scripts/stage/tests/stage_test.js --game <新> --orig <原>（結果一致 / 契約 / 分層 / Http）；smoke.js 截圖 0 error
└─ 接 Server：node scripts/stage/tests/mock_server.js --game <game.js> → ?service=http&base=…&game=…&dev=1；契約 references/stage-api.md
```

## 守門

| 規則 | 條件 | 嚴重度 |
|------|------|--------|
| L1 精算 | RTP 類 \|精算−§2\| ≤ 容許（§2 容許誤差，預設 0.2 pp）；平均類相對 ≤ 1–5% | 驗證台紅 / 綠 |
| L2 模擬 | \|模擬−精算\| ≤ 95% CI | 驗證台 |
| 規格缺口 | 每條 gap 必有 推定 + 回驗方式；有 Go 證據標「Go 已證」| 交付必列 |
| Go 設定檔對照 | `--strict` 下 mismatch > 0 | exit 3 |
| 逐局對照 | mismatch > 0 | exit 1 |
| 演出不改結果 | 同 seed present / 非 present 結果必一致（core_test）| 測試失敗 |

| Stage 結果一致 | LocalService 與 Proto Logic 同 seed 10 萬局 total 倍數差 ≠ 0 | stage_test 失敗 |
| Stage 契約 | SpinResult 不過 Schema（含浮點金額、帳不平）| 不播放、不改餘額 |
| Stage 分層 | 演出層呼叫 slotLogic 抽值函式或 Math.random | stage_test 失敗 |
| Stage 單檔 | `--single` 超過 `--budget-mb`（預設 15）| exit 3 |

## 邊界

- **規格書是唯一來源**：Go 設定檔只用來對照、以及補規格書缺的值（標來源 + 記 gap），不覆蓋規格書已有的值。
- **結果先決、演出後演**：`spin()` 一次算完；演出只讀 SpinResult；「強制情境」= 搜尋真實 seed，不存在改結果的後門。
- **數學 RNG 與演出 RNG 分流**：假轉分數、聽牌、出場順序、復活這類演出抽選不吃數學流。
- **抽值順序 = Go 引擎順序**：改順序會破壞逐局對照；新模型照 Go 程式的呼叫順序寫。
- **驗證台不是正式前端**：美術是程式產生的 SVG 佔位圖、無音效、無帳務；不仿任何原廠美術 / 商標。
- **Stage 是正式演出版型，但不含帳務 / session**：餘額只顯示 GameService 回傳值（Http 模式由 slot-bot server 權威）；美術來自遊戲包素材，競品裁圖只供內部參考、不入 skill 與 data。
- **Stage 數學零修改**：遊戲包的 `CFG` 與玩法 logic 與來源逐字相同，演出層零抽值；兩者由 `stage_test.js` 的 parity-src 與 layering 兩項檢查把關。
- **不做 Go 快測**：L2 約 1M 手/秒，千萬手級驗收仍走 ark-game-quicktest。

## 版本

| 版本 | 日期 | 內容 |
|---|---|---|
| 1.1.2 | 2026-10-19 | stage_build 支援機率設定檔：`stage.yaml` 的 `odds:`（或 `--odds`）→ 在 game.js 前注入 `globalThis.HUFF_ODDS`（單檔內嵌／資料夾 odds.js；壞 JSON 擋下；清冊記 odds sha16）；stage-game-pack 補遊戲包 odds 模式寫法。試點 HuffNPuff 交付物 index.html 與 Go 引擎同 seed 2 萬局 0 不一致 |
| 1.1.1 | 2026-10-16 | 修正 `?rng=go` 數學流：Go `Float64()` 是 `float64(Int63())/2^63`（1.1.0 誤用低 53 位元，與真 Go 不同流）；gorand 測試改用 Go 實跑黃金值；stage-api 補 Go Server 雛型 |
| 1.1.0 | 2026-10-16 | 新增 Stage 正式演出版型（`scripts/stage/`）：PixiJS 8 演出 + Pixi HUD、GameService（Local / Http / Replay / Recorder）、SpinResult Schema `proto-stage-result/1`、`stage_build.py --slug`（佈局契約 v3 ⑦ `game/pixi-client`）、mock slot-bot server、go-rand Float64 數學流；golden `stage-demo`；試點 Huff N' Puff Open House |
| 1.0.0 | 2026-10-15 | 驗證雛型 skill 化：proto_build、collect-mult / coin-lock、go_parity 逐局對照 |
