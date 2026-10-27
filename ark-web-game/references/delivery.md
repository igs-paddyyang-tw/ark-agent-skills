# 交付：分包、Manifest、雜湊、發布、指標

> 來源：web-game-client-architecture-plan §5～§8、dev-tech §6、§7、§9、§11。知識頁：W-008。

## 1. Bundle

- 依「玩家什麼時候用到」分組，不依美術資料夾。命名 `<gameKey>-<用途>`。
- 老虎機建議：`boot`（必要）、`<key>-core`（必要：背景、HUD、符號、轉輪、基本報獎）、每個玩法一個（非必要、進場後背景預載）、`<key>-jackpot`、`<key>-audio`、`<key>-highres`。
- 結果先決的好處：收到 SpinResult 時就知道要不要玩法素材，停輪動畫期間就是預載窗口；未就緒播過渡，不可破圖。

## 2. 兩種 Manifest

| | 格式 | 產生者 |
|---|---|---|
| Assets Manifest | PixiJS `{bundles:[{name, assets:[{alias, src}]}]}` | 建置（AssetPack 或 stage_build `--bundles`） |
| Release Manifest | 見下 | `wg_release.py pack` |

```json
{ "schema": "web-game-release/1", "releaseId": "<key>-<ver>+<hash7>", "gameId": "...", "gameVersion": "1.0.0",
  "runtimeApi": "^1.0.0", "protocol": {"result": "proto-stage-result/1", "info": "proto-stage-info/1", "wire": "ark-wire/1"},
  "manifestHash": "sha256:...", "bundles": [{ "name": "huff-core", "requiredForPlayable": true, "hash": "sha256:...", "bytes": 0,
  "files": [{ "path": "...", "sha256": "...", "bytes": 0 }] }], "unassigned": [], "status": "candidate" }
```

- 雜湊一律對**實際位元組**計算；bundle hash = 依路徑排序的 `path\tsha256` 行再取 sha256。
- 同一檔案不得屬於兩個 bundle（pack 失敗）；沒被分到的檔案列在 `unassigned`。

## 3. 指令

```bash
python .kiro/skills/ark-web-game/scripts/wg_release.py pack --dir <建置資料夾> --bundles <bundles.yaml|json> \
    --game-id <id> --game-key <key> --version 1.0.0 [--runtime-api ^1.0.0] [--out <dir>/release.json]
python .kiro/skills/ark-web-game/scripts/wg_release.py verify --dir <資料夾> --release <release.json>
```

bundles 設定（與 stage.yaml `bundles:` 同格式）：

```yaml
huff-core:      { required: true,  include: ["assets/core/**"] }
huff-openhouse: { required: false, include: ["assets/openhouse/**"] }
```

## 4. 發布

上傳不可變路徑 → 下載回來 verify → Candidate → 測試環境 → 灰度（`hash(arkId) % 100 < percent`）→ Stable；異常切回上一個 Stable。只有 Release Pointer 可變。協定改主版號時，Server 要先支援新舊兩版。

## 5. 指標

`time_to_playable_ms`、`manifest_fetch_ms`、`core_bundle_download_ms`、`core_bundle_parse_ms`、`cache_hit_ratio`、`asset_download_fail_rate`、`bundle_integrity_fail_rate`、`game_start_fail_rate`、`background_load_completion_rate`、`spin_rtt_ms`、`reconnect_count`、`protocol_mismatch_count`。看 P50／P75／P95。

初值預算：boot ≤ 200 KB（gzip）；必要 Bundle 合計 ≤ 3 MB；`time_to_playable_ms` P75 ≤ 4 秒（4G、中階 Android、未快取）。

量測（2026-10-22，Huff N' Puff；細節見知識庫 raw `2026-10-22-asset-measure-baseline`）：

| 項目 | 數字 | 對預算 |
|---|---|---|
| 正式 Client 程式（pixi chunk＋遊戲碼） | 513,790 B（gzip 約 151 KB） | 在 boot 預算內 |
| huff-core（必要） | 原 PNG 2,042,966 B；WebP q82 294,508 B | 在 3 MB 內；正式版用 WebP |
| huff-feature＋huff-audio（背景） | WebP 342,046 B＋音效 227,167 B | — |
| time_to_playable_ms | 本機 98 ms（佔位圖） | 實機待量（計畫 5.8），之後再修訂預算 |

```bash
python .kiro/skills/ark-web-game/scripts/wg_measure_assets.py --slug <slug> --check [--out <json>]   # 有原檔量原檔，否則量單檔建置內嵌
```

## 6. 容器發佈（本機測試環境）

> 參考實作：huffnpuff（`data/web-game/pixi-game-platform/deploy/huffnpuff/`），設計與手冊見 `docs/designs/2026-10-22-web-game-docker-deploy-design.md`、`docs/2026-10-22-web-game-docker-deploy-manual.md`；事實見知識庫 raw `2026-10-22-docker-deploy-notes`。

- 兩個映像：Server（Go 靜態檔、alpine、非 root、HEALTHCHECK `/healthz`）；Client（node 建置＋測試 → nginx）。只對外開 web 一個埠。
- 素材與 odds 用 BuildKit `additional_contexts` 帶入，不複製進程式碼樹；缺 `manifest.json` 建置失敗。
- nginx：`/ws` 走 Upgrade、逾時大於 Server 閒置秒數；index、manifest、release no-cache，雜湊檔 immutable；**不要在 server 區塊寫 `types {}`**（會蓋掉整張 MIME 表）。
- Client 預設連同站 `/ws`；每個瀏覽器自產訪客 arkId，避免 KickSameID 互踢。
- 對外測試用 cloudflared Quick Tunnel（compose profile）；Server 是 `-dev`，測完即停。正式環境另走 §4 與設計文件第 8 節。
- 多款並存：每款一個 `deploy/<game>/`（compose 專案名＝遊戲），Web 埠錯開（豬來蓋福 3030、神燈寶藏 3031）。還原局 odds 放 go-server `configs/`、映像不推外部 registry（R-3）。
