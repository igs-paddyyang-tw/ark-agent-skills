# A4 文件版面（多頁，Markdown 直接轉）

> 與 `a4-infocard.md` 並列：**圖卡＝單頁、手工組版**；**文件＝多頁、Markdown 原稿直接轉**。
> 專案計畫書、規格書、分析報告要列印或存 PDF 時用這個。

## 什麼時候用

| 需求 | 用 |
|---|---|
| 「A4 文件」「計畫書 A4」「規格書列印版」「轉 PDF 的文件」、多頁、要交出去印 | **本版面**：`scripts/md_to_a4.py` |
| 「做一張圖卡」「A4 一頁講清楚」 | `a4-infocard.md`（單頁） |
| 捲動閱讀、要目錄、hero、KPI、公開版 | ark-md-report 的 `build_report_html.py` |

## 用法

```bash
S=<ark-html-report>/scripts
python $S/md_to_a4.py docs/plans/x-plan.md docs/plans/x-plan.html --kick "<專案> ・ 專案計畫書"
python $S/md_to_a4.py docs/reports/review/x.md docs/reports/review/x.html --style boardroom
python $S/md_to_a4.py --list-styles
```

| 參數 | 說明 |
|---|---|
| `--style` | 五種風格之一（讀 `styles.md` 的 token），預設 `paperprint`（列印最穩）；深色風格會照樣印出背景，較耗墨 |
| `--kick` | 報頭小字，建議「<專案> ・ <文件類型>」；不給就不顯示 |
| `--playwright` | 原稿有 ```mermaid 圖才需要（同 ark-md-report）；也可用環境變數 `PW_DIR` |
| `--no-webfont` | 不載入 Google Fonts，用系統字型（離線環境） |
| `--stamp`／`--no-stamp` | 強制寫／不寫雙軌戳記（預設：原稿 frontmatter 有 `source_skill: ark-md-report` 才寫） |

**相依**：python-markdown；mermaid 另需同一棵 skills 樹裡有 ark-md-report（沿用它的渲染），沒有時保留原始碼區塊並提示。

## 版面規則（腳本已內建）

- **報頭**：frontmatter 的 `title`；`version／date／created／updated／status／verdict` 放小字；內文開頭的 H1 與標題**相同才**拿掉
- **分頁**：`@page A4`、頁尾右下「頁碼 / 總頁數」；表格列、程式碼、引言、圖不跨頁切斷；`h1～h3` 不孤立在頁尾；長表格每頁重複表頭
- **頁尾**：原稿路徑（在目前目錄底下用相對路徑，否則只放檔名，不洩漏 home 路徑）
- **deterministic**：不寫產生日期，同一份原稿重產內容相同 → 戳記與 diff 不會無故變動
- **frontmatter**：容許 BOM、CRLF；只讀單行 `key: value`，不需 PyYAML

## 驗收

```bash
CH=$(ls -d ~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome | tail -1)
"$CH" --headless --no-sandbox --no-pdf-header-footer --print-to-pdf=out.pdf file://$PWD/x.html
```

- 看 PDF：每頁有頁碼、表格沒有被切在列中間、中文字型正常
- 原稿是報告：`python <ark-md-report>/scripts/report_pair.py check <src.md>` → `OK`

> 實測（fish-bot，2026-11-19）：專案計畫書 12 章 → 5 頁、架構決策報告 → 3 頁，頁碼與表格正常。
