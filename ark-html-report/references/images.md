# 放圖引擎 html_images.py（1.1）

> 目標：報告可以放很多圖，但單檔仍然小到可以當附件寄。做法是「依用途縮到頁面實際需要的尺寸 → 轉 WebP → 同一張圖只存一份 → 內嵌」。

## 為什麼要有這支

| 做法 | 36 張 1080×1920 遊戲截圖 |
|---|---|
| 原圖直接 base64 內嵌 | 約 127 MB（原檔 95 MB × 4/3）|
| 縮到寬 560 + WebP q65 + base64 | 約 2.8 MB |

參考：金猴爺新手體驗報告（2026-10-08）用同一招：44 張 JPEG 800×450 內嵌，整份 3.6 MB，文字只佔 26 KB。

## 指令

```bash
python scripts/html_images.py inspect report.html                         # 列出引用、預估大小，不寫檔
python scripts/html_images.py embed report.html [--base <dir>] [--out <file>] \
       [--quality lite|standard|hi] [--format webp|jpeg] [--mode auto|uri|map] \
       [--budget-mb 8] [--layout] [--lightbox] [--manifest images.json] [--no-json-src] [--role 'GLOB=ROLE' …]
```

Python 內呼叫：`html, report = html_images.embed(html_text, base_dir, quality=..., do_layout=True)`；
錯誤丟 `html_images.EmbedError(code, msg, data)`（code：BAD_INPUT 缺檔／GATE_BLOCKED 超預算／MISSING_DEP 沒 Pillow）。

## 處理哪些引用

| 位置 | 例 | 備註 |
|---|---|---|
| `<img src>` | `<img src="shots/a.png">` | 主要用法 |
| `<a href>` 指向圖檔 | `<a href="shots/a.png">原圖</a>` | 換成內嵌圖（同一份）|
| `<source srcset>` 單一路徑 | | 多重 srcset 不處理 |
| JSON 字串 `"src":"…"` | 燈箱、gallery 資料 | map 模式改成 `"__img:<key>"`，頁面 JS 用 `window.__imgsrc(s)` 解析 |

不動：`http(s)://`、`//`、`data:`、`#`；外部圖片會列在 `external_images`（offline 交付要處理掉）。

## 用途、尺寸、品質

| data-role | 自動判斷 | lite | standard | hi | 格式 |
|---|---|---|---|---|---|
| icon | 長邊 ≤ 400 | 156 | 240 | 240 | WebP（保留透明）|
| portrait | 高 ≥ 1.3 × 寬 | 364 | 560 | 840 | WebP |
| landscape | 其他 | 520 | 800 | 1200 | WebP |
| diagram | 手動 | 780 | 1200 | 1800 | WebP 無損 |
| full | 手動 | 原尺寸 | 原尺寸 | 原尺寸 | WebP |

品質：lite q55／standard q65／hi q80。`--format jpeg`：不透明圖用 JPEG（品質 +10），透明圖與 diagram 用 PNG。
SVG 原樣內嵌；動態 GIF 原樣內嵌（會很大，建議改成靜態圖或影片連結）。原圖已經比轉檔結果小、又不需要縮時，直接用原圖。

## 內嵌模式

| 模式 | 什麼時候 | 結果 |
|---|---|---|
| uri | auto：沒有重複引用、也沒有 JSON 引用 | 每個 src 直接是 data URI；零 JS，信件預覽、關掉 JS 都看得到 |
| map | auto：有重複引用或 JSON 引用 | `<body>` 開頭一段 `window.__IMG={key:dataURI}`；`<img data-img="key">` 由 `</body>` 前的 script 回填；同一張圖只存一份 |

key = 轉檔後 bytes 的 sha256 前 12 碼，所以不同檔名但內容相同的圖也會合併。

## 放圖輔助（--layout／--lightbox）

- 獨立成段的 `<img>`（`<p><img></p>` 或單獨一行）→ `<figure class="ar-fig ar-{role}">`，`alt` 變圖說
- 連續兩個以上 figure → `<div class="ar-gallery">`（全是 icon 時加 `ar-icons`）
- CSS 注入 `<head>`，只讀 `--radius --border/--line --surface/--card --text-muted/--muted`，沒有就用 fallback
- `--lightbox`：點 figure 裡的圖全螢幕放大，Esc 或點任意處關閉

## 守門與 deterministic

- 缺檔 → exit 2（列前 20 個）；超過 `--budget-mb`（預設 8）→ exit 3，`top` 列前 10 大張圖（role、原尺寸、轉檔後 KB、被引用幾次）
- 同一份 HTML、同一批圖、同參數 → 輸出逐位元相同（WebP 編碼參數固定、不寫 metadata、key 排序）
- `--manifest` 另存每張圖的 key／role／尺寸／原 KB／內嵌 KB／引用次數／原路徑，方便事後追查是哪張圖撐大檔案

## 預算建議

| 交付通道 | 建議 --budget-mb | 建議 --quality |
|---|---|---|
| Telegram／Slack 附件、手機看 | 5 | standard |
| Email 附件 | 8 | standard |
| 內網歸檔、要看細節 | 15 | hi |
| 只看文字大意 | 2 | lite |

## 依路徑指定用途（1.1：`--role` / `role_rules`）

沒寫 `data-role` 的引用（含 JSON 的 `"src"`）可依路徑 glob 指定用途：`--role 'symbols/*=icon' --role 'charts/*=diagram'`；
Python 呼叫用 `embed(..., role_rules={"symbols/*": "icon"})`。`data-role` 屬性優先於規則，規則優先於自動判斷。
用途相同的同一張圖只編碼一次、內容去重成一份——ark-game-spec bundle 用它讓素材總覽的圖騰卡片與燈箱 gallery 共用同一份 240px 圖。
