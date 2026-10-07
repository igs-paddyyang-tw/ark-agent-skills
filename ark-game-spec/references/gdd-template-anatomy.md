# 企劃樣板拆解（data/gdd-sample/賭博默示錄_素材總覽.html → gdd-pack）

> 為什麼契約長這樣：企劃 2026-09-16 交出的樣板其實是「資料 + 模板」——靜態骨架只有標題與規則列，
> 圖騰牆 / 畫面流程 / 對照表 / INFO / 多語全由 8 個 JS 陣列渲染。gdd-pack 就是把那 8 個陣列顯式化。

## 樣板資料結構 → 契約

| 樣板 JS | 內容 | 契約落點 | 刻意改動 |
|---------|------|----------|----------|
| `SYMBOLS[]` | g/code/id/name/file(美術名)/ref/odds/desc/scene/dot/guess | `symbols.yaml` | `file` 改為工程命名實檔；美術名移到 `art_name`；`dot: var(--red)` → `color: red`；`guess` → `flag`/`role` |
| `SOFT{}` | 美術名 → 軟體命名 | 併入 symbols（`soft` + `file`） | 不再需要對照表；`soft:false` 取代「查無」 |
| `UPDATED` | 較新版集合 | `symbols[].updated` | — |
| `COMP{}` | code → 規格書原圖/參考圖 | `symbols[].ref_files` | lint 擋參考圖進 file |
| `SCREENS[]` | g/step/title/file|null/from/lang/guess/desc | `screens.yaml` | `g` → `feature`（對到 gdd.features）；`guess` → `issue` |
| `INFO[]` | t/en/tw/jp | `info.blocks` | 賠率表由「en === 'ODDS TABLE'」硬判 → `widget: odds_grid` |
| `PH{}` | 佔位符 → 檔名 | `info.placeholders` → code | 對到 code 不對到檔名，換圖不用改 INFO |
| `SLOTS[]` | 「INFO 第 occ 次出現這句英文之後」插圖 | `info.slots[].after = block id` | 顯式 id 錨點，改文案不斷 |
| `LANGROWS[]` | 74 列 × 8 欄 | `i18n.csv` | 欄位由 `gdd.i18n_columns` 宣告 |
| 靜態規則 `<ul class="rules">` + 表格 | 主/免費/彩金/階段面板 | `rules/<feature>.md` | 資料化；mini-markdown |
| header `.spec` + kv 表 | 兩份手寫 | `gdd.spec[]`（short / v / kv） | 單一來源 |
| `<nav>` 十段 | 固定 | 由 features 動態產生（一玩法一章） | 新玩法只加 features |
| lightbox / 搜尋 / 複製 | JS | 保留（改讀 data-* 與 GALLERY JSON） | server-side 先渲染卡片，無 JS 也能讀 |

## 樣板裡的真實瑕疵（golden case 的 lint 要抓到）

- `賭博默示錄_JP報獎_轉場宣告_0904_修愷.png.png` 雙副檔名 → GDD-SCR-HYGIENE
- 免費宣告面板 3×5 / 4×5 顏色對調（樣板以 guess 標）→ GDD-SCR-ISSUE
- `Snipaste_…`、`圖層 4.png` 泛用檔名 → GDD-SCR-HYGIENE
- 12 張待補示意圖、2 個 INFO 插圖待補 → todo.md

## 保留不動的長相

配色（暗棕金）、卡片尺寸、9:16 縮圖、odds 三格、tag 樣式、lightbox 右側資訊欄——全部沿用；只把顏色抽成 token（`assets/default-style.yaml`）。企劃樣板優先於圖書館一致性。
