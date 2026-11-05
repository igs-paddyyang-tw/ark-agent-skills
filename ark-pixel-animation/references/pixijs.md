# PixiJS 版說明

> 完整範本：`assets/template-pixi.html`（已用 `scripts/verify_pixel.py` 驗收通過）。使用者指定 PixiJS 時才用；預設用 Canvas 2D 範本。

保留區段 1、3 的寫法與 `window.__pixel` 契約，只換繪圖層：

- 載入固定版本：`<script src="https://cdn.jsdelivr.net/npm/pixi.js@8.6.6/dist/pixi.min.js"></script>`
- 初始化：`PIXI.TextureStyle.defaultOptions.scaleMode = 'nearest'`；`await app.init({width:W, height:H, antialias:false, resolution:1, roundPixels:true, background:PAL[0], preserveDrawingBuffer:true})`；`app.ticker.stop()`，改由自己的 rAF 迴圈在格數變化時呼叫 `renderAt(t)` → `app.render()`。
- 放大：`app.canvas.style.width = W*SCALE+'px'`，CSS `image-rendering:pixelated`。
- 繪圖：每次 `renderAt` 先 `g.clear()`，`rect()` 改為 `g.rect(I(x),I(y),I(w),I(h)).fill(PAL[c])`；不用 `circle()`、`stroke()`、濾鏡（BlurFilter/Glow）、`alpha`。
- `pixels()`：`renderAt` 後 `app.render()`，再用 `app.canvas` 畫到暫存 2D canvas 取 `getImageData`（需 `preserveDrawingBuffer:true`）。
- 驗收腳本不用改。
- 離線環境載不到 CDN → 改用 Canvas 2D 範本，不要自行下載或內嵌 pixi.js。
