# 風格預設（Style Presets）

每種風格是一組 CSS variables。所有元件只使用這些變數，因此換風格 = 換 `:root` 區塊 + 對應的 Google Fonts import。

## Token 規格（所有風格共用同一組變數名）

| 變數 | 用途 |
|------|------|
| `--bg` | 頁面背景 |
| `--surface` / `--surface-2` | 卡片背景 / 次級背景（表頭、code 底） |
| `--border` | 邊框 |
| `--text` / `--text-2` / `--text-3` | 主文字 / 次要文字 / 弱化文字（註腳、eyebrow） |
| `--accent` / `--accent-soft` | 主題色 / 主題色淡背景（10-15% 透明度） |
| `--ok` / `--warn` / `--danger` / `--info` | 語意色 |
| `--c1` ~ `--c6` | 圖表色盤 |
| `--font-display` / `--font-body` / `--font-mono` | 標題字 / 內文字 / 等寬字 |
| `--radius` / `--radius-sm` | 圓角 |
| `--shadow` | 卡片陰影 |
| `--maxw` | 內容最大寬度 |

中文 fallback 一律：`"Noto Sans TC", "Microsoft JhengHei", "PingFang TC", sans-serif`。

---

## 1. boardroom 企業簡報

正式、可信、資訊密度中等。深藍 + 金銅 accent，襯線標題。

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Noto+Serif+TC:wght@600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root {
  --bg:#f6f7f9; --surface:#ffffff; --surface-2:#eef1f5; --border:#dde2e9;
  --text:#1a2332; --text-2:#4a5568; --text-3:#8b95a5;
  --accent:#1e3a5f; --accent-soft:rgba(30,58,95,.08);
  --ok:#2e7d52; --warn:#b7791f; --danger:#c53030; --info:#2b6cb0;
  --c1:#1e3a5f; --c2:#b08d57; --c3:#5a7fa6; --c4:#8ba888; --c5:#c9a86a; --c6:#7d8ca3;
  --font-display:"Noto Serif TC","Noto Sans TC","Microsoft JhengHei",serif;
  --font-body:"Noto Sans TC","Microsoft JhengHei","PingFang TC",sans-serif;
  --font-mono:"IBM Plex Mono","Noto Sans TC",monospace;
  --radius:10px; --radius-sm:6px;
  --shadow:0 1px 3px rgba(26,35,50,.06),0 4px 12px rgba(26,35,50,.05);
  --maxw:960px;
}
```
特色：封面標頭可加一條 `border-top: 4px solid var(--c2)` 金銅線作為簽名元素。

## 2. terminal 技術文件

清晰、工程感。白底、藍 accent、等寬字用於標籤/數據/eyebrow。

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root {
  --bg:#fafbfc; --surface:#ffffff; --surface-2:#f1f4f7; --border:#e2e7ed;
  --text:#16202b; --text-2:#4d5d6e; --text-3:#93a1b0;
  --accent:#0b66c3; --accent-soft:rgba(11,102,195,.09);
  --ok:#1a8754; --warn:#b45309; --danger:#d1242f; --info:#0b66c3;
  --c1:#0b66c3; --c2:#1a8754; --c3:#7c3aed; --c4:#d97706; --c5:#0d9488; --c6:#64748b;
  --font-display:"Noto Sans TC","Microsoft JhengHei",sans-serif;
  --font-body:"Noto Sans TC","Microsoft JhengHei","PingFang TC",sans-serif;
  --font-mono:"JetBrains Mono","Noto Sans TC",monospace;
  --radius:8px; --radius-sm:5px;
  --shadow:0 1px 2px rgba(22,32,43,.05);
  --maxw:920px;
}
```
特色：eyebrow、badge、表格數字欄使用 `--font-mono`；章節標題前可加 `##` 或 `>` 的 mono 裝飾字符。

## 3. midnight 深色儀表板

