---
name: ark-pixel-animation
description: |
  產出復古遊戲像素動畫 executor（單檔 HTML，Canvas 2D 或 PixiJS）：低解析邏輯畫布、固定色盤、整數倍放大、8–12 FPS 點陣節奏，
  角色待機／集氣／施法／收招等循環動作；先分鏡、再 2 秒測試版、以 verify_pixel.py 逐秒取樣驗收（色盤外顏色、決定性、靜止、平滑放大、FPS）。
  使用此 skill 當提及：像素動畫、pixel art 動畫、點陣動畫、8-bit／16-bit 風、復古遊戲角色動作、sprite 循環動畫、像素角色、點陣角色待機動畫。
  不適用於：一般網頁 UI 動效與前端介面（→ ark-frontend-design）、slot 機率雛型與演出（→ ark-game-proto）、
  正式遊戲 Client 與素材打包（→ ark-web-game）、數據圖表與儀錶板（→ ark-html-dashboard）。
metadata:
  schema_version: "1.2"
  status: active
  author: paddyyang
  category: view
  form: executor
  domain: game
  version: "1.0.0"
  updated: 2026-11-05
  outputs:
    - { format: html, audience: human }
    - { format: png, audience: human }
  render: html
---

# ark-pixel-animation — 復古遊戲像素動畫

把一段角色或場景描述做成**單一 HTML 檔**的像素風循環動畫：不用外部圖檔，所有圖形由程式逐像素畫出，
畫面完全由時間 `t` 決定，可逐秒截圖驗收。

| 檔案 | 用途 |
|---|---|
| `assets/template-canvas.html` | Canvas 2D 範本（預設，零依賴） |
| `assets/template-pixi.html` | PixiJS 8 範本（使用者指定 PixiJS 時；需 CDN），說明見 `references/pixijs.md` |
| `scripts/verify_pixel.py` | 驗收腳本（必跑） |
| `references/motion-guide.md` | 動作設計守則、分鏡表格式 |
| `references/prompt-template.md` | 給使用者的提詞範本 |

## 鐵律（每支動畫都必須遵守）

1. **低解析邏輯畫布**：常用 160×90（16:9）、128×96（4:3）、64×64（icon）。所有座標是邏輯像素整數。
2. **整數倍放大、關閉平滑**：`canvas.width/height = 邏輯尺寸`，CSS 寬高 = 邏輯尺寸 × 整數 SCALE；`imageSmoothingEnabled = false`；CSS `image-rendering: pixelated`。
3. **固定色盤**：全片只用 `PAL` 陣列中的顏色（常用 16 或 24 色），以索引取色。**禁止**漸層、模糊、陰影、`globalAlpha`、半透明、`arc()`／`fillText()`／`lineTo` 斜線（都會產生反鋸齒色）。圓、斜線、文字一律用像素點或 bitmap 自己畫。
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
- **一定要用 Read 打開 `_contact_sheet.png` 親自看**，再回報。`ok: false` 時修正後重跑，直到通過。

### Step 5 — 正式版

節奏與細節確認後，把 `DURATION` 與 `STATES` 擴成正式長度，重跑 Step 4。

### Step 6 — 交付

- 有 Artifact 工具：發佈成 artifact（頁面本身已自包含）。
- 否則：存到專案產出目錄交付 HTML，並附 contact sheet。
- 網址參數：`?t=3.5` 凍結在 3.5 秒，`?scale=6` 指定放大倍率。

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
