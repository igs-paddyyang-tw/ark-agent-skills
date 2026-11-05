---
name: ark-pixel-animation
description: |
  產出復古遊戲像素動畫 executor（單檔 HTML，Canvas 2D 或 PixiJS）：低解析邏輯畫布、固定色盤、整數倍放大、8–12 FPS 點陣節奏，
  角色待機／集氣／施法／收招等循環動作；先分鏡、再 2 秒測試版、以 verify_pixel.py 逐秒取樣驗收（色盤外顏色、決定性、靜止、平滑放大、FPS）。
  1.1 起另有 sprite sheet 模式：名字 → 原創 Q 版角色 112×96 sheet（3 方向 × 7 格，pixel-agents 相容）＋ manifest，verify_sheet.py 驗收。
  使用此 skill 當提及：像素動畫、pixel art 動畫、點陣動畫、8-bit／16-bit 風、復古遊戲角色動作、sprite 循環動畫、像素角色、點陣角色待機動畫、
  sprite sheet、角色圖集、Q 版像素角色、辦公室角色、agent 頭像像素圖。
  不適用於：一般網頁 UI 動效與前端介面（→ ark-frontend-design）、slot 機率雛型與演出（→ ark-game-proto）、
  正式遊戲 Client 與素材打包（→ ark-web-game）、數據圖表與儀錶板（→ ark-html-dashboard）。
metadata:
  schema_version: "1.2"
  status: active
  author: paddyyang
  category: view
  form: executor
  domain: game
  version: "1.1.0"
  updated: 2026-11-05
  outputs:
    - { format: html, audience: human }
    - { format: png, audience: human }
    - { format: data, audience: ai }
  render: html
---

# ark-pixel-animation — 復古遊戲像素動畫

把一段角色或場景描述做成**單一 HTML 檔**的像素風循環動畫：不用外部圖檔，所有圖形由程式逐像素畫出，
畫面完全由時間 `t` 決定，可逐秒截圖驗收。

| 檔案 | 用途 |
|---|---|
| `assets/template-canvas.html` | Canvas 2D 範本（預設，零依賴） |
| `assets/template-pixi.html` | PixiJS 8 範本（使用者指定 PixiJS 時；需 CDN），說明見 `references/pixijs.md` |
| `scripts/verify_pixel.py` | 動畫驗收（必跑）；1.1 起可驗網址、`--canvas` 指定畫布、viewport 自動容得下 |
| `assets/chibi.js` | **sprite sheet 模式**：Q 版角色產生器（唯一來源；瀏覽器／ES 模組／node 都能載入） |
| `assets/template-sheet.html` | sprite sheet 預覽頁（動作預覽＋sheet 圖；`chibi.js` 由匯出腳本注入） |
| `scripts/export_sheet.py` | 名字 → `char_<slug>.png`（112×96 RGBA）＋ `<slug>.json`（`ark.pixel_character.v1`） |
| `scripts/verify_sheet.py` | sprite sheet 驗收（8 項，只需 Pillow） |
| `references/motion-guide.md` | 動作設計守則、分鏡表格式 |
| `references/prompt-template.md` | 給使用者的提詞範本 |

## 鐵律（每支動畫都必須遵守）

1. **低解析邏輯畫布**：常用 160×90（16:9）、128×96（4:3）、64×64（icon）。所有座標是邏輯像素整數。
2. **整數倍放大、關閉平滑**：`canvas.width/height = 邏輯尺寸`，CSS 寬高 = 邏輯尺寸 × 整數 SCALE；`imageSmoothingEnabled = false`；CSS `image-rendering: pixelated`。
3. **固定色盤**：全片只用 `PAL` 陣列中的顏色（常用 16 或 24 色），以索引取色。**禁止**漸層、模糊、陰影、`globalAlpha`、半透明、`arc()`／`fillText()`／`lineTo` 斜線（都會產生反鋸齒色）。圓、斜線、文字一律用像素點或 bitmap 自己畫。
   **sprite sheet 模式例外**：背景必須透明 → 每個像素的 alpha 只能是 0（背景）或 255（色盤色），**禁止中間值**（`verify_sheet.py` ② 檢查）。
4. **點陣節奏**：FPS 8–12（預設 10）。`f = floor(t*FPS)`，所有動作數值都由 `f` 或量化後的 `tq = f/FPS` 推出，位移用 `Math.floor`／`step()` 對齊像素格。
5. **決定性**：同一個 `t` 永遠畫出同一張圖。不用 `Math.random()`、`Date.now()`，改用 `hash(n)`。
6. **單一入口 `renderAt(t)`**：每次全畫面重畫，不依賴上一格狀態；並暴露 `window.__pixel` 驗收介面。
7. **原創角色**：只做使用者自訂或原創角色；不重現既有遊戲、動畫、品牌的角色或 sprite。若需求指向知名角色，說明一次後改做風格相近的原創角色。

## 流程

### Step 1 — 收規格

從需求整理成下表；缺的項目用預設值，**不要為此停下來問**，在分鏡中列出假設即可。

| 項目 | 預設 |
|---|---|
| 畫布 | 160×90 |
| 色盤 | 16 色（給 hex 清單，標註各色用途） |
| FPS | 10 |
| 長度 | 10 秒（測試版 2 秒） |
| 角色 | 原創，約 24×32 像素（小角色 12×16 亦可） |
| 動作狀態 | 待機 → 準備／集氣 → 主動作 → 收尾，循環 |
| 引擎 | Canvas 2D（零依賴）；使用者指定 PixiJS 時用 PixiJS 範本 |

