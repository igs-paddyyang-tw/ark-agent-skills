# View 軌契約 — prob-spec.html（ps_html，1.4 md-first）

## 讀什麼、不讀什麼

| 來源 | 用在 | 不可 |
|---|---|---|
| `prob-spec.md` | **一切**：KPI、表格、長條、色階、旗標、帶面、人工區、流程圖——全部從 md 的契約表格（prob-spec-contract.md §表格契約）讀 | 不讀 prob-data.json 的數字（1.3 起；避免兩套數字）|
| `prob-spec.meta.json` | verdict / pending_params / md sha / 來源 sha（選配；沒有也能渲染）| — |
| `prob-data.json` | 只拿 `raw_log` 放「原始快測輸出」摺疊區（選配）| 不拿任何數字 |
| 手填 | **禁止**。頁面任何文字都要能回到 prob-spec.md | |

為什麼改成 md-first：xlsx 模式、qt 模式、人手照範本寫的 md，三者只要表頭照契約命名，就得到**同一套** View；
沒有 xlsx（設計局、競品反解、只有快測產物）也能出和彌勒佛一樣完整的機率規格報告書。

## 表格 → 元件

| md 表（分類鍵，見 contract §表格契約）| 元件 |
|---|---|
| summary（§2 快測摘要）| 總覽 KPI 六格、RTP 組成 SVG + golden / 目標線、驗收守門（總 RTP 收斂、三向 checks、F-1 分佈、待決議數）；§2 本體不重印 |
| base | 緊湊數字表（全 0 / 全 — 列省略）|
| symhit | 列內色階（x2…x5，全 0 欄省略）+ TOTAL 粗體；兩張相鄰 → 左右並排 |
| reelset_rtp / range / multiple / asset / decile / fg_groups | 長條 + 數字表；range+multiple、asset+decile 相鄰 → 並排 |
| reelsets | 換帶旗標（0/1）或用組號碼（表頭含「用組」）+ 權重長條 + 佔比 + Σ 列；RTP 欄自動 ×100 |
| paytable / odds / strip_counts | 符號 chip（M 高賠藍、低賠灰、WW 綠、SC 橘、SS 金）；odds 全 0 欄省略、待決議紅字；strip_counts 每組一張熱度表 |
| weights / yesno / dual / matrix / series / kv | 長條 + % + Σ ／ 是否條 ／ 雙欄配對條 ／ 列內色階（尾端全 0 欄省略、>12 欄 tight）／ 序列條 ／ 規格格（≤ 24 列）|
| generic | 緊湊表；數字欄右對齊；超長格摺疊；「來源」欄移到列 title（滑過可見）|
| ```strip 帶面 | 每軸一行、每 10 格標位置、符號依類別上色，預設摺疊 |
| ```mermaid | mermaid（CDN；離線顯示原始碼）|
| `<!-- human:* -->` | 虛線「人工填寫區」框，內容走最小 markdown |

任一表渲染失敗 → 退回通用表（頁面不炸）。

## 章節（固定 9 段，id 固定供 deep-link）

| id | 標題 | 內容 | 無資料時 |
|---|---|---|---|
| overview | 總覽：規格與快測一眼看 | 由 §2「快測摘要」表產生：KPI 六格（總 RTP 對 golden / 目標 差、MG / FG RTP、觸發率、均倍、最大倍數）、RTP 組成條 + golden / 目標線、驗收守門表（RTP 收斂 / 三向 checks / 強中弱分佈 / 待決議數）；沒有摘要表時從 BASE INFO 表回推 | 「未快測」callout + 守門表 |
| brief | 規格簡述 | 基本規格格、機率人員簡述卡、Pay table、xlsx 簡述分頁原文（折疊）| 「（無資料）」|
| data | 數據資料（快測結果）| md §2 逐表（摘要表除外）：BASE INFO、符號命中熱度 ×2、輪帶組理論 vs 實測、贏分區間 + 倍數頻率、100 手資產 + 十分位、FG 強中弱 vs 權重、FG 詳細格；prob-data.json 在時附原始輸出折疊 | 段落逐一略過 |
| flow | 機率流程圖 | md §3 原樣（mermaid + 人工區）| （無流程圖）|
| params | 參數表 | md §4 逐表：`### 表 X-n　標題` → tid 標籤；表依分類渲染（上表）；未辨識 → generic 表 | — |
| kcards | 競品資料／手法對應 | md human:competitor | 提示未填 |
| hidden | 隱性規則與設計目的 | md §6（xlsx 原文清單 + human:hidden-rules）| 提示未填 |
| strips | 輪帶 Strip | md「## 輪帶 Strip（附錄）」：每組 strip_counts 熱度表 + ```strip 帶面；只有 §4 有 strip_counts 時指回 §4 | 無則整段不出現（導覽同步少一項）|
| appendix | 來源與版本 | frontmatter sources（+ meta sha）、md sha / verdict、邊界聲明 | — |

## 戳記與一致性

- 第一行 `<!-- content-src: prob-spec.md sha256:<md sha16> -->`，`<title>` 緊接其後（發佈端只掃前 8KB）。
- 頁尾重複 content-src 與產出日期。
- md 改了 → html 戳記不符 → ps_lint PS-STALE error；重跑 ps_html 即可。

## Token 契約（與 ark-html-report styles.md 同名變數，可整組換色）

`--bg --surface --surface-2 --border --text --text-2 --text-3 --accent --accent-soft --ok --warn --danger --info --c1~--c6 --font-display --font-body --font-mono --radius --radius-sm --shadow --maxw`
加本 skill 專用：`--g1~--g4`（強中弱序列色，深→淺）、`--sym-high/--sym-low/--sym-wild/--sym-sc/--sym-ss`（符號類別色）。
三段定義：`:root` 亮色；`@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` 與 `:root[data-theme="dark"]` 暗色（含 `color-scheme: dark`）。圖表色盤經 dataviz 驗證（CVD 鄰近對比 ≥ 8、對底 ≥ 3:1）。

## 版面

- 寬 ≥ 980px：左側 200px 黏性章節導覽 + 內容；窄：導覽變頂端橫向膠囊列。
- 所有表格在 `.table-wrap{overflow-x:auto}` 內；頁面本體不橫向捲動（400px 驗過）。
- 數字欄 `font-variant-numeric: tabular-nums`；第一欄 nowrap。
- `--body-only`：不含 doctype / html / head / body，給會自己包骨架的發佈端（如 claude.ai Artifact）。

## 外連

只有 Google Fonts（Noto Sans TC / JetBrains Mono，皆有系統字 fallback）與 mermaid CDN（`cdn.jsdelivr.net/npm/mermaid@10`）；其餘全部內嵌。
