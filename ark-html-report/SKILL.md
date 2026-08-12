---
name: ark-html-report
description: 產出專業的單檔 HTML 報告（技術報告、日報/週報、數據分析、競品分析、專案總結、N-M-P-Q 報告）。只要使用者要求「做一份報告」「產出 HTML 報告」「整理成報告頁面」「做一個 dashboard 風格的總結」，或要把分析結果、數據、文件內容排版成可分享的網頁時，就使用此 skill。內含 5 種風格預設（token 系統）與完整元件庫（卡片、圖表、表格、時間軸、callout 等），元件與風格可任意組合。
metadata:
  category: view
  outputs:
    - format: html
      audience: human
  depends_on: []
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

### 4. 圖表（如有數據）

讀 `references/charts.md`。用 Chart.js CDN，顏色一律取自 token（`--c1`~`--c6`），這樣換風格圖表配色會跟著換。需要列印的報告優先考慮純 SVG 圖表（reference 內有模式）。

### 5. 產出與 QA

- 單一 `.html` 檔，所有 CSS 內嵌於 `<style>`，只允許 Chart.js 與 Google Fonts 兩個外部資源
- 從 `assets/template.html` 骨架開始，貼入所選風格的 `:root` 區塊與基礎樣式
- 檢查：中文字體正常（Noto Sans TC 載入前的 fallback 是 Microsoft JhengHei / PingFang TC）、手機寬度不破版、`@media print` 生效、深色風格的文字對比足夠
- 產出到 `/mnt/user-data/outputs/` 並用 present_files 呈現

## 內容撰寫原則

- 標題句要有資訊量：「Q3 營收成長 23%，行動端貢獻過半」優於「Q3 營收報告」
- KPI 卡片的 delta（↑↓）要標示比較基準（vs 上週 / vs 目標）
- 表格數字右對齊、加千分位；重點欄位可用 accent 色標記
- Callout 依語意選類型：info（補充）、success（達成）、warning（風險）、danger（阻塞）
- 摘要寫給「只看 30 秒的人」：結論先行，3-5 個 bullet