### Step 2 — 分鏡（先給使用者確認）

依 `references/motion-guide.md` 輸出分鏡表（每列一個狀態：時段、格數、姿勢、特效、量化規則），
附色盤表（索引、hex、用途）與角色 sprite 草圖（字串陣列）。使用者在場時等確認；無人回應或使用者說「直接做」就照分鏡往下。

### Step 3 — 2 秒測試版

複製範本，`DURATION = 2`，`STATES` 壓縮到 2 秒內，**只改「1. 規格」與「3. 場景」區段**；區段 2、4 是引擎與驗收介面，保持原樣。

### Step 4 — 驗收（必跑）

```bash
python3 scripts/verify_pixel.py anim.html --out shots --step 0.5   # 測試版每 0.5 秒
python3 scripts/verify_pixel.py anim.html --out shots              # 正式版逐秒
```

檢查項目：色盤外顏色（反鋸齒／漸層／半透明）、同一 t 渲染兩次是否一致、相鄰截圖是否完全相同（動作停滯）、
放大後每格是否單色（平滑放大）、FPS 範圍、console 錯誤；最後一格必取樣（循環接縫）。
輸出 `_contact_sheet.png` 與 `report.json`；exit 0 通過、1 有問題、2 環境缺件。

- 需要 Python `playwright` 與 `Pillow`。Chromium 已安裝就不要重裝；版本與 playwright 不合時用 `--chromium <執行檔>` 或 `ARK_PIXEL_CHROMIUM` 指定。
- 驗網頁：目標直接給 `http(s)://` 網址；頁面有多張 canvas 時用 `--canvas "<選擇器>"`；viewport 預設自動放大到容得下放大後的畫布（`--viewport WxH` 可覆寫）。Playwright 截圖預設隱藏捲軸，要驗捲軸請自行截整頁並關掉 `--hide-scrollbars`。
- **一定要用 Read 打開 `_contact_sheet.png` 親自看**，再回報。`ok: false` 時修正後重跑，直到通過。

### Step 5 — 正式版

節奏與細節確認後，把 `DURATION` 與 `STATES` 擴成正式長度，重跑 Step 4。

### Step 6 — 交付

- 有 Artifact 工具：發佈成 artifact（頁面本身已自包含）。
- 否則：存到專案產出目錄交付 HTML，並附 contact sheet。
- 網址參數：`?t=3.5` 凍結在 3.5 秒，`?scale=6` 指定放大倍率。

## sprite sheet 模式（1.1）

用途：遊戲或網頁要拿「一個角色的全部動作格」當素材（例：Pixel Office 的 agent 角色）。產出物是 PNG＋manifest，不是單檔動畫。

| 項目 | 規格 |
|---|---|
| 版型 | 112×96 RGBA＝3 列方向（下、上、右；左＝右的水平鏡像）× 7 格 × 16×32；第 0–2 格走路、3–4 格打字、5–6 格閱讀（與 pixel-agents `char_N.png` 相容） |
| 造型 | 原創 Q 版：14×14 大頭、小身體；**名字決定外觀**（FNV-1a 雜湊 → 髮色 × 衣服 × 配件，216 種）；同一次匯出的名字保證不重複；同樣輸入永遠同樣輸出 |
| 色盤 | `chibi.js` 的 `CHIBI_PAL`（寫進 manifest 的 `palette`） |
| manifest | `{"schema":"ark.pixel_character.v1","name","frame":{"w":16,"h":32},"rows":["down","up","right"],"frames":{"walk":[0,1,2],"type":[3,4],"read":[5,6]},"palette":[…],"look":{…},"hash"}` |

流程：

```bash
python3 scripts/export_sheet.py --name cto-agent --name qa-agent --out characters/   # 或 --names-file names.txt
python3 scripts/verify_sheet.py characters/char_*.png --out characters/contact/       # 8 項全過才交付
python3 scripts/export_sheet.py --preview sheet.html                                   # 預覽頁：開 sheet.html?name=cto-agent
```

`verify_sheet.py` 檢查：① 尺寸 112×96 ② alpha 只有 0／255 ③ 不跨格 ④ 每格非空且腳底在第 31 列 ⑤ 顏色都在 manifest 色盤 ⑥ 走路首尾腳部位移 ≤ 2px ⑦ 打字、閱讀兩格各有變化 ⑧ 輸出 6 倍 contact sheet。
**一定要用 Read 打開 contact sheet 親自看**再交付。網頁要即時畫同一個角色時，直接載入 `assets/chibi.js` 呼叫 `ArkChibi.buildSheet()`，不要另寫一份畫法。

## `window.__pixel` 契約

| 成員 | 說明 |
|---|---|
| `W`、`H`、`FPS`、`DURATION`、`PAL`、`SCALE`、`STATES` | 規格常數（`STATES` 為狀態名稱陣列） |
| `renderAt(t)` | 畫出時間 `t` 的畫面，回傳 `{t, frame, state}` |
| `pause()`／`play()` | 停止／恢復自動播放 |
| `pixels()` | 目前畫面的 RGBA 位元組陣列（長度 `W*H*4`） |

## 回報格式

1. 規格：畫布、色盤數（實際使用數）、FPS、長度、狀態序列
2. 驗收結果：`ok` 與問題清單（含時間點）；附 contact sheet
3. 目視檢查：節奏、剪影可讀性、循環接縫是否順
4. 下一步可調整的參數（例如各狀態 `dur`、光圈階數、角色位置）
