# 元件庫（Components）

所有元件只使用 token 變數，可搭配任何風格。CSS 放入 `<style>`（只放用到的元件），HTML 依內容組裝。

目錄：
1. 封面標頭 report-header
2. 摘要 summary
3. KPI 卡片列 kpi-grid
4. 章節標題 section
5. 卡片 card / 卡片網格 card-grid
6. 資料表格 table
7. 比較表格 compare-table
8. 圖表容器 chart-card
9. Callout
10. 時間軸 timeline
11. 進度條 progress
12. 標籤 badge
13. 引用 quote
14. 程式碼 codeblock
15. 雙欄 two-col
16. N-M-P-Q 區塊
17. 頁尾 footer

---

## 1. 封面標頭

```html
<header class="report-header">
  <div class="eyebrow">週報 · 研七 · ARK PLATFORM</div>
  <h1>報告主標題：一句話說出核心結論</h1>
  <p class="lede">副標補充範圍與重點，一到兩句。</p>
  <div class="meta">
    <span>2026-08-11</span><span>·</span><span>作者</span><span>·</span><span class="badge badge-accent">機密等級</span>
  </div>
</header>
```
```css
.report-header { padding:8px 0 32px; border-bottom:1px solid var(--border); margin-bottom:40px; }
.eyebrow { font-family:var(--font-mono); font-size:12px; letter-spacing:.14em; color:var(--accent); text-transform:uppercase; margin-bottom:14px; }
.report-header h1 { font-size:clamp(26px,4.5vw,38px); margin-bottom:12px; }
.lede { font-size:17px; color:var(--text-2); max-width:44em; }
.meta { display:flex; gap:10px; align-items:center; margin-top:18px; font-size:13px; color:var(--text-3); }
```

## 2. 摘要（Executive Summary）

```html
<section class="summary">
  <h2>摘要</h2>
  <ul>
    <li><strong>結論先行：</strong>一句話結論，附關鍵數字。</li>
    <li><strong>第二重點：</strong>…</li>
  </ul>
</section>
```
```css
.summary { background:var(--accent-soft); border-left:4px solid var(--accent); border-radius:var(--radius-sm); padding:22px 26px; margin-bottom:40px; }
.summary h2 { font-size:15px; letter-spacing:.06em; color:var(--accent); margin-bottom:10px; }
.summary ul { padding-left:20px; display:grid; gap:6px; }
```

## 3. KPI 卡片列

```html
<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-label">日活躍用戶</div>
    <div class="kpi-value">12,483</div>
    <div class="kpi-delta up">↑ 8.2% vs 上週</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">錯誤率</div>
    <div class="kpi-value">0.42%</div>
    <div class="kpi-delta down">↓ 0.11pp vs 目標</div>
  </div>
</div>
```
```css
.kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin:28px 0; }
.kpi { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); padding:20px 22px; }
.kpi-label { font-size:12px; letter-spacing:.08em; color:var(--text-3); margin-bottom:8px; }
.kpi-value { font-family:var(--font-display); font-size:30px; font-weight:700; line-height:1.1; }
.kpi-delta { font-size:12.5px; margin-top:8px; font-family:var(--font-mono); }
.kpi-delta.up { color:var(--ok); } .kpi-delta.down { color:var(--danger); }
```
注意：「上升」不一定是好事（如錯誤率），`up/down` class 依**好壞**選色而非依方向。

## 4. 章節標題

```html
<section class="section">
  <div class="section-head">
    <span class="section-no">01</span>
    <h2>章節標題</h2>
  </div>
  <p>內文…</p>
</section>
```
```css
.section { margin:48px 0; }
.section-head { display:flex; align-items:baseline; gap:14px; padding-bottom:12px; border-bottom:1px solid var(--border); margin-bottom:20px; }
.section-no { font-family:var(--font-mono); font-size:13px; color:var(--accent); font-weight:600; }
.section-head h2 { font-size:clamp(20px,3vw,26px); }
.section p { color:var(--text-2); margin-bottom:14px; max-width:52em; }
```
`section-no` 僅在章節確實有順序意義時使用，否則拿掉。

## 5. 卡片與卡片網格

```html
<div class="card-grid cols-3">
  <div class="card">
    <h3>卡片標題</h3>
    <p>內容說明。</p>
  </div>
  <div class="card card-accent">
    <h3>重點卡片</h3>
    <p>需要突出的內容。</p>
  </div>
</div>
```
```css
.card-grid { display:grid; gap:16px; margin:24px 0; }
.card-grid.cols-2 { grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }
.card-grid.cols-3 { grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); }
.card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); padding:22px 24px; }
.card h3 { font-size:16px; margin-bottom:10px; }
.card p { font-size:14px; color:var(--text-2); }
.card-accent { border-top:3px solid var(--accent); }
```

