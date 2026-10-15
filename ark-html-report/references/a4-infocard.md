# A4 資訊圖卡（infocard）版面

> 這是一種**版面格式**，與五種配色風格正交 —— 可搭配任一風格的 token。
> 適合：單頁速覽、技術總覽、套件/工具介紹、教學一頁通、可列印/轉 PDF 的 A4 圖卡。
> 與標準報告的差異：標準報告是**捲動長文**；infocard 是**單頁固定版面**，
> 一眼掃完，資訊密度高、字適中，上下分區。

## 何時用 infocard 而非標準報告

| 情境 | 用 |
|------|-----|
| 「做一張圖卡」「A4 一頁講清楚」「快速了解 X」 | **infocard** |
| 教學/工具總覽，要能列印貼牆或轉 PDF 分享 | **infocard** |
| 資料多、要捲動閱讀、含互動圖表 | 標準報告 |

## 版面骨架：上 → 中 → 下三分區

infocard 的核心是**分區敘事**，不是把長報告塞進一頁。典型三分：

```
┌─────────────────────────────────┐
│ 報頭：標題 + 一句定位 + 來源       │  ← 誰、什麼、一句話講完
├─────────────────────────────────┤
│ 上半：核心概念 / 哲學 + 概念圖     │  ← 「為什麼」，配 SVG 概念圖
│      （philo 區，背景色塊 + SVG）   │
├─────────────────────────────────┤
│ 中段：痛點條 / 重點列（可選）       │  ← 4 格等寬，快速掃
├─────────────────────────────────┤
│ 下半：分類卡片牆 + 流程圖           │  ← 「是什麼/怎麼組」，卡片 grid + SVG 流程
├─────────────────────────────────┤
│ 頁尾：整理者 + 日期 + 來源          │
└─────────────────────────────────┘
```

**分區依內容調整，不是固定模板**：哲學型放「概念圖+理念」在上；數據型放「KPI 列」在上；
流程型放「步驟圖」在下。決定分區前先問：讀者第一眼要看到什麼？

## A4 尺寸與列印 CSS（必備）

```css
.a4{
  width:210mm; min-height:297mm; margin:16px auto; background:var(--surface);
  padding:14mm 13mm; box-shadow:0 2px 20px rgba(24,34,51,.12);
  display:flex; flex-direction:column; gap:7mm;
}
@page{ size:A4; margin:0; }
@media print{
  body{ background:#fff; }
  .a4{ margin:0; box-shadow:none; width:auto; min-height:auto; }
  .card,.philo,.flow{ break-inside:avoid; }   /* 元件不被分頁切斷 */
}
```

## 密度控制（A4 一頁塞得下的關鍵）

單頁空間有限，字級比標準報告小一號、間距收緊：

| 元素 | 標準報告 | infocard |
|------|---------|---------|
| 內文 | 14-15px | 10.5-12px |
| 卡片標題 | 16px | 13px |
| 區塊間距 | 24-48px | 7mm（gap） |
| 卡片內距 | 22px | 11-13px |

**原則**：資訊密度高但不擁擠。寧可少放兩個 skill，也不要擠到看不清。
一頁放不下就是內容太多 —— 拆成兩張 infocard，不要縮到 9px。

## SVG 概念圖（infocard 靈魂，一律內嵌純 SVG）

infocard 幾乎一定要圖，且**必須內嵌 SVG**（列印/離線穩定，見 offline-mode.md）。
兩種最常用：

### A. 中心輻射圖（表達「核心 + 可插拔模組」）
```html
<svg width="150" height="120" viewBox="0 0 150 120">
  <circle cx="75" cy="60" r="20" fill="#1e3a5f"/>       <!-- 中心 -->
  <text x="75" y="60" text-anchor="middle" fill="#fff" font-size="10">核心</text>
  <circle cx="75" cy="18" r="13" fill="#2e7d52"/>        <!-- 衛星模組 -->
  <line x1="75" y1="40" x2="75" y2="31" stroke="#9db0c4"
        stroke-width="1.5" stroke-dasharray="3 3"/>       <!-- 虛線=可插拔 -->
</svg>
```

### B. 流程圖（表達「步驟串接」）
```html
<svg viewBox="0 0 250 130">
  <defs><marker id="ar" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto">
    <path d="M0,0 L6,3 L0,6 Z" fill="#8a95a6"/></marker></defs>
  <rect x="4" y="6" width="90" height="24" rx="5" fill="#e8edf3" stroke="#1e3a5f"/>
  <text x="49" y="20" text-anchor="middle" font-size="8">步驟 1</text>
  <line x1="94" y1="18" x2="116" y2="18" stroke="#8a95a6"
        stroke-width="1.3" marker-end="url(#ar)"/>
</svg>
```

SVG 配色一律從風格 token 取（`--c1`~`--c5`），換風格自動跟色。
文字用 `font-family="sans-serif"`（SVG 內不繼承 CSS 變數字型，寫死系統字型最穩）。

## 卡片牆（下半主體）

```css
.grid{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.card{ border:1px solid var(--border); border-radius:9px; padding:11px 13px;
       border-top:3px solid var(--cat); }   /* 每類一個 accent 色 */
.card li code{ font-family:var(--mono); font-size:10px; background:var(--surface-2);
               padding:1px 5px; border-radius:4px; }
```

每張卡片：類別標題 + 一句目標 + 3-4 個項目（`<code>名稱</code> + 一句白話用途`）。

## 檢查清單

- [ ] `.a4` 210mm×297mm、`@page size:A4`、`@media print` 三者齊全
- [ ] SVG 全內嵌（無 `<img src>`、無 CDN）、開合標籤數相等
- [ ] 字型系統 fallback（無 Google Fonts import），離線可開
- [ ] `break-inside:avoid` 讓卡片不被列印分頁切斷
- [ ] 上/中/下分區依內容決定，不硬套模板
- [ ] 一頁塞得下 —— 塞不下就拆兩張，不縮到看不清

## 完整範例

`artifacts/reports/mattpocock-skills-a4card-2026-09-02.html`
（上：哲學+中心輻射 SVG；下：五類卡片牆+流程 SVG）
