---
type: test-checklist
contract: "1"
game: GHY 金猴爺
machine: 阿茲特克2 Slot
app_version: v4.6.8
pack: games/ghy/machines/aztec2 @0.1
protocol: aiqa-protocol/1
resolution: 1600x900
generated_by: ark-aiqa-testgen（規格書 + 模板展開 + import 既有測試表為 baseline）
items: 6（節選；完整版 124 項）
---

# test-checklist — 阿茲特克2 Slot（節選 6 項示範六種型態）

> 每項 = 前置 + 動作 + 原子斷言（各帶 oracle 與 spec_ref）+ 執行提詞。判定由腳本依斷言計算，AI 只回報觀察。
> Tier：T1 可觀察全自動 / T2 需 harness / T3 環境 / T5 掛測 / N/A 不執行。

## 對照：公司測試表欄位 → 本檔

| 公司欄位 | 本檔 |
|---|---|
| 編號 / 類別 / 項目 / 測試目的 | `id` / `category` / `folder` / `title` |
| 步驟 | `actions`（同時渲染成測試員可讀步驟） |
| 重複次數 | `repeat` |
| 預期結果（一格多項） | `assertions[]`（每條一個 oracle） |
| 執行人員 / Android / 測試日期 | run 時由 report 回填（aiqa / PASS… / 日期） |

---

### GHY-AZ2-MG-001 遊戲計分：Symbol 賠率對應 info 頁 〔T1〕
| 類別 | 項目 | Tier | 重複 | 來源 | 規格依據 |
|---|---|---|---|---|---|
| 1.遊戲流程 | 1-1 Main Game | T1 | 3 | spec + baseline#1 | 規格書!賠率表 · 規格書!線數(ALL WAYS, 成本100線) |

**前置**：screen=lobby · bet=min · credit ≥ 5000
**步驟**：1. 進入阿茲特克2 → 2. 開 info 頁，擷取賠率表（放大 3 倍）→ 3. 關閉 → 4. spin 20 次，每次讀 bet / win、截盤面、記錄亮框符號
**斷言**
- A1 `ocr_number` win == Σ(paytable[symbol][連線數]) × bet / 100 — spec: 規格書!賠率表 — evidence: info_paytable, board, win
- A2 `visual` (when win>0) 中獎連線 symbol 有亮框且動態播放 — spec: 規格書!表演 — min_confidence 0.8
- A3 `visual` (when win==0) 盤面 symbol 無破圖 / 錯位 — origin: template:visual_integrity

<details><summary>執行提詞（項目段，協定段另附）</summary>

```
測試項 GHY-AZ2-MG-001「遊戲計分」，第 {k}/3 次。目前畫面：{screen}。
可用目標：btn:spin, btn:info, btn:close, roi:bet, roi:win, roi:info_paytable, roi:board
動作：
 1. tap btn:info → 等 screen:info_page → 讀 roi:info_paytable（zoom 3）→ 回報 paytable: [{symbol: S01..S12, count, pay}]
 2. tap btn:close → 等 screen:main_game
 3. 重複 20 次：讀 roi:bet → tap btn:spin → 等 state:reels_settled（≤12s）→ 讀 roi:win → 回報 {bet, win, highlighted: [{symbol,count}], animation_ok, glitch, confidence}
不要：判定對錯、改押注、開其他頁面。讀不清先 crop_zoom。
```
</details>

---

### GHY-AZ2-MG-011 乘倍：連線疊加 +1、不連線重置 x1、超過 5 次變彩虹 〔T1〕
| 類別 | 項目 | Tier | 重複 | 來源 | 規格依據 |
|---|---|---|---|---|---|
| 1.遊戲流程 | 1-1 Main Game | T1 | 2 | spec + baseline#11/#12 | 規格書!乘倍 |

**前置**：screen=main_game
**步驟**：1. 連續 spin 30 次 → 2. 每次停輪後讀乘倍欄與是否有消除 → 3. 記錄乘倍序列
**斷言**
- A1 `ocr_number` 初始 mult == 1 — spec: 規格書!乘倍!起始
- A2 `sequence` 每次有消除後 mult[n+1] == mult[n] + 1 — spec: 規格書!乘倍!疊加
- A3 `sequence` 無消除的下一手 mult == 1 — spec: 規格書!乘倍!重置
- A4 `visual` (when 連續消除 > 5) 乘倍顯示為彩虹樣式 — spec: 規格書!乘倍!彩虹 — min_confidence 0.8

<details><summary>執行提詞（項目段）</summary>

```
測試項 GHY-AZ2-MG-011「乘倍」。可用目標：btn:spin, roi:multiplier, roi:board
重複 30 次：tap btn:spin → 等 state:reels_settled → 若出現消除動畫，等 state:cascade_done（≤10s）→
  讀 roi:multiplier（zoom 3）→ 回報 {spin_no, multiplier_value, cascade_count, multiplier_style: number|rainbow|uncertain, confidence}
連續 spin 之間不做其他操作。
```
</details>

---

### GHY-AZ2-MG-007 Scatter 聽牌表演-正常轉輪 〔T2 · harness:trigger〕
| 類別 | 項目 | Tier | 重複 | 來源 | 規格依據 |
|---|---|---|---|---|---|
| 1.遊戲流程 | 1-1 Main Game | T2 | 2 | spec + baseline#7 | 規格書!Scatter!聽牌 |