## 6. 資料表格

```html
<div class="table-wrap">
<table class="table">
  <thead><tr><th>項目</th><th>負責人</th><th class="num">數量</th><th>狀態</th></tr></thead>
  <tbody>
    <tr><td>Router 優化</td><td>秉陞</td><td class="num">1,240</td><td><span class="badge badge-ok">完成</span></td></tr>
  </tbody>
</table>
</div>
```
```css
.table-wrap { overflow-x:auto; margin:24px 0; border:1px solid var(--border); border-radius:var(--radius); }
.table { width:100%; border-collapse:collapse; font-size:14px; background:var(--surface); }
.table th { background:var(--surface-2); text-align:left; font-weight:600; padding:11px 16px; border-bottom:1px solid var(--border); white-space:nowrap; }
.table td { padding:11px 16px; border-bottom:1px solid var(--border); color:var(--text-2); }
.table tbody tr:last-child td { border-bottom:none; }
.table .num { text-align:right; font-family:var(--font-mono); font-variant-numeric:tabular-nums; }
.table tbody tr:hover { background:var(--accent-soft); }
```
數字欄一律 `.num`；金額加千分位；空值顯示 `—` 不留白。

## 7. 比較表格（highlight 欄）

```html
<div class="table-wrap">
<table class="table compare">
  <thead><tr><th>面向</th><th>方案 A</th><th class="hl">方案 B（建議）</th><th>方案 C</th></tr></thead>
  <tbody>
    <tr><td>成本</td><td>高</td><td class="hl">中</td><td>低</td></tr>
  </tbody>
</table>
</div>
```
```css
.compare .hl { background:var(--accent-soft); font-weight:600; color:var(--text); border-left:2px solid var(--accent); border-right:2px solid var(--accent); }
.compare thead .hl { color:var(--accent); }
```

## 8. 圖表容器

```html
<div class="chart-card">
  <div class="chart-head">
    <h3>圖表標題（含結論）</h3>
    <span class="chart-sub">單位 / 期間</span>
  </div>
  <div class="chart-body"><canvas id="chart1"></canvas></div>
  <div class="chart-note">資料來源與備註。</div>
</div>
```
```css
.chart-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--shadow); padding:22px 24px; margin:24px 0; }
.chart-head { display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px; margin-bottom:16px; }
.chart-head h3 { font-size:16px; }
.chart-sub { font-size:12.5px; color:var(--text-3); font-family:var(--font-mono); }
.chart-body { position:relative; height:300px; }
.chart-note { font-size:12px; color:var(--text-3); margin-top:12px; }
```
`chart-body` 必須固定高度，否則 Chart.js 會無限撐高。圖表寫法見 `charts.md`。

## 9. Callout

```html
<div class="callout callout-warning">
  <div class="callout-title">風險</div>
  <p>說明內容。</p>
</div>
```
```css
.callout { border:1px solid var(--border); border-left-width:4px; border-radius:var(--radius-sm); padding:16px 20px; margin:20px 0; background:var(--surface); }
.callout-title { font-weight:700; font-size:13.5px; margin-bottom:6px; }
.callout p { font-size:14px; color:var(--text-2); }
.callout-info    { border-left-color:var(--info); }    .callout-info .callout-title{ color:var(--info); }
.callout-success { border-left-color:var(--ok); }      .callout-success .callout-title{ color:var(--ok); }
.callout-warning { border-left-color:var(--warn); }    .callout-warning .callout-title{ color:var(--warn); }
.callout-danger  { border-left-color:var(--danger); }  .callout-danger .callout-title{ color:var(--danger); }
```

## 10. 時間軸

```html
<div class="timeline">
  <div class="tl-item">
    <div class="tl-time">08/05</div>
    <div class="tl-dot"></div>
    <div class="tl-body"><strong>事件標題</strong><p>說明。</p></div>
  </div>
</div>
```
```css
.timeline { margin:24px 0; }
.tl-item { display:grid; grid-template-columns:64px 20px 1fr; gap:0 12px; padding-bottom:24px; position:relative; }
.tl-time { font-family:var(--font-mono); font-size:12.5px; color:var(--text-3); text-align:right; padding-top:2px; }
.tl-dot { width:10px; height:10px; border-radius:50%; background:var(--accent); margin:5px auto 0; position:relative; z-index:1; }
.tl-item::before { content:""; position:absolute; left:calc(64px + 12px + 9px); top:16px; bottom:-4px; width:2px; background:var(--border); }
.tl-item:last-child::before { display:none; }
.tl-body strong { font-size:14.5px; }
.tl-body p { font-size:13.5px; color:var(--text-2); margin-top:4px; }
```

