# 圖表（Charts）

兩種模式：**Chart.js**（互動、螢幕閱讀）與**純 SVG**（列印/PDF 穩定、零依賴）。顏色一律從 token 讀取，換風格自動跟色。

## Chart.js 基礎設定

CDN（放 `</body>` 前）：
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
```

**Token 讀取 helper + 全域設定**（每份報告只寫一次）：
```html
<script>
const css = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
const C = ['--c1','--c2','--c3','--c4','--c5','--c6'].map(css);
const isDark = matchMedia && document.body.dataset.theme === 'dark'; // midnight 風格在 body 加 data-theme="dark"
Chart.defaults.font.family = css('--font-body');
Chart.defaults.color = css('--text-2');
Chart.defaults.borderColor = isDark ? 'rgba(255,255,255,.07)' : css('--border');
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.boxHeight = 12;
</script>
```

## 常用圖表模式

### 長條圖（比較）
```js
new Chart(document.getElementById('chart1'), {
  type: 'bar',
  data: {
    labels: ['一月','二月','三月'],
    datasets: [{ label:'營收', data:[120,190,150], backgroundColor:C[0], borderRadius:4, maxBarThickness:48 }]
  },
  options: { plugins:{ legend:{ display:false } }, scales:{ y:{ beginAtZero:true } }, maintainAspectRatio:false }
});
```

### 折線圖（趨勢）
```js
{
  type: 'line',
  data: { labels, datasets: [{
    label:'DAU', data, borderColor:C[0], borderWidth:2.5,
    backgroundColor:'transparent', pointRadius:0, pointHitRadius:12, tension:.3
  }]},
  options: { maintainAspectRatio:false, interaction:{ mode:'index', intersect:false } }
}
```
面積填色版：`backgroundColor` 用 accent 的透明版（如 `C[0]+'22'` 若 C 是 hex），`fill:true`。

### 環圈圖（占比）
```js
{
  type: 'doughnut',
  data: { labels:['A','B','C'], datasets:[{ data:[45,30,25], backgroundColor:[C[0],C[1],C[2]], borderWidth:0 }]},
  options: { maintainAspectRatio:false, cutout:'62%', plugins:{ legend:{ position:'right' } } }
}
```
占比項目 > 6 個時合併成「其他」，不要撒 10 種顏色。

### 水平長條（排名/長標籤）
`type:'bar'` + `options:{ indexAxis:'y' }`。項目多、中文標籤長時優先用這個而非直式長條。

### 雷達圖（多維評估）
```js
{ type:'radar', data:{ labels:['效能','成本','穩定','擴充','維運'],
  datasets:[
    { label:'方案A', data:[4,3,5,4,3], borderColor:C[0], backgroundColor:'transparent', borderWidth:2 },
    { label:'方案B', data:[3,5,3,5,4], borderColor:C[1], backgroundColor:'transparent', borderWidth:2 }
  ]},
  options:{ maintainAspectRatio:false, scales:{ r:{ min:0, max:5, ticks:{ stepSize:1 } } } } }
```

## 純 SVG 圖表（列印/paperprint 風格優先）

零依賴、列印穩定。適合簡單長條與占比條。顏色直接用 `var(--c1)` 寫在 SVG 屬性裡。

### 水平長條
```html
<svg viewBox="0 0 600 130" style="width:100%;height:auto" role="img" aria-label="各項目數量比較">
  <g font-size="13" fill="var(--text-2)">
    <text x="0" y="24">項目A</text><rect x="90" y="12" width="380" height="16" rx="3" fill="var(--c1)"/><text x="478" y="24" font-family="var(--font-mono)">380</text>
    <text x="0" y="54">項目B</text><rect x="90" y="42" width="240" height="16" rx="3" fill="var(--c2)"/><text x="338" y="54" font-family="var(--font-mono)">240</text>
    <text x="0" y="84">項目C</text><rect x="90" y="72" width="150" height="16" rx="3" fill="var(--c3)"/><text x="248" y="84" font-family="var(--font-mono)">150</text>
  </g>
</svg>
```
`rect` 寬度依比例換算（最大值對應可用寬度）。

### 占比條（stacked bar）
```html
<div style="display:flex;height:14px;border-radius:99px;overflow:hidden;margin:12px 0">
  <div style="width:45%;background:var(--c1)"></div>
  <div style="width:30%;background:var(--c2)"></div>
  <div style="width:25%;background:var(--c3)"></div>
</div>
```
下方配 legend（小色塊 + 標籤 + 百分比）。

## 圖表選型速查

| 資料型態 | 圖表 |
|----------|------|
| 類別比較（<8 項） | 長條 / 水平長條 |
| 時間趨勢 | 折線 |
| 占比（<6 塊） | 環圈 / 占比條 |
| 多方案多維比較 | 雷達 / 比較表格 |
| 進度 vs 目標 | 進度條元件 |
| 精確數值很重要 | 直接用表格，不要硬畫圖 |

## 注意事項

- `chart-body` 容器必須固定高度（如 300px），Chart.js 的 `maintainAspectRatio:false` 才能正常
- midnight 深色風格：在 `<body data-theme="dark">` 標記，讓 helper 換 grid 色
- 一張圖只講一件事；標題寫結論（「行動端占比首次過半」）而非變數名（「平台分布」）
- 列印場景（paperprint 或使用者要轉 PDF）：優先 SVG。若必須用 Chart.js，加 `devicePixelRatio: 2` 並提醒使用者列印前等圖表渲染完成
