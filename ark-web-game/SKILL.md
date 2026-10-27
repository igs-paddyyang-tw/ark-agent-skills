---
name: ark-web-game
description: |
  網頁遊戲 ⑦⑧ 工程 skill：把「單機試玩版」做成「Server 算結果、網路傳送、PixiJS Client 只演出」的網頁遊戲。
  涵蓋五件事：單局結果契約（RoundOutcome → SpinResult、抽選點對照表 trace-map）、網路（Go 網路層 wire 協定、
  GameService／WsService／HttpService、冪等、斷線續玩、協定版本協商）、⑧ 抽離（把 ⑦ game.js 的數學移植成
  Go prob.Game，逐局對帳 0 不一致）、Go Server 範本、交付（資源分包、Release Manifest、雜湊驗證、灰度回滾、
  啟動指標）。每次使用都讀 knowledge/webgame 的知識頁，做完把新事實回寫知識庫、把新做法回寫 references 與 scripts。
  使用此 skill 當提及：網頁遊戲、web game、H5 遊戲、game.js 抽離、抽成 Go Server、⑧ Game Server、單機換連線、
  local 換 network、WsService、wire 協定、WebSocket 協定、SpinResult 傳輸、抽選點對照表、trace-map、斷線續玩、
  pending／ack、協定版本、Release Manifest、資源分包、bundle、灰度發布、回滾、time_to_playable、正式 Client、
  pixi-game-platform。
  不適用於：Stage 演出版型本身與 ⑥ 驗證台（→ ark-game-proto）、機率規格書（→ ark-game-prob）、
  Go 快測與 RTP 模擬（→ ark-game-quicktest）、上線成效（→ ark-game-report）、一般網頁或 dashboard（→ ark-html-dashboard）。
metadata:
  schema_version: "1.2"
  status: experimental
  author: paddyyang
  category: scaffolder
  form: executor
  domain: game
  version: "0.11.1"
  updated: 2026-10-27
  outputs:
    - { format: data, audience: ai }
    - { format: md, audience: both }
  render: none
  depends_on:
    - { name: ark-game-proto, version: "^1.4.0" }
    - { name: ark-wiki-engine, version: "^3.0.0" }
---

# ark-web-game — 網頁遊戲 ⑦⑧ 工程

一句話：**結果在 Server 算完，Client 只演出；數學只有一份來源，第二份實作靠逐局對帳證明。**

> 製程位置：slot AI 開發十階段的 ⑦ 遊戲試玩版（連線化）與 ⑧ Game Server。承接原規劃的 `ark-game-code`（佈局契約 ⑧「規劃中」）。
> Stage 演出版型的程式仍在 ark-game-proto；本 skill 定義它要接的網路、契約與 Server，並負責正式 Client。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| Python 3.10+、`pyyaml` | 全部腳本 | exit 8；bundles 設定改用 JSON 仍可跑 |
| ark-game-proto（同層） | SpinResult schema、Stage runtime、parity 工具 | wg_trace_check 需 `--schema` 指定 schema 路徑 |
| ark-wiki-engine（同層）＋ `knowledge/webgame/` | 讀知識頁、回寫後的守門 | 只能讀 references，不能回寫知識 |
| Go（go.mod 版本）、node 22 | Server、對帳、冒煙 | 只能做文件與清單類工作 |
| pnpm 10、Playwright（Chromium） | 正式 Client 建置與 e2e | wg_client_init 仍可產骨架；不能建置與跑 e2e |

