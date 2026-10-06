# View 軌契約 — prob-spec.html（ps_html）

## 讀什麼、不讀什麼

| 來源 | 用在 | 不可 |
|---|---|---|
| `prob-data.json` | 所有數字：KPI、表格、長條、色階、輪帶 | — |
| `prob-spec.md` 人工區 | §1 機率人員簡述、§3 流程補充、§4 參數備註、§5 手法對應、§6 隱性規則 | 不讀 md 的數字表（避免兩套數字）|
| `prob-spec.meta.json` | verdict、pending_params、md sha | — |
| 手填 | **禁止**。頁面任何文字都要能回到上面三個檔 | |

## 章節（固定 9 段，id 固定供 deep-link）

| id | 標題 | 內容 | 無資料時 |
|---|---|---|---|
| overview | 總覽：規格與快測一眼看 | KPI 六格（總 RTP 對 golden 差、MG / FG RTP、觸發率、均倍、最大倍數）、RTP 組成條 + golden 線、驗收守門表（RTP 收斂 / FG RTP / 強中弱分佈 / 待決議數）| 「未快測」callout + 守門表 |
| brief | 規格簡述 | 基本規格格、機率人員簡述卡、Pay table、xlsx 簡述分頁原文（折疊）| 「（無資料）」|
| data | 數據資料（快測結果）| 執行資訊格、BASE INFO、符號命中熱度 ×2、輪帶組理論 vs 實測（有 known.reelsets 時加旗標 / 理論欄 / 加權列）、贏分區間 + 倍數頻率、100 手資產 + 十分位、FG 詳細（卡片 4 格、觸發顆數、SC 顆數均倍、強中弱 vs 權重、SS 分項、乘倍十分位）、原始輸出折疊 | 段落逐一略過 |
| flow | 機率流程圖 | md §3 原樣（mermaid + 人工區）| （無流程圖）|
| params | 參數表 | 每個區塊一個 `<h3>`（表編號 tid）；recognizer 對應渲染：reelsets 旗標 + 權重條、weights 條 + %、dual 雙欄條、yesno 條、matrix 列內色階（尾端全 0 欄省略、>12 欄 tight）、series 條、scalars 大字卡；未辨識 → generic 表 | — |
| kcards | 競品資料／手法對應 | md human:competitor | 提示未填 |
| hidden | 隱性規則與設計目的 | xlsx 隱性規則分頁原文（折疊）+ md human:hidden-rules | 提示未填 |
| strips | 輪帶 Strip | 每組：顆數表（色階 = 佔該輪比例）+ 帶面（每 10 格一組、標位置；符號依類別上色）| 「xlsx 無輪帶分頁」|
| appendix | 來源與版本 | 來源表（xlsx sha / md sha / prob-data）、分頁清單（隱藏標記）、製作方針原文 | — |

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