**前置**：screen=main_game · harness `trigger 1`（3 顆 SC 進 FG）— **pack harness.yaml 沒有宣告 → 本項 BLOCK，報告列「需測試員提供 trigger 下法」**
**步驟**：1. 下 trigger 1 → 2. spin → 3. 觀察第 3 顆 SC 落定前的整輪聽牌表演
**斷言**
- A1 `sequence` 出現 ≥3 顆 Scatter 時進入 state:near_miss（整輪聽牌）再進 FG — spec: 規格書!Scatter!聽牌
- A2 `visual` Scatter 無銀框 / 金框 — spec: 規格書!Scatter!外框 — min_confidence 0.8

<details><summary>執行提詞（項目段；harness 就緒後才發出）</summary>

```
測試項 GHY-AZ2-MG-007。前置已由腳本執行 harness:trigger1。可用目標：btn:spin, roi:board, roi:reels
tap btn:spin → 每 0.5s 由腳本連拍直到 state:free_game_intro 或 15s；你會收到一串截圖。
回報：{scatter_count_at_stop, near_miss_animation_seen: true|false|uncertain, scatter_frame: none|silver|gold|uncertain, confidence}
```
</details>

---

### GHY-AZ2-RC-003 Recover：Free Game 第 1 手重啟 〔T2 · harness:trigger + T1 restart〕
| 類別 | 項目 | Tier | 重複 | 來源 | 規格依據 |
|---|---|---|---|---|---|
| 3.特殊操作 | 3-1 Recover | T2 | 1 | template:recover(fg_hand_1) + baseline | 規格書!Recover |

**前置**：harness trigger 1 → 進入 FG → 第 1 手停輪
**步驟**：1. 進入 FG 第 1 手 → 2. `restart_app()` → 3. 重新進入阿茲特克2 → 4. 檢查回到 FG、剩餘次數、流程可續
**斷言**
- A1 `state` 回到 state:free_game — spec: 規格書!Recover
- A2 `ocr_number` FG 剩餘次數 == 離開前讀值 — spec: 規格書!Recover!剩餘次數
- A3 `no_crash` logcat 無 FATAL / ANR，app 在前景 — origin: template:recover
- A4 `visual` 無破圖、掉圖 — origin: template:visual_integrity

（同模板另展開 7 項：進 FG 前 / 進 FG 後 / 第 5 手 / 倒數第 2 手 / 最後一手 / retrigger / 結算後回 MG，只有前置狀態點不同。）

---

### GHY-AZ2-NET-002 網路：MG Spin 中斷線 → 15 秒 6002 〔T3-auto〕
| 類別 | 項目 | Tier | 重複 | 來源 | 規格依據 |
|---|---|---|---|---|---|
| 3.特殊操作 | 3-3 網路環境 | T3 | 2 | template:network(mg_spin, disconnect) + baseline | 規格書!網路!6002 |

**前置**：screen=main_game
**步驟**：1. tap spin → 2. 0.5 秒後 `net(disconnect)` → 3. 連拍 20 秒 → 4. `net(restore)` → 5. 觀察彈窗與重連後畫面
**斷言**
- A1 `visual` 盤面中間出現網路不穩符號 — spec: 規格書!網路 — min_confidence 0.8
- A2 `timing` 斷線起算 ≥ 15 s 後出現 `text` "6002" — spec: 規格書!網路!6002
- A3 `state` 按重連後回到 state:lobby，且為橫版（非直版）— spec: 規格書!網路!重連

（延遲 1000/3000ms、掉包 15%/50% 的 20 項同模板，Tier T3-manual：需主機側 clumsy，pack 未宣告 → BLOCK 並列前置。）

---

### GHY-AZ2-LR-001 掛測：網路正常 8 小時自動旋轉 〔T5〕
| 類別 | 項目 | Tier | 重複 | 來源 | 規格依據 |
|---|---|---|---|---|---|
| 3.特殊操作 | 3-5 掛測 | T5 | 1 | template:long_run(8h_stable) + baseline | — |

**前置**：screen=main_game · autoplay on · credit 足夠 8 小時（pack `credit_min_8h`，不足 → BLOCK 請 GM 補幣）
**步驟**：1. 開自動旋轉 → 2. 每 60 秒截圖一張 + logcat 增量 → 3. 每 30 分鐘做一次 state 判定 → 4. 8 小時後停止
**斷言**
- A1 `no_crash` 全程無 FATAL / ANR、app 在前景 — origin: template:long_run
- A2 `state` 每次抽查皆在 state:main_game / free_game / cascade 之一（非卡死同幀 > 120 s）— origin: template:long_run
- A3 `ocr_number` credit 單調變化、無異常跳值（前後差 ≤ 最大單手贏分）— origin: template:long_run

---

## N/A 清單（不執行，報告列出）
- 3-4 裝置適配性：samsung A20、華為 mate 30、iphone 11、Tab S7、iPad air 3（真機 / iOS）
- 3-3 網路環境：CN 線路 ×3、ipv6（需 VPN / 研三環境）
- 7-1 音樂音效 ×14（v1 無音訊 oracle）
- 6-1 版本差異 iOS 項
