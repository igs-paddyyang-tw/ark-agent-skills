# bundle 契約（ark-game-spec 2.2）

把「競品分析報告（md）」與「正式遊戲規格書（gdd-pack 素材總覽）」合成**一份圖文自包含、檔案小的單檔 HTML**。
腳本：`scripts/bundle/gs_bundle.py`；入口：`gs_run --stage bundle --bundle <bundle.yaml>`。

## bundle.yaml

路徑一律相對於 bundle.yaml 所在目錄。

| 欄位 | 必填 | 預設 | 說明 |
|---|---|---|---|
| `bundle` | — | `"1"` | 契約版本 |
| `title` | 建議 | `報告` | `<title>`；沒有 gdd 段時也是頁首 h1 |
| `subtitle` | — | — | 只用於簡版外殼 |
| `out` | — | `<title 清檔名>.html` | 輸出檔 |
| `quality` | — | `standard` | `lite`（寬 ×0.65、q55）／`standard`（q65）／`hi`（寬 ×1.5、q80）|
| `budget_mb` | — | `8` | 內嵌後 HTML 超過 → exit 3 |
| `format` | — | `webp` | `jpeg`：給不吃 WebP 的舊瀏覽器（有透明或 diagram 用 PNG）|
| `roles` | — | `{"symbols/*": icon}` | glob → 用途（icon 240／portrait 560／landscape 800／diagram 1200／full），補在預設之上 |
| `style` | — | gdd 預設樣式 | gdd 段的 style yaml |
| `parts` | ✔ | — | 依順序排版；`{kind: md, id, label, title?, path}` 或 `{kind: gdd, id, label, pack}`，gdd 段至多一段 |

## 組裝規則

1. **外殼**：有 gdd 段 → `gdd_build` 產素材總覽頁（`assets.root_rel` 改成相對輸出目錄）；沒有 → 內建簡版外殼（light / dark token）。
2. **md 段**：去 front matter（`date / author / verdict / confidence / provenance / source` 顯示成 meta 列）；第一個 `# ` 當段名（`title` 可覆寫）並移除；其餘標題降一級（`##`→h3）；表格包 `.tbl-wrap`；mermaid 區塊保留原始碼（`pre.bp-mermaid`，單檔不載外部 JS）。
3. **位置**：gdd 段之前的 md → nav 插在「遊戲規格」前、內容插在 `<main>` 開頭；之後的 md → nav 插在搜尋框前、內容插在 `</main>` 前；頁首下方加「本檔收錄」列。
4. **md 圖片**：`![說明](路徑)` 先找 md 所在目錄，再找 gdd 素材根（寫 `symbols/S1.png` 即與規格書共用、去重成一份）。獨立成段的圖由 html_images 包成 figure（alt 當圖說），連續圖排成圖庫，點圖放大。
5. **放圖**：ark-html-report `html_images.embed(mode="map", do_layout=True, lightbox=True, json_src=True, role_rules=roles)`；燈箱 gallery JSON 的 src 換成 `__img:<key>`，gdd 燈箱由 bundle 改成 `(window.__imgsrc || (s => s))(d.src)` 解析。

## 守門

| 條件 | 結果 |
|---|---|
| parts 空、kind 錯、id 重複、md / pack 找不到、兩段 gdd | exit 2 BAD_INPUT |
| md 內含 `<script>`／`<iframe>`／`on*=`／`javascript:` | exit 2 BAD_INPUT |
| md 圖片找不到 | exit 2（`data.missing`）|
| 內嵌後超過 `budget_mb`、或仍殘留本機圖片連結 | exit 3 GATE_BLOCKED |
| `--check`：尾端戳記與現況（yaml、各 md、gdd 來源戳記、quality/format）不一致 | exit 3（STALE）|
| 找不到 ark-html-report `html_images.py` | exit 8 MISSING_DEP |

## 輸出

- `<out>.html`：deterministic（無時間戳；同輸入 bit-identical），尾端 `<!-- gs-bundle: yaml:<sha16> md-<id>:<sha16> gdd[<gdd-src 戳記>] q:<quality>/<format> -->`。
- `<out>.bundle.json`：parts、stamp、images（每張圖用途、尺寸、原始／內嵌 KB、引用處）。

## 大小參考（KAIJI，2026-10-08）

| 素材 | 張數 | 原圖 | standard 內嵌 |
|---|---|---|---|
| 圖騰（icon 240） | 25 | 1.6 MB | ≈ 0.13 MB |
| 示意圖（portrait 560） | 31 | ≈ 82 MB | ≈ 1.9 MB |
| 規格書競品圖 | 40 | 1.5 MB | ≈ 0.14 MB |
| 合計（含 md 文字與頁面） | 96 張／335 處引用 | 85.9 MB | HTML **3.04 MB** |

`lite` 約 2 MB；`hi` 約 5 MB。
