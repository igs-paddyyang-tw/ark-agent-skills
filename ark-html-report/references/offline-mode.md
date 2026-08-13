# Offline 模式 — 零外部請求的報告

> 預設模式允許兩個外部資源（Chart.js CDN、Google Fonts）。
> **有些交付通道不允許任何外部請求**，這時整份報告的每一個位元組都必須內嵌。

## 什麼時候必須用 offline

| 通道 | 為什麼 |
|------|--------|
| **Telegram／Slack 檔案附件** | 讀者常在手機上點開，可能沒有網路或在受限網路。CDN 一掉，字體與圖表同時失效 |
| Email 附件 | 同上，且多數郵件客戶端封鎖遠端資源 |
| 內網／封閉網路交付 | 對外連線本來就被擋 |
| 長期歸檔 | CDN 版本會下架。三年後打開，`chart.umd.min.js` 404 就只剩空白區塊 |
| 客戶端不明的分享 | 不確定就用 offline —— 代價只是圖表少一點互動 |

反過來，**明確在有網路的瀏覽器開啟、且需要互動圖表**時，用預設模式即可。

## 三件事要改

### 1. 字體：移掉 `@import`，保留同名 fallback

```css
/* ❌ 需要網路 */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC…');

/* ✅ 直接用本機字體，字體名稱本身不需要網路 */
--font-body: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", "Hiragino Sans", sans-serif;
--font-display: "Noto Serif TC", "Songti TC", "PMingLiU", Georgia, serif;
--font-mono: "JetBrains Mono", "SF Mono", Consolas, "Noto Sans TC", monospace;
```

多數 Windows／macOS／Android 都有其中一款中文字體。**不要為了字體一致而內嵌 woff2 data URI**
—— 一套中文字體動輒 3-8 MB，會把附件撐爆（Telegram 上限 50 MB，但沒人想下載 8 MB 的日報）。

字重也要收斂：本機字體通常只有 400／700 兩級，設計時不要依賴 500／600。

### 2. 圖表：Chart.js → 純 SVG

`references/charts.md` 的 SVG 模式直接可用。取捨很明確：

| | Chart.js | 純 SVG |
|---|---|---|
| 外部請求 | 需要 | 無 |
| 互動 tooltip | ✅ | ❌（可用 `<title>` 做原生 hover 提示） |
| 列印 | 需等 JS 執行 | 直接可印 |
| 資料量 | 大 | 建議 ≤ 30 點 |

資料超過 30 點時，改用表格或先聚合 —— 硬塞進 SVG 只會擠成一團。

### 3. 主題三態

檢視器可能在根元素蓋 `data-theme`，也可能只吃系統偏好。三個入口都要顧：

```css
:root { /* 完整淺色 token */ }

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* 深色 token */ }
}
:root[data-theme="dark"] { /* 同一組深色 token */ }
```

`body` 必須明確設定 `background: var(--bg)` —— 沒設就會透出檢視器自己的底色，
在深色檢視器裡看到淺色文字配深色底，整份糊掉。

**元件只讀 token，不在 media query 裡直接寫顏色**。只定義在 `@media` 內的顏色，
在「系統淺色 + 未蓋章」的狀態下不會生效。

## 交付前檢查

```bash
# 應該只印出報告本身的來源連結（新聞／資料來源），不該有 cdn/fonts/googleapis
grep -oE '(src|href)="https?://[^"]+"' report.html

# 這三個都應該是 0
grep -c '@import' report.html
grep -c '<script src=' report.html
grep -c 'fonts.googleapis' report.html
```

再開一次檔案確認：**關掉網路**，用瀏覽器開，版面與線上一致。
沒實際斷網看過就不算驗過 —— 瀏覽器快取會讓你以為沒問題。

## 可用的樣板

| 檔案 | 用途 |
|------|------|
| `assets/template-offline.html` | offline 骨架（已內含三態主題與系統字體 stack） |
| `../ark-daily-news/assets/news-daily.html` | 日報卡片牆版式，本身就是 offline 的完整實例 |
