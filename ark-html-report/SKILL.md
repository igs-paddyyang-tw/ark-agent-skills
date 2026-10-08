---
name: ark-html-report
description: 產出專業的單檔 HTML 報告（技術報告、日報/週報、數據分析、競品分析、專案總結、N-M-P-Q 報告）。使用此 skill 當使用者要求「做一份報告」「產出 HTML 報告」「整理成報告頁面」「做一個 dashboard 風格的總結」，或要把分析結果、數據、文件內容排版成可分享的網頁時。內含 5 種風格預設（token 系統）與完整元件庫（卡片、圖表、表格、時間軸、callout、圖片 figure／gallery 等），元件與風格可任意組合。報告要放素材圖或示意圖時，附 html_images.py 放圖引擎：本機圖片自動縮圖、轉 WebP、去重後內嵌成零外部請求的單檔，並可自動排成圖說與圖庫（3.6 節）。與 ark-md-report 成對：本 skill 是 View 軌（給人看的網頁），給 AI／知識庫消費的結構化 Markdown 走 ark-md-report。不適用於：互動式數據儀錶板（篩選、排序、Chart.js）請用 ark-html-dashboard。
metadata:
  version: "1.2.0"
  schema_version: 1
  status: active
  updated: 2026-10-08
  category: view
  outputs:
    - format: html
      audience: human
  depends_on: []
  requires: [Pillow]          # 只有 scripts/html_images.py 需要
  author: paddyyang
---

# HTML Report

產出**單一自包含 HTML 檔**的專業報告。核心設計：

- **風格 = token**：每種風格是一組 CSS variables（`references/styles.md`）
- **元件 = 消費 token 的 HTML 片段**（`references/components.md`）
- 任何元件 × 任何風格都能直接組合，換風格只需換 `:root` 區塊

## 工作流程

### 1. 理解內容與受眾

先確認報告的：主題、資料來源（使用者提供的文字/數據/檔案）、受眾（主管簡報？團隊內部？對外分享？）、是否需要列印/轉 PDF。

### 2. 選擇風格

讀 `references/styles.md`。五種預設：

| 風格 | 適合場景 |
|------|----------|
| `boardroom` 企業簡報 | 給主管/客戶的正式報告、季度總結、提案 |
| `terminal` 技術文件 | 架構設計、技術評估、系統文件、code review 報告 |
| `midnight` 深色儀表板 | 數據監控、KPI 總覽、營運日報、metrics-heavy 內容 |
| `editorial` 雜誌編輯 | 競品分析、市場洞察、長文閱讀型報告 |
| `paperprint` 極簡印刷 | 需要列印或轉 PDF 的正式文件、會議紀錄 |

選擇方式：
- 使用者指定風格 → 直接用
- 未指定但場景明確 → 自行挑選並**在回覆中說明選了什麼、為什麼**
- 場景模糊或使用者可能在意外觀 → 用一句話介紹 2-3 個候選風格讓使用者選

也可以基於某個預設微調（換 accent 色、換字體），在 token 層改，不要改元件的 CSS。

### 3. 組裝元件

讀 `references/components.md`，依內容挑選元件。常見報告結構：

```
封面標頭 → 摘要（executive summary）→ KPI 卡片列 →
各章節（章節標題 + 內文/卡片網格/表格/圖表/時間軸/callout）→ 頁尾
```

原則：
- 元件的 class 名稱與結構照抄 reference，不要自創變體 —— 一致性讓後續維護容易
- 數據多 → 表格 + 圖表；結論導向 → 卡片 + callout；過程敘事 → 時間軸
- N-M-P-Q 報告使用 `nmpq` 元件（四段式：Needs → Methods → Plan → Quantitative）
- 內容為主，裝飾為輔。每個元件都要承載真實內容，不要為了好看塞空卡片

### 3.5 決定交付模式：標準或 offline

**先確認報告要怎麼送到讀者手上**，這決定能不能用外部資源：

| 交付通道 | 模式 | 骨架 |
|----------|------|------|
| 瀏覽器開啟、需要互動圖表 | 標準（允許 Chart.js + Google Fonts） | `assets/template.html` |
| **TG／Slack／Email 附件** | **offline** | `assets/template-offline.html` |
| 內網／封閉網路、長期歸檔、通道不明 | **offline** | 同上 |

附件類一律 offline —— 讀者常在手機上點開，可能沒有網路。CDN 一掉，字體與圖表同時失效。
規範與檢查清單見 `references/offline-mode.md`。

### 3.6 放圖（報告有截圖、素材圖時）

**不要手動 base64，也不要把原圖直接塞進 HTML。** 一張 1080×1920 截圖原檔就 2～3 MB，十幾張就幾十 MB。
流程是「寫 HTML 時用相對路徑引用圖 → 交付前跑放圖引擎」：