## 資產地圖

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `references/architecture.md` | 雙軌（Stage 試玩／正式 Client）、四段模組（機率／局服務／網路／Client）、子系統與依賴方向 | 任何設計或改動前 |
| `references/result-contract.md` | 單局兩層契約 RoundOutcome → SpinResult、取整、`feature.script`、trace-map 格式 | 動到結果、新遊戲、抽離 |
| `references/wire-protocol.md` | ark-go wire 封包、auth、sn、alive、sys `slot` 指令、分段、錯誤碼表、協定協商 | 寫 WsService、改 Server API |
| `references/extraction-sop.md` | ⑧ 抽離：game.js 數學 → Go `prob.Game` 七步與守門；設計局與還原局的差別 | 新遊戲走到 ⑧ |
| `references/delivery.md` | 資源分包、Assets／Release Manifest、雜湊、灰度回滾、啟動指標與預算 | 建置、發布、量測 |
| `references/kb-loop.md` | skill＋知識庫回寫規則：什麼寫 references、什麼寫 raw／wiki、守門指令 | 每一期收尾 |
| `references/client-vertical-slice.md` | 正式 Client：骨架產生、Stage → TS 移植對照、e2e 五情境、兩軌重播一致（present-events） | 建正式 Client、新遊戲上正式版 |
| `scripts/wg_trace_check.py` | 檢查 trace-map：表格六欄完整、SpinResult 欄位存在於 schema、prob-spec 的 P-xx 參數全有對應 | 產出或修改 trace-map 後 |
| `scripts/wg_release.py` | `pack`：依 bundles 設定由資料夾產 Release Manifest（每檔 sha256、bytes）；`verify`：重算比對 | 建置後、上傳前、上傳後 |
| `scripts/wg_measure_assets.py` | 量素材大小並依 bundles 分組（原檔或單檔建置內嵌兩種來源）；`--check` 驗合計與不重疊 | 定 Bundle 與預算前 |
| `scripts/wg_draw_scan.js` | ⑧ 第 1 步：掃 game.js 抽值點與順序 → trace-map 草稿；`--dump-spec` 輸出設定正本；`--compare` 對既有 trace-map | 抽離開始、改 game.js 數學後 |
| `scripts/wg_server_init.py` | 由 `assets/go-server-template` 產 Go Server 骨架；`--sync-template` 由參考 Server 更新範本 | ⑧ 第 2 步 |
| `scripts/wg_pack_assets.py` | 正式 Client 素材打包：依遊戲 `assets.yaml`（schema pgp-assets 第 1 版）讀 git 裡的 L2 素材（成品 WebP、ogg＋m4a 直通，位元組不變），產 PixiJS manifest 與 release.json（並 verify）；`--regen`＋`--export` 由產生器重產並凍結回 L2 | 建置前（Docker 映像內也會跑）；美術改版時 |
| `scripts/wg_svg_render.mjs` | 瀏覽器（Playwright Chromium）SVG → PNG；wg_pack_assets 沒有 cairosvg 或 `--svg-engine browser` 時呼叫 | 由 wg_pack_assets 呼叫 |
| `scripts/wg_client_init.py` | 由 `assets/client-template` 產正式 Client monorepo 或加一款遊戲；`--sync-template` 由參考 Client 更新範本 | 建正式 Client |
| `assets/go-server-template/` | Go Server 範本（ark-go 複本、api、round、result、prob 介面；34 檔） | wg_server_init 使用，勿手改 |
| `assets/client-template/` | 正式 Client 範本（shared-types、ark-wire、game-service、遊戲 runtime／controller／轉輪） | wg_client_init 使用，勿手改 |
| `scripts/tests/test_wg.py` | 上述腳本與資產完整性測試 | 改腳本或 references 後 |

## 工作流程

```
新遊戲或改動
├─ 先讀：knowledge/webgame/index.md → 相關 wiki 頁；本 skill references 對應章
├─ ⑧ 抽離（設計局：game.js 有數學、還沒有 Go）
│   └─ references/extraction-sop.md 七步：trace-map → Server 骨架 → 逐函式移植 → 對帳 → GT → 接 ④ → handoff
│       守門：wg_trace_check、parity 0 不一致、go test -race
├─ ⑦ 連線（Stage 或正式 Client 改向 Server 取結果）
│   └─ references/wire-protocol.md：WsService／HttpService、pending／ack、協定協商；對帳 WsService ⇄ LocalService
├─ 還原局（Go 已在線上或快測）
│   └─ 不產新 Go；⑦ 改連既有 Server（經 slot-bot），對帳改用 ⑥ 同流或 Go trace 重播
├─ 正式 Client
│   └─ references/client-vertical-slice.md：wg_client_init → 設定與 Presenter → 素材（assets.yaml → wg_pack_assets）→ e2e（真 Server）→ trace-parity
├─ 交付
│   └─ references/delivery.md：wg_measure_assets → bundles → wg_release pack → 上傳 → wg_release verify
├─ 資安（每款都做，0.11.1；事實與踩雷見 knowledge/webgame/raw/2026-10-23-web-game-security-hardening.md「新遊戲開發時的資安檢查點」）
│   ├─ 開新遊戲：deploy/<game> 從既有遊戲複製（compose.yaml＝dev、compose.release.yaml＝release、nginx.conf 已含 security-headers）；
│   │   Server 映像預設 CMD 不帶 -dev、Client 正式 build 不產 source map（範本已是安全預設，不要改回）
│   ├─ ⑧ 測試環境（S-3）：python tools/sec_check.py --game <slug> [--client <名>] --base http://localhost:<埠> --profile test → 0 FAIL
│   └─ 上線前（S-9）：同指令 --profile prod（讀 compose.release.yaml）→ P0／P1 無 FAIL 才放行；人工項目照規格 §5 勾
└─ 收尾（每次都做）
    └─ references/kb-loop.md：事實 → knowledge/webgame/raw → wiki；做法 → references／scripts；升版號
```