## 11. 進度條

```html
<div class="progress-row">
  <span class="progress-label">WP-3 TASK閉環</span>
  <div class="progress"><div class="progress-bar" style="width:72%"></div></div>
  <span class="progress-val">72%</span>
</div>
```
```css
.progress-row { display:grid; grid-template-columns:minmax(120px,180px) 1fr 48px; gap:14px; align-items:center; margin:10px 0; font-size:13.5px; }
.progress { height:8px; background:var(--surface-2); border-radius:99px; overflow:hidden; }
.progress-bar { height:100%; background:var(--accent); border-radius:99px; }
.progress-val { font-family:var(--font-mono); color:var(--text-2); text-align:right; }
```

## 12. 標籤 Badge

```html
<span class="badge badge-accent">進行中</span>
<span class="badge badge-ok">完成</span>
<span class="badge badge-warn">風險</span>
<span class="badge badge-danger">阻塞</span>
<span class="badge">一般</span>
```
```css
.badge { display:inline-block; font-size:11.5px; font-weight:600; font-family:var(--font-mono); padding:3px 10px; border-radius:99px; background:var(--surface-2); color:var(--text-2); border:1px solid var(--border); }
.badge-accent { background:var(--accent-soft); color:var(--accent); border-color:transparent; }
.badge-ok { background:color-mix(in srgb, var(--ok) 12%, transparent); color:var(--ok); border-color:transparent; }
.badge-warn { background:color-mix(in srgb, var(--warn) 14%, transparent); color:var(--warn); border-color:transparent; }
.badge-danger { background:color-mix(in srgb, var(--danger) 12%, transparent); color:var(--danger); border-color:transparent; }
```

## 13. 引用

```html
<blockquote class="quote">
  <p>「引用內容。」</p>
  <cite>— 出處</cite>
</blockquote>
```
```css
.quote { border-left:3px solid var(--accent); padding:6px 0 6px 22px; margin:24px 0; }
.quote p { font-family:var(--font-display); font-size:18px; color:var(--text); }
.quote cite { display:block; margin-top:8px; font-size:13px; color:var(--text-3); font-style:normal; }
```

## 14. 程式碼區塊

```html
<pre class="codeblock"><code>ARK_ROUTER_ENABLED=true</code></pre>
```
```css
.codeblock { background:var(--surface-2); border:1px solid var(--border); border-radius:var(--radius-sm); padding:16px 18px; overflow-x:auto; margin:20px 0; }
.codeblock code { font-family:var(--font-mono); font-size:13px; line-height:1.7; color:var(--text); }
```

## 15. 雙欄

```html
<div class="two-col">
  <div>左欄內容</div>
  <div>右欄內容</div>
</div>
```
```css
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:24px 0; }
@media (max-width:700px){ .two-col{ grid-template-columns:1fr; } }
```

## 16. N-M-P-Q 區塊（研七報告格式）

```html
<div class="nmpq">
  <div class="nmpq-item"><div class="nmpq-key">N</div><div><strong>Needs</strong><p>需求描述。</p></div></div>
  <div class="nmpq-item"><div class="nmpq-key">M</div><div><strong>Methods</strong><p>方法。</p></div></div>
  <div class="nmpq-item"><div class="nmpq-key">P</div><div><strong>Plan</strong><p>計畫。</p></div></div>
  <div class="nmpq-item"><div class="nmpq-key">Q</div><div><strong>Quantitative</strong><p>量化指標。</p></div></div>
</div>
```
```css
.nmpq { display:grid; gap:12px; margin:24px 0; }
.nmpq-item { display:grid; grid-template-columns:44px 1fr; gap:16px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:18px 20px; }
.nmpq-key { width:44px; height:44px; display:grid; place-items:center; background:var(--accent-soft); color:var(--accent); font-family:var(--font-display); font-weight:700; font-size:20px; border-radius:var(--radius-sm); }
.nmpq-item strong { font-size:14.5px; }
.nmpq-item p { font-size:13.5px; color:var(--text-2); margin-top:4px; }
```

## 17. 頁尾

```html
<footer class="report-footer">
  <span>研七 · Ark Agent Platform</span>
  <span>產出於 2026-08-11 · 內部文件</span>
</footer>
```
```css
.report-footer { display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-top:64px; padding-top:20px; border-top:1px solid var(--border); font-size:12.5px; color:var(--text-3); }
```