1. 寫 HTML 時照常用 `<img src="screens/main_01.png" alt="圖說">`（路徑相對報告檔，或絕對路徑）；
   想讓引擎幫忙排版，就讓圖獨立成段（`<p><img …></p>`），連續幾張會自動排成圖庫。
2. 需要時用 `data-role` 指定用途：`icon`（圖示、圖騰）／`portrait`（直式截圖）／`landscape`（橫式截圖、照片）／`diagram`（圖表、流程圖，保持銳利）／`full`（不縮）；不寫就依原圖尺寸自動判斷。
3. 交付前跑：
   ```bash
   python scripts/html_images.py embed report.html --layout --lightbox --out report.final.html
   ```
   - `--layout`：獨立的圖包成 `<figure>`（alt 當圖說），連續的圖排成 `.ar-gallery`；直式截圖限寬 360、圖示限寬 160
   - `--lightbox`：點圖放大
   - `--quality lite|standard|hi`（預設 standard）、`--format jpeg`（要相容很舊的瀏覽器時）、`--budget-mb 8`（超過就擋，列出前 10 大張圖）、`--role 'symbols/*=icon'`（依路徑批次指定用途，可重複；同一張圖在 `<img>` 與 JSON 都被引用時用它讓兩邊共用一份）
   - 先看會多大：`python scripts/html_images.py inspect report.html`
4. 回覆使用者時報 `delivery` 那行：幾張圖、原圖幾 MB → 內嵌後幾 MB。

| 用途 | 自動判斷 | 最大寬（standard）| 典型大小 |
|---|---|---|---|
| icon | 長邊 ≤ 400 | 240 | 3～8 KB |
| portrait | 高 ≥ 1.3 × 寬 | 560 | 40～80 KB |
| landscape | 其他 | 800 | 40～90 KB |
| diagram | 只能手動指定 | 1200（無損）| 視內容 |

內嵌方式自動選：沒有重複引用 → 直接 data URI（零 JS，信件預覽也能看）；同一張圖用很多次或頁面 JS 的資料裡有圖（燈箱、gallery JSON 的 `"src"`）→ 圖只存一份在 `window.__IMG`，頁面 JS 用 `window.__imgsrc(s)` 取圖。完整規格見 `references/images.md`。

### 4. 圖表（如有數據）

讀 `references/charts.md`。標準模式用 Chart.js CDN，顏色一律取自 token（`--c1`~`--c6`），
這樣換風格圖表配色會跟著換。**offline 模式與需要列印的報告一律走純 SVG**（reference 內有模式）。

### 5. 產出與 QA

- 單一 `.html` 檔，所有 CSS 內嵌於 `<style>`；有本機圖片的一律跑過 `scripts/html_images.py embed`（`grep -c 'src="[^d#h]' ` 應為 0：沒有殘留本機路徑）
- 標準模式最多兩個外部資源（Chart.js、Google Fonts）；**offline 模式零外部資源**
- 從對應骨架開始（`assets/template.html` 或 `assets/template-offline.html`），貼入所選風格的 `:root` 區塊與基礎樣式
- offline 模式交付前跑一次 `references/offline-mode.md` 的檢查指令，並**實際斷網開啟確認**
- 檢查：中文字體正常（Noto Sans TC 載入前的 fallback 是 Microsoft JhengHei / PingFang TC）、手機寬度不破版、`@media print` 生效、深色風格的文字對比足夠
- 主題：`body` 一定要明確設 `background: var(--bg)`。沒設會透出檢視器自己的底色 —— 在深色檢視器裡看到淺色文字配深色底，整份糊掉。元件只讀 token，不要把顏色的唯一定義寫在 `@media` 或 `[data-theme]` 區塊裡
- 產出到 `/mnt/user-data/outputs/` 並用 present_files 呈現

## 內容撰寫原則

- 標題句要有資訊量：「Q3 營收成長 23%，行動端貢獻過半」優於「Q3 營收報告」
- KPI 卡片的 delta（↑↓）要標示比較基準（vs 上週 / vs 目標）
- 🇹🇼 **漲跌配色**：一般 KPI 好壞用 `.up`(綠)/`.down`(紅)；**台股/華人財經漲跌**用 `.tw-up`(紅=漲)/`.tw-down`(綠=跌)——依方向不依好壞（見 components.md 台股變體與 styles.md 的 `--tw-up/--tw-down`）。進度條/圖表漸層等非漲跌元素維持原色
- 表格數字右對齊、加千分位；重點欄位可用 accent 色標記
- Callout 依語意選類型：info（補充）、success（達成）、warning（風險）、danger（阻塞）
- 摘要寫給「只看 30 秒的人」：結論先行，3-5 個 bullet