## 守門

| 項目 | 條件 | 不過怎麼辦 |
|------|------|-----------|
| trace-map | `wg_trace_check` exit 0 | 補列抽選點、修正欄位名 |
| 抽離對帳 | 正式設定 ≥ 2 seed 共 ≥ 10 萬局、壓力版、不給設定守門，整份 SpinResult 0 不一致 | 依第一個不一致的局號回頭比對抽值順序 |
| Server | `go test ./... -race`、vendored 守門（`internal/ark-go` 不得就地修改） | 修程式，不改守門 |
| 契約 | 每局通過 SpinResult schema；金額全為整數 | 修 Builder，不放寬 schema |
| 資安（開發期） | `tools/sec_check.py --profile test` 0 FAIL（S-3 測試環境） | 照報告修設定；不要為了過關改檢查 |
| 資安（上線前） | `tools/sec_check.py --profile prod` P0／P1 無 FAIL；規格 §5 人工項目已勾（S-9） | 補 `compose.release.yaml`、映像預設、source map、nginx 標頭；擋下不上線 |
| 正式 Client | `pnpm -r typecheck／test／build` 全過；e2e main／features／pending／protocol 全過；trace-parity 事件逐筆相同 | 依第一筆不同的事件回頭查演出流程 |
| 發布 | `wg_release verify` exit 0 | 重新建置，不手改 release.json |
| 回寫 | 知識庫 guard／taxonomy／lint 0 errors、索引 fresh；skill 測試與 prompt_lint 通過 | 收尾未完成，不升版號 |

## 規則

- **數學只有一份來源**：設計局以 ⑦ game.js（＋ odds）為準，Go 是第二實作；還原局以線上或快測 Go 為準。不准兩邊各改各的。
- **抽值順序是契約**：Go 與 JS 必須以相同順序向數學亂數流取值；演出用的亂數只吃 `fx`。
- **Client 不算錢**：餘額、贏分只顯示 Server 回傳值；正式 Client 不帶數學程式。
- **不改 vendored 網路層**：ark-go 複本由 `tools/vendorsync` 同步，有問題回報上游。
- **seed 不出 Server**：回應與局號都不得含數學 seed。
- **事實寫知識庫、做法寫 skill**：同一內容不在兩處複製，互相連結。
- **正式 Client 只用原創或授權素材**：競品裁圖、截圖只供內部參考（Stage），不美化、不臨摹、不打包進正式 Client。
- **可出貨素材進 git，出貨位元組＝git 裡的檔**（0.10.0 素材版控分層 L1～L4）：美術成品在 `data/slot/<slug>/art/`、共用音效在 `pixi-game-platform/shared/sfx/`；內部參考只在 `analysis/source/manifest.json` 登錄；output 只放重產物。乾淨 clone 要能直接 `docker compose build`。

## 版本