數據密集、螢幕閱讀。深藍黑底、青色 accent、高對比數字。

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root {
  --bg:#0d1219; --surface:#151c26; --surface-2:#1c2532; --border:#273140;
  --text:#e8edf4; --text-2:#a8b4c4; --text-3:#68758a;
  --accent:#3dd6c3; --accent-soft:rgba(61,214,195,.12);
  --ok:#4ade80; --warn:#fbbf24; --danger:#f87171; --info:#60a5fa;
  --c1:#3dd6c3; --c2:#60a5fa; --c3:#c084fc; --c4:#fbbf24; --c5:#f472b6; --c6:#94a3b8;
  --font-display:"Space Grotesk","Noto Sans TC","Microsoft JhengHei",sans-serif;
  --font-body:"Noto Sans TC","Microsoft JhengHei","PingFang TC",sans-serif;
  --font-mono:"JetBrains Mono","Noto Sans TC",monospace;
  --radius:12px; --radius-sm:7px;
  --shadow:0 0 0 1px rgba(255,255,255,.03),0 8px 24px rgba(0,0,0,.35);
  --maxw:1080px;
}
```
注意：深色底的 Chart.js 需設定 `gridColor: 'rgba(255,255,255,.07)'` 與淺色 tick（見 charts.md）。KPI 數字用 `--font-display` 放大呈現效果最好。

## 4. editorial 雜誌編輯

長文閱讀、洞察類報告。暖白底、墨綠 accent、大標題強對比。

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@500;700;900&family=Noto+Sans+TC:wght@400;500;700&display=swap');
:root {
  --bg:#faf8f4; --surface:#ffffff; --surface-2:#f2efe8; --border:#e5e0d5;
  --text:#22261f; --text-2:#565b50; --text-3:#98988c;
  --accent:#2f5233; --accent-soft:rgba(47,82,51,.09);
  --ok:#2f7d3f; --warn:#a16207; --danger:#b3362d; --info:#3a6ea5;
  --c1:#2f5233; --c2:#a16207; --c3:#7a5c3e; --c4:#3a6ea5; --c5:#8c4646; --c6:#6b705c;
  --font-display:"Noto Serif TC","Microsoft JhengHei",serif;
  --font-body:"Noto Sans TC","Microsoft JhengHei","PingFang TC",sans-serif;
  --font-mono:"Noto Sans TC",monospace;
  --radius:4px; --radius-sm:3px;
  --shadow:none;
  --maxw:820px;
}
```
特色：卡片以 `border:1px solid var(--border)` 取代陰影；章節標題大字級（clamp(28px, 4vw, 40px)）+ 首段可用 drop cap 或粗體導語；引用區塊是這個風格的強項。

## 5. paperprint 極簡印刷

列印/PDF 優先。純白底、黑字、單一紅 accent，無陰影無漸層。

```css
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
:root {
  --bg:#ffffff; --surface:#ffffff; --surface-2:#f4f4f4; --border:#d9d9d9;
  --text:#111111; --text-2:#444444; --text-3:#888888;
  --accent:#b52b2b; --accent-soft:rgba(181,43,43,.07);
  --ok:#1f6f3f; --warn:#8a5a00; --danger:#b52b2b; --info:#2a5a8a;
  --c1:#333333; --c2:#b52b2b; --c3:#777777; --c4:#aaaaaa; --c5:#555555; --c6:#cccccc;
  --font-display:"Noto Sans TC","Microsoft JhengHei",sans-serif;
  --font-body:"Noto Sans TC","Microsoft JhengHei","PingFang TC",sans-serif;
  --font-mono:"Noto Sans TC",monospace;
  --radius:0px; --radius-sm:0px;
  --shadow:none;
  --maxw:800px;
}
```
特色：全部用 1px 實線分隔；圖表優先用純 SVG（列印穩定）；務必包含完整 `@media print` 規則。

---

## 基礎樣式（所有風格共用，放在 :root 之後）

```css
* { box-sizing:border-box; margin:0; padding:0; }
body {
  background:var(--bg); color:var(--text);
  font-family:var(--font-body); font-size:15px; line-height:1.75;
  -webkit-font-smoothing:antialiased;
}
.page { max-width:var(--maxw); margin:0 auto; padding:48px 28px 80px; }
h1,h2,h3 { font-family:var(--font-display); line-height:1.3; }
a { color:var(--accent); }
@media (max-width:640px){ .page{ padding:28px 16px 56px; } }
@media print {
  body { background:#fff; }
  .card,.kpi,.callout { box-shadow:none !important; break-inside:avoid; }
  .section { break-inside:avoid-page; }
  a { color:inherit; text-decoration:none; }
}
```

## 微調指引

- 換主題色：只改 `--accent`、`--accent-soft`、`--c1`（保持 `--c1` = accent 讓圖表主色一致）
- 公司品牌色：把品牌色放進 `--accent`，並確認在該風格底色上的對比 ≥ 4.5:1
- 不要在元件層寫死顏色。所有顏色微調都回到 token 層
