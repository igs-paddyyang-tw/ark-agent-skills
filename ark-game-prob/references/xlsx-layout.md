# 公版「機率表 xlsx」讀取約定（ps_extract）

> 以 IGS 機率人員的公版（福星指路 → 開司 → 彌勒佛 v3 1001A 一脈）為準。ps_extract 不靠固定座標，靠**標籤錨 + 表頭判定**，
> 所以同一套公版、不同遊戲的參數表都能抽；抽不到時依本檔調 xlsx 標籤，而不是改腳本。

## 分頁名候選（大小寫 / 空白不敏感；可用 `--params-sheet` / `--data-sheet` 覆寫）

| key | 候選名 | 用途 |
|---|---|---|
| params | 參數表、參數 | **必要**。所有表 |
| data | 數據資料、數據、快測結果 | 快測報表原文（整段貼上）|
| main_strip / free_strip / fake_strip | Main Game Strip、Free Game Strip、Free Fake Strip | 輪帶帶面 + 總顆數 |
| guide / brief / hidden / notes | 機率規格書製作方針、規格簡述、隱性規則、機率表注意事項 | 文字原文（隱藏分頁也讀）|

隱藏分頁一樣會讀，並在 `sheets[].hidden` 標記；View 的附錄會列出全部分頁。

## 參數表：區塊與表

1. **標籤錨**：A～C 欄任一格以 `表 X-n`（如 `表M-1`、`表 F-3-1`、`表F-4-3`）開頭，或等於 `基本資訊` / `Odds表` / `Pay table` → 開新區塊，`id` 正規化為 `M-1`、`F-4-3`。標籤格剩餘文字（`表 F-2　FG 組別 → …`）或同列右側第一個字串 = 區塊標題。
2. **切表**：區塊內「連續非空列」為一張表；空列分隔。每張表以最小非空欄為左界。
3. **表頭判定**（`_header_row`）：
   - 跳過只有一格文字的列（當 caption，例：`金幣・出現次數（權重）`、`SC`）。
   - 一列有 ≥ 2 個字串 → 表頭；只有 1 個字串但是表頭字（權重 / Weight / 倍數 / 機率 / % / Total / 權重和）且同列有數字或下一列有數字 → 表頭。
   - 若下一列是更完整的純文字表頭（如 `SC | SS` 後面接 `圖騰倍數 | Weight | … | 圖騰倍數 | Weight`）→ 本列降為 caption。
4. **recognizer**（辨識常見結構，抓不到就留 generic 表）：

| 結構 | 判定 | 產出（known.*）| 公版例 |
|---|---|---|---|
| 基本資訊 | 區塊 id = 基本資訊，k/v 列 | board | 盤面 / 線數 / 基本收費 |
| Pay table | 表頭含 Symbol 與數字欄 | paytable[{tier, sym, odds}] | Odds表 |
| 輪帶組 | 表頭含 `Index` 與 `Weight`，`R1..Rn` 欄 | reelsets{sets[idx, flags, weight, extra], totals} | 表M-1（TOTAL RTP / FG RTP 進 extra；單獨一格的 1000 → weight_sum）|
| SC/SS 雙欄 | 表頭有兩個以上 `Weight` | dual{names（caption）, columns[pairs, total, extra]} | 表M-2 / M-5（`*2` 保留字串，ps_diff 轉負值）|
| 是/否表 | 表頭含 是、否 | yesno | 表M-3-1 / M-3-2 |
| 組別矩陣 | 表頭第一欄 `組別`、≥ 3 個數字欄名 | matrix{caption, head, groups}（到 `機率 Prob.` 列為止）| 表F-2 六張 |
| 橫向序列 | 每列 = 標籤 + 一串數字 | series{head, rows} | 表F-3-1、表F-4-3 |
| 權重表 | 表頭含 權重 / Weight（單欄）| weights{items[label, weight]} | 表F-1、M-4、F-4-2 |
| 單值 | 區塊只剩一個數字 | scalars | 表F-4-1、F-5 |

## 數據資料：FastTest 報表

把快測程式 stdout（或 result.txt）**整段貼進 B 欄**即可；第一個非空列若不是 `Workers:` 會當旗標（如 `開MAXWIN`）。
解析段落（缺段略過，`report.sections_found` 列出有哪些）：`Workers / Done in / 版本 / Times:TotalWin:TotalBet`、
`BASE INFO`、`Main Symbol Hit Rate / Hit RTP`、`Reel Set RTP`（兩種格式）、`100手資產`、`Multiple Information`、
`SpecialGame Range`、`Decile Table`、`RTP 分項`、`詳細統計`（FG觸發率 / 平均倍率 / 最大倍數）、`FG 詳細統計`（彌勒佛型引擎的觸發面 / 初始基底 / FG內部 / 結算面 / 貢獻拆解 / 各組別 / SC 顆數 / 乘倍十分位 / SS 分項）。

## Strip 分頁

表頭列（前 6 列內）出現 `Ree1s_g` / `Reels_g` / `假轉` 即為一個區塊：其後 `R1..Rn` 欄往下讀到空格為帶面；區塊右側第一個 `總顆數` 欄為顆數表（讀到 `Total`）。空區塊（Reels_2～4 只有標題）略過。

## 已知陷阱

- **`=` 開頭的報表行**：`===== Done in …` 若用 openpyxl 寫入會變公式、`data_only=True` 讀回 None。Excel 手貼沒問題；程式產表要設 `cell.data_type = "s"`。
- **樣板殘留分頁**：彌勒佛 v3 的「規格簡述」「隱性規則」是 5×5 寶箱範本殘留（隱藏）。ps_extract 原樣帶出、Content 軌標「請確認」，不替人刪。
- **合併儲存格**：openpyxl 只在左上格有值；表頭若跨欄合併會少欄名 → View 以 generic 表呈現。
- **百分比**：參數表的 RTP 常是小數（0.96）；數據資料是 `96.0000%` 字串。`known` 內 < 5 的 RTP 視為小數顯示 ×100。
- **公式格**：`data_only=True` 讀的是 Excel 上次計算的快取值；xlsx 若由程式寫入公式未經 Excel 開啟，會讀到 None。