| 版本 | 日期 | 內容 |
|---|---|---|
| 0.11.1 | 2026-10-27 | 資安進開發流程（Paddy：下次開發要注意資安）：決策樹加「資安」分支（開新遊戲、⑧ 測試環境、上線前三個檢查點）、守門表加資安兩列；`tools/sec_check.py` 進 client-template（新平台一開就有），`--game` 不再限兩款、可加 `--client` |
| 0.11.0 | 2026-10-27 | 上線前資安三件（2026-10-23 資安快測 prod 4 FAIL → 0）：範本預設安全——`wg_server_init` 產的 Server 映像預設 CMD 不帶 `-dev`（fail closed）、client-template vite 正式 build 不產 source map（`PGP_SOURCEMAP=1` 才產）；兩款加 `compose.release.yaml`、nginx `security-headers.conf`＋`server_tokens off`；delivery §6 補 dev／release 分開與 nginx add_header 繼承陷阱；測試 17 |
| 0.10.0 | 2026-10-27 | 素材版控分層（Paddy 拍板，佈局契約 v3.8）：`wg_pack_assets` 來源順序 override → --set → dir → env → generator，成品 WebP 與同名音效直通（兩款重打包 releaseId 不變、位元組相同），`--regen`／`--export` 凍結美術成品；兩款美術成品進 `data/slot/<slug>/art/`、共用音效進 `shared/sfx/`；`Dockerfile.client` 建置內打包（不依賴 output）；client-template assets.yaml 改 L2 寫法；delivery §6、client-vertical-slice §6 更新；測試 16 |
| 0.9.2 | 2026-10-27 | metadata：category `executor` → `scaffolder`（schema 1.2 三軸：executor 是形態、已由 `form: executor` 表示；主要產出是 Server／Client 骨架與發版清單），無行為變更（上游 r7） |
| 0.9.1 | 2026-10-27 | 首次推上游：description 去掉 `ark-go`／`ark-game-code` 字樣（audit dangling-desc-ref P1：description 裡的 ark-* 會被當成 skill 名；ark-go 是 Go 網路模組、ark-game-code 是原規劃舊名），正文說明不變 |
| 0.9.0 | 2026-10-23 | 第二款神燈寶藏（還原局）：extraction-sop §5 Go → Go 路線；`wg_trace_check` 支援還原模式表號（### 表 X-n）；Server 範本加 Dockerfile／.dockerignore／tools/smoke_ws.js；Client 範本同步訪客 arkId 與 PresenterCtx.reels（玩法在主轉輪逐手停輪）；delivery §6 第二款 Web 埠 3031 |
| 0.8.0 | 2026-10-22 | 階段報告 A-6、A-7：`wg_pack_assets --svg-engine auto／cairo／browser`＋`wg_svg_render.mjs`（兩種轉圖尺寸一致測試）；正式 Client e2e 通用化（`e2e/e2e.mjs`＋`e2e.config.json`），收進 client-template |
| 0.7.0 | 2026-10-22 | 素材接入：`wg_pack_assets.py`（WebP、ogg＋m4a、manifest、release verify）＋測試；client-template 加 AssetLoader／AudioManager／Art 與 assets.yaml 範本；client-vertical-slice §6 素材與原創美術規則 |
| 0.6.0 | 2026-10-22 | P5：`wg_client_init.py`＋`assets/client-template`；references/client-vertical-slice.md；result-contract §3 present-events/1；wire-protocol §7 實測事實；architecture 現況與正式 Client 套件 |
| 0.5.0 | 2026-10-22 | P4：`wg_draw_scan.js`；extraction-sop 定版 1.0（stage-demo 演練：10 萬局＋壓力版 0 不一致） |
| 0.4.0 | 2026-10-22 | P3：`assets/go-server-template`（34 檔）＋`wg_server_init.py`；huffnpuff go-server 改 prob.Game 註冊表＋局服務 |
| 0.3.0 | 2026-10-22 | P2：配合 ark-game-proto 1.5.0（WsService、pending／ack、bundles、啟動指標）；wg_release 略過 stage-build.json |
| 0.2.0 | 2026-10-22 | P1：`wg_measure_assets.py`；決策紀錄 ND-1～ND-6（暫定） |
| 0.1.0 | 2026-10-22 | 初版：references 六份（由 2026-10-22 單局網路化 spec／design、網頁遊戲 Client 架構／系統分析／開發技術、一致性報告濃縮）；`wg_trace_check.py`、`wg_release.py`＋測試；搭配新知識庫命名空間 `knowledge/webgame/`；試點 huffnpuff trace-map |
