# 還原局每款流程：⓪ → ④ → ③⑤ → ⑥-lite → ⑦（ark-game-quicktest；W1／W2 實戰累積）

先讀 `cpp-port-sop.md`（同目錄）；本檔規定 W1 每款要交的東西。範例：`data/slot/cakebonanza/`（④ 已完成，照它的 quicktest 結構）、`data/slot/cash-mania/`（C++ 移植）。

## 輸入

| 項目 | 位置 |
|---|---|
| ⓪ ref（線上機率、主版機率表 csv、R-1 判讀）| `data/slot/<slug>/ref/`；遊戲卡 `data/slot/<slug>/README.md` |
| Go 快測引擎 | `<slot_math_squad>/SLOT/<資料夾>/…`（= slot_math_squad/SLOT）|
| C++ 快測（87、101 這類）| `<slot_math_squad>/SLOT/<資料夾>/…` |
| 原始機率表 xlsx（③⑤ 用）| `<slot_math_squad>/SLOT/<資料夾>/`（檔名見 ref/README 版本地圖；主版 = R-1）|
| skills | `.kiro/skills/`（ark-game-prob 1.6.0、ark-game-proto、ark-game-quicktest）|

## 輸出（全部在 `data/slot/<slug>/`，結構同 repo 的 data/slot/<slug>/）

| 階段 | 交付 | 過關條件 |
|---|---|---|
| ⓪ | 不重做；只在 README 記 R-1 是否被 ④ 印證（線上值與主版逐鍵相同 → 建議升級信心）| — |
| ④ 快測 | `quicktest/`（同 PORTING.md）| 引擎讀 json（`QT_CONFIG`）、固定 seed（`QT_SEED`，Go 1.24 要 `//go:debug randseednop=0`）、設定回歸或逐局對照 0 差異；`config/live.json` 每鍵有來源；2,000 萬局；qt_report |
| ③⑤ 機率規格書 | `prob/`：`python3 .kiro/skills/ark-game-prob/scripts/ps_run.py --xlsx <主版 xlsx> --slug <slug> --game <中文名> --dest data/slot/<slug>/prob --qt-report data/slot/<slug>/quicktest/qt-report/report_live.txt` | ps_lint PASS；§2 有快測數字。xlsx 解析失敗 → 試 `--params-sheet`；仍失敗就記缺口（不手寫規格書）|
| ⑥-lite 引擎回放對帳 | `game/replay/engine-trace.meta.json` 的 200,000 局 RTP 落在 ④ 結果 ± 3 SD/√n 內；寫進 README | 一致 |
| ⑦ 試玩版 | `game/replay/{trace.json, engine-trace.meta.json, stage.yaml, README.md}`＋單檔 `output/slot/<slug>/game/replay/single/index.html` | smoke PASS |

### ⑦ 指令

```bash
P=.kiro/skills/ark-game-proto/scripts
python3 $P/engine_trace.py --engine data/slot/<slug>/quicktest/engine --config data/slot/<slug>/quicktest/config/live.json \
  --n 2000 --sim 200000 --seed 7 --out data/slot/<slug>/game/replay --name "<中文名>" --engine-label "data/slot/<slug>/quicktest/engine（config live.json）"
rm -f data/slot/<slug>/game/replay/engine-trace.jsonl
python3 $P/stage/stage_build.py --game $P/stage/replay/game.js --odds data/slot/<slug>/game/replay/trace.json --out output/slot/<slug>/game/replay/single --single
cd $P/stage/tests && timeout 550 node smoke.js --html output/slot/<slug>/game/replay/single --scenes '[]' --spins 3 --out <暫存>/smoke-<slug>
```

- engine_trace 依賴 GameCheck／GameProcess 鉤子；引擎沒有 GameCheck（例 523）就在 quicktest/engine 加一個等價的記盤面點，或在 README 記缺口。
- `game/replay/stage.yaml` 照下面寫（路徑相對於 repo 的 data/slot/<slug>/game/replay/）：

```yaml
# 引擎回放試玩（⑦-lite）——數學 = quicktest/engine＋config/live.json（線上機率）
game: ../../../../../.kiro/skills/ark-game-proto/scripts/stage/replay/game.js
odds: trace.json
assets_base: []
```

- `game/replay/README.md`：寫明「數學 = 線上機率 × 快測引擎（不是規格書 ⑥ 第二實作者）、特色只顯示摘要、只限內部」。若之前已有用 slot_math_squad 原 odds 產的版本，註明本版改用線上機率。

## 遊戲卡 README（`data/slot/<slug>/README.md`）

從 `data/slot/<slug>/README.md` 複製，更新：

- `updated:`。
- 「十階段進度」改成表格（⓪ ④ ③⑤ ⑥ ⑦ 各一列：狀態 ✅／⚠️／❌、主檔、關鍵數字、待裁定 ID）。
- 「來源標記」一行：🟩 live n／🟦 xlsx n／🟦 engine n／🟪 ruled n／🟨 AI 補齊 n。

## 鐵則

- 不改原始來源（slot_math_squad、GoldenHoyeahServer）、⓪ ref、kit 與 skill（發現 bug → kit_issues 回報，在自己的遊戲資料夾內繞過）。
- 上線款不改線上值；RTP 對不上 → 敏感度分析找出是哪個鍵，記 G-xx。
- `sub_game_rate`（砍分）：已列為全域待裁定 R-G1。正式 live 跑**不套**砍分；README 另給「套用後推估 = RTP × (1 − sub/base)」與機率表目標的比較（機率表目標若含砍分要說明）。
- 道具卡、Buy Bonus、AB 變體：標準快測一律關閉，變體只在 README 列出、不跑。**保底／天井例外**：線上有 `mg_payout_ceiling_*` 之類鍵、或規格簡述把它列為基本規則時，它就是線上規則，正式 live 要開（src live），另跑一份關閉版做比較（beach-idol G-BI-3）。
- 機器只有 2 核、和其他 3 個子代理共用：Go 快測單執行緒或 `-workers 1`，不要同時開多個長跑。
- 線上機率只放在遊戲資料夾內，不寫進回報文字以外的地方；回報不要貼參數值。

## 回報（只回這個 JSON＋最多 5 行註記）

```json
{"slug": "", "route": "A|C|D", "stages": {"quicktest": "ok|warn|fail", "prob": "ok|warn|fail", "replay_check": "ok|warn|fail", "trial": "ok|warn|fail"},
 "rtp": {"live": 0, "target": 0, "target_src": "", "with_kill": 0, "sim200k_trial": 0}, "verdict": "", "provenance": {"live": 0, "xlsx": 0, "engine": 0, "ruled": 0, "filled": 0},
 "findings": ["G-xx …"], "kb_notes": ["跨款可重用的發現（鍵語意、引擎結構、坑）"], "kit_issues": [], "hours": 0}
```

## 第 1 輪累積的規律（必讀）

- **砍分 sub_game_rate 依遊戲而異**：
  - 線上有 `sub_game_reel_index(_set)` → 是「換輪帶」砍分。引擎通常有 ReduceRTP／ReduceRTPWeight／ReduceRTPReelData，要用 config 實際模擬（另跑 `config/with-kill.json`），不要用 ×0.952 估算。mexico-hot 用估算會高估 0.47pt。
  - 沒有輪帶組 → 才用 ×(1 − sub/base) 估算，並註明是估算。
  - 正式 live 一律關砍分（例 ReduceRTPWeight [10000, 0]），以 R-G1 標示。
- **線上 main_reels 可能多一組砍分輪帶**，輪帶組索引會位移；index set 要直接照線上對應，不要照引擎。
- **找出線上對應哪個 odds 檔**：在副本把每個註解掉的 odds_*.go 去掉一層 //，dump 後和線上逐鍵比。「唯一沒註解的 odds 檔」常是實驗表、道具卡表或 AB 變體，先 dump 看 IsItemCard 與權重再跑。
- **⓪ R-1 可能指錯檔**：例如指到檢核表，裡面沒有參數表分頁。主版要能讓 ps_run 解析；用線上的特徵權重 grep xlsx 的 xml 找真正的主版。README 寫建議修正。
- **引擎常見坑**：
  - seed 不可重現：rand.New 的回傳值沒用到。
  - 局數寫死在程式裡。
  - recorder 直接 fmt.Printf → 在 main 暫時把 os.Stdout 換掉，就能接到最後報表，不必改 recorder。
  - 除錯用的 sleep，要改成只計次。
  - slice aliasing 會改到 config。
  - 跨局狀態：只能單執行緒。
- **CI 比容許寬**（SD 大的遊戲，20M 局 CI 半寬 > 0.5）：多跑一個 seed（不挑 seed），README 列兩次結果與合計。正式報表照舊。
- **線上值可能不等於任何一版 xlsx**（book-of-horus G-BH-1）：做敏感度分析，列出每個差異鍵對 RTP 的影響。
- **機率表沒有 Overview RTP**：依序取 參照表／快測結果頁／M-1 加權；都沒有就照參數表算期望值（例 kuromu port/analytic_rtp.py），並在 basis 寫明。

## 第 2 輪累積的規律

- **JP 不在單手贏分裡**：有些引擎的彩金只走 recorder（例 SpecialGameAddTotalWin），GameProcess 的回傳值不含 JP，engine_trace 回放就會少掉 JP RTP。⑥-lite 前先檢查。解法：引擎加一個預設關閉的環境變數開關（例 QT_TRACE_JP_IN_WIN），開了才把 JP 併進回傳值，正式報表仍逐字相同（chiotian）。
- **KillState／KillGate 型砍分**（只在盤面沒有 Wild 時換成 0 分盤）砍得很少，要用 config 實際模擬；公式估算會差好幾個 pt。
- **odds_*_test.go 是唯一沒註解的 odds 檔時，go build 會跳過它，引擎編不過**：副本改名（yuuka），不要退回舊版引擎。
- **⓪ 吻合度高可能只是假輪帶（fake strips）一樣**：判主版只比玩法鍵。
- **線上 99＋符號碼 = 大符號的佔位格**：轉換時填入下一格。
- **目標 RTP 可能只在數據資料頁的截圖裡**：在 xl/drawings → media，依 anchor row 排序找。
- **smoke 在高負載下可能逾時**：重跑一次；仍失敗才算 fail。

## 第 3 輪累積的規律

- engine_trace 已修：
  - GameProcess 多回傳值時，自動取名稱含 earn／win／credit 的那個。
  - 新增 `--keep <欄位,…>`：指定的欄位不讓 __trialTune 關掉。天井是線上基本規則時用 `--keep GuarenteeSpinEnable`（依引擎實際欄位名）。
- 3×3 小盤遊戲可以窮舉算出精確 RTP，機率表沒有目標時用它（fortune-gems）。
- 同一張機率表裡有兩個同名參數區塊（例兩個「表M-2」）時，ps_run 會漏掉一個 → 記成缺口。
- 線上表找不到逐鍵相同的 xlsx 時，先拿引擎留下的舊 odds 檔來比（wizard-s-lock：線上 = 引擎 odds_6.11.0）。
- 小押／大押（BetType）各有一套權重：正式 live 跑小押，大押列在 README。

## 第 4～5 輪累積的規律（skill 已修）

- ark-game-prob 1.6.0 已修：
  - `.xls` 會自動用 LibreOffice 轉檔。
  - 可見分頁優先於隱藏分頁。
  - 沒有「表」字的標籤（「M-1」）也能抓到；分頁名不是參數表時，仍要用 `--params-sheet <分頁>`。
- engine_trace 的讀表函式 regex 改成 `NewProbSetting\w*|LoadProbSetting\w*`。
- smoke 指令的 timeout 改成 550（Bash 工具 timeout 要設 600000）；4 個代理共用 2 核時一次約 110～300 秒。逾時後用 `pgrep -f "chrom.*smoke-<slug>"` 只清自己的 chromium。
- **R-1 常指錯檔**：線上預設通常 = 引擎某個 odds 檔 = 檔名同版本的 xlsx（AB 組別看檔名 (A)／(B)）。先拿引擎留下的 odds 檔和線上逐鍵比，最快。
- **引擎寫死的保底（不在 ProbSetting 裡）**：加一個預設關閉的環境變數開關，另跑一份關閉版做比較；正式跑保持開啟（線上規則）。
- **線上 index set 可能少掉引擎專用的組**（例道具卡組），索引會位移；expr 裡保留引擎的佔位組。

## W2（C++ 已上線款，路線 C）補充

- 每款都照 PORTING.md 的 C++ 步驟做 ④（逐局 100 萬手 0 不一致 → 線上 config → 2,000 萬局），③⑤／⑥-lite／⑦／遊戲卡照本檔。
- **⑦ 用 portkit 內建的 replay 子命令**（kit 的 go/portkit 已新增 replay.go）：
  - Play 回傳的 `Result.Grid` 填主遊戲第一轉盤面 [軸][列]，並轉成回放顯示碼：1 WILD、2 SCATTER、3 BONUS、11～19 M1～M9、21～30 A K Q J 10 9 8 7 6 5；其他碼照原碼。
  - 執行 `cd quicktest/engine && go run . replay -config ../config/live.json -n 2000 -sim 200000 -seed 7 -out ../../game/replay -name <中文名>`，產出 trace.json 與 engine-trace.meta.json。
  - 之後照常 stage_build 加 smoke。不要用 engine_trace.py。
- 先查 C++ 結構（reel_amount／check_reel_length）是否和線上一致：不一致代表 C++ 是早期原型，改以 Go 世代引擎或線上結構為準（bridge-of-love）。
- cpp_trace 主遊戲贏分欄已支援 sl*／*MainGameWin；遊戲專屬修正一律放 `quicktest/port/cpp_patch.sh`（用 `--patch` 傳入）。
- 一款若有多個 C++ 專案目錄：用線上輪帶逐格比對，挑最接近的那個。
- 已有 ④ 的款（cash-mania、forest-bash）：不重做 ④，補 ③⑤／⑥-lite／⑦／遊戲卡。portkit 換成新版（有 replay），並重驗 parity。

## W2 第 1 輪累積的規律

- replay 顯示碼：倍數 Wild（DW/TW/QW/PW 等）一律轉成 1 WILD；第 10 個以上的 M 符號沒有顯示碼，用 20 以上不和 A..5 撞的碼（例 20），顯示為 S20。
- 有砍分重轉時，Grid 取最後一轉（決定本手贏分的那一轉）。
- GHY 系 C++ 的 RANDOM 是 MSVC rand() 拒絕取樣（沒有 SFMT），portkit 的 MSRand 可以直接用。
- CGTChance 的 private 靜態表：在 cpp_dump 裡 include GameData.h 之前加 `#define private public`，就能印出來。
- 有些 C++ x1 專案把 Free 呼叫註解掉了（只有 Main）。對照前先看 vGTChance_Process；用 cpp_patch.sh 打開，README 註明。
- 分級（Gold 1..5）／JP 遊戲：正式跑選押注量最大的那一級，其他級列在 README。JP、金元寶這類 C++ 沒有的機制不模擬，只依 xlsx 估算。
- cpp_trace 的 `--patch` 腳本失敗（rc≠0）時，現在會判失敗。
- 舊式自由排版的 .xls（Overview／Strip 分頁）ps_run 抽不到參數，§4 空白，記為缺口即可。

## W2 第 2 輪累積的規律

- **原版與重製版可能共用 server_id**：例如 59 和 139 EX。開跑 ④ 前，先拿 ref/live 和重製版的 slug 比 md5；相同就表示原版沒有自己的線上表。這時正式結論改用「C++ 原表對機率表」，線上表只當參考，並記 G-xx。
- cpp_trace 已經會自動關掉 `#define DEF_OUTPUT_GAMEDATA`（逐局寫檔）。
- 線上有超過 32767 的單次抽籤（例如 1/90000）時，MSVC rand() 做不到。config 加一個 rng 開關，線上用 sfmt；對照 C++ 時仍用 msrand（witch-forest）。
- C++ 的 slMainGameWin 若已經含特色贏分，就在 cpp_patch.sh 把 trace 的主遊戲欄改成「主遊戲 − 特色」，讓它和報表定義一致。
- 線上的兩段式抽籤（數量 × 位置）可以精確還原成 C++ 的單次聯合表：權重 = 數量權重 × 位置權重 ÷ 位置權重合計。
- base_game_rate 約等於機率表的目標 RTP（GHY 系實測 9801 ≈ 98.07%）。

## W2 第 3 輪累積的規律

- `special_odds.fever` 的索引不是每款都一樣：有的是 [顆數−1]，有的是軸數。先拿觸發率和 xlsx／C++ 對過再採用（monkey-king）。
- 線上 extra_odds 的權重陣列可能和 C++ 順序相反（例 [3,2,1,350]）：反著讀跑一次敏感度，看哪個對得上目標。
- **線上有 C++ 和 xlsx 都沒有的鍵**（例 fail_feature_gate、total_win_feature_gate、wild_feature_gate_map）時：不模擬，記 G-xx，並說明對 RTP 可能的方向。
- `#if` 分支的註解可能標錯：用輪帶 diff 和 RTP 確認哪個分支才是 98% 線上版。parity 原樣與線上分支各做一次。
- kit 已修：cpp_trace 會自動去掉 Big5 註解行尾的 0x5C；ps_extract 的 soffice 改用獨立 profile。
- scratchpad 是多個子代理共用的：暫存檔一律放 `<scratchpad>/<slug>/` 子目錄。

## W2 第 4 輪累積的規律

- **C++ 輪帶初值可能比宣告長度短**：沒列到的格會補 0（常常就是 WILD），原程式甚至會卡死。對照前先數元素個數，不夠就在 cpp_patch.sh 用 xlsx／線上補齊（jungle-queen）。
- **GameData.h 常用 DEF_GAMERATE（98／120）或 DEF_RTP_INFO 選分支**，原專案可能停在 120 或道具卡分支：先用 sed 改成 98，再用線上輪帶逐格確認是哪個分支。
- **多個 C++ 目錄時**，`上線版本/` 子目錄通常是正式版，根目錄可能是早期原型。看輪帶長度就能分辨。
- **雙向計獎**（右到左用 Odds2）只寫在 C++ 裡，線上沒有對應的鍵：保留為 engine 鍵。只算左到右 RTP 會差很多。
- **線上 fake_life 這類鍵**：做敏感度分析，若結果遠高於 base_game_rate，就判定為只影響表演。
- **C++ 在掛鉤點之後才抽的亂數**（例 DEF_PROTECT 的 RANDOM），trace 會把它算到下一手。Go 端把這次抽值延到下一手 Play 一開始，parity 才會一致。
- **xls 輪帶欄的最後 2 格是重複開頭的環狀顯示**，diff 前先去掉。

## W2 第 5 輪累積的規律（GHY 6×4 家族：83／84／89／90）

- **GHY 系 .xls 的 Overview 頁常常沒有儲存格**，目標 RTP 在截圖裡：soffice 轉 xlsx → `xl/media/image1.png`（C++ 1 億局快測）。§4 會是空的（沒有參數表分頁），記缺口即可，不要手寫。
- **GameData.h 常停在 DEF_VERSION 1（120%）**：0 = 98% 線上、1 = 120%、2 = 道具卡（sg_card）。cpp_patch.sh 改成 0，原分支另做一次 parity 留存。
- **權重表分頁可以 1:1 對到線上 extra_odds**（gate、weight），是確認 R-1 最快的方法。
- **跨手狀態**（黏輪、Wild 疊塊下移，flag 只在 ulPlayTimes==1 清）會讓 Pay Combo 解析值偏低約 9pt：目標改用快測截圖（three-musketeers）。
- **編譯期分段**（DEF_GAMERATE Gold 1..5）：每段各編一次 dump 再合併；正式結論用線上預設段，其餘段列在 quicktest/README（golden-piggy 的 cpp_dump.sh 是範本）。
- **玩家自選 FG 類型**：C++ 均等抽，線上沒有權重鍵 → 照 C++，記 G-xx 待裁定。
- 線上鍵沒有對應機制（remove_scatter_gate、fail_feature_gate 等）：照第 3 輪規則，不模擬、寫方向。
- 已知 kit 缺口：replay 舞台的列數固定取第一局，盤面列數會變的遊戲只會顯示前幾列 → 在 game/replay/README 記一行即可。

## W2 第 6 輪累積的規律（91／93／95／97）

- **線上可能是 GoldenHoyeah 重調版**，對不上任何 xlsx 或 C++（songkran-festival）：目標用 Overview Pay Back＝base_game_rate；逐組把鍵換回 C++ 值做敏感度，確認重調後仍平衡，記 G-xx。
- **玩家自選 FG**（龍騎士 5 選 1）：C++ 寫死某一選項 → 正式照 C++，五個選項各跑一次列在 quicktest/README。
- **C++ x 版／+S 版可能是道具卡模擬器**：把主遊戲贏分、MG JP 都註解掉了。先拿 xlsx 截圖的分項 RTP 比，再決定要不要在 cpp_patch.sh 打開（daruma）。
- **#if 分支可能整段是別款貼錯的表而編不過**：用相鄰分支＋xlsx＋線上逐格做最小修補，兩版都做 parity（atlantis）。
- **線上 main_reels 兩組只差 1 格**：可能是累積 JP 版和不累積版；用 jp_info.jp_game_rate 判斷線上預設是哪組。
- **JP 押注分段**（jp_actually_min_bet）：正式跑用最高押注段，低押注段另跑。
- Overview 多張截圖並排：依 drawing anchor 欄位對應標籤。
- 線上 SS 列 [0,0,1,0,0] = scatter 付總押注倍數：拆成獨立鍵，避免假的 engine_equal diff。
- kit 已修：gen_config odds_map 可加 `rows: N`，給線上新增的符號碼（例 濕人 20..22）留列。

## W2 第 7 輪累積的規律（98／99／103／106）

- **同一個 GameID 可能有兩個不同遊戲的資料夾**（99 白蛇傳2／Wild Fishing）：先用盤面規格與輪帶逐格比，只移植對得上線上表的那個，另一個記 G-xx（無線上表、⓪ 目錄待裁定）。
- **C++ 可能停在測試分支**（DEF_VERSION 3／9：排序過的測試輪帶、每手進 FG、SS 強制 3）；g++ 不接受 MSVC 允許的裸 `#elif`，在 cpp_patch.sh 改成 `#else`。
- **兩段 JP 押注**（DEF_LOCKJP／DEF_MINIMAL_LINE_BET）：線上 extra_odds 的 "0"／"1" 或 main_reels 組 0／1 = 押注 ≥／< jp_min_bet。正式跑高押注段，低押注段另跑一次 parity（cpp_patch.sh 換 line bet）。
- **C++ 的純量常數可能來自道具卡或 120% 分支**，即使輪帶對得上線上：每個純量都要和 xlsx 對過，不要因為 C++ 跑出 98% 就相信它（lion-safari）。
- **base_game_rate 明顯高於所有 xlsx 的 Pay Back**：照線上跑，記 G-xx 待裁定，不要去找「對得上」的版本湊數。
- **KILL_GATE 整手回傳空盤、與盤面無關**時，RTP×(1−sub/base) 是精確值，with_kill 可直接用（標「精確」而非「估算」）。
- 語意判讀用「兩種讀法 × 正式組與變體組」做敏感度：哪種讀法讓某組 RTP 變得不合理（例 109%）就排除。
- 已知 kit 缺口：ps_extract 在 Strip 分頁「真輪帶與假轉帶並排」時會抓到假轉帶，附錄輪帶以 ④ config 為準，在 prob/README 記一行。

## W2 第 8 輪累積的規律（107／110／113／114）

- **線上獨有的大機制**（super_fever_gate、symbol_post、wild_change…）沒有 C++／xlsx 可對照時：不模擬、不自行推定實作。用解析估算列出可能補回多少 RTP，qt_report 會是 rejected，這是正確結果，交由人裁定（需要線上 Server 程式）。
- 線上把 FG 輪帶的 Wild 拿掉、改由控制表「post」放 Wild 時，不模擬會少約 15pt：拿 free_reels 換回 C++ 值的敏感度來對照。
- **C++ 在 Free 放的特殊符號可能超出 ENUM_SYM_MAX**，連線檢查會越界讀賠率表（未定義行為，g++ 下 RTP 可到 300%+）：用 quirk_oob_odds 鍵保留給 parity，正式跑以 xlsx FG Avg. Combo 為準（dragon-gate）。
- JP 貢獻比例只改分配、總額相同時，長期 RTP 不變。
- 部分完成的子代理被中斷後重跑：先用 sha 確認 parity 檔與現在的 config／main.go 一致，再沿用。

## W2 第 9 輪累積的規律（115／116／117／118）

- **GHY 系特殊符號（FF、RB）越界讀 odds 表**又出現（shu-lai-bao、wild-gorilla）：越界值用 nm＋objdump 看 cpp_trace 的 trial.bin 符號位址程式化取得（shu-lai-bao 的 port/oob_layout.py）；quirk_oob_odds 正式設 0。
- **⓪ R-1 常挑到檔名日期最新的道具卡版 xlsx**：用 free_spin_odds_limit／item_scatter_weight／progressed_jackpot_limit_bet 判斷線上預設是哪個廳。
- **C++ 版本可能比 xlsx 舊**（maya-118：C++ 200413、xlsx 200428）：線上 = xlsx 時照線上；C++ 註解掉、但線上與 xlsx 都有的規則，可以依註解程式實作（標 filled:inferred 並寫 off 時的 RTP）。
- **DEF_MAIN_EMULATION**（主輪帶窮舉停點）：只給原樣 parity 用，正式跑用隨機停點。
- 15 格家族（reel_length 1）：線上每格 [符號, 權重]、C++ 每格一條 100 格輪帶，展開後分布相同；順序不同造成的 diff 可接受。
- 金字塔／拼圖類 (ULONG) 截斷：line_bet 要讓 line_bet/100 是整數。
- kit 已修：gen_config odds_map 多碼對同一引擎碼時保留第一個；cpp_parity 會把 QT_* 環境變數寫進 parity.json 的 cpp.patch_env。

## W2 第 10 輪累積的規律（119／120／121／122）

- **🟪 ruled 只能是人裁定**。「R-G1 待裁定前正式不砍分」這類流程預設要標 `filled:default`（reason＋check），不可以標 ruled（oceanheart 已更正）。
- **目標含砍分、正式跑不含**時（xlsx 寫明含 win 分砍牌）：拿 with_kill 的模擬值和目標比，報告寫「以含砍分基準比對」。集氣型 FG（鑽石收集）整手 KILL_GATE 幾乎不影響 FG，**一定要模擬**，公式會低估約 1.7pt（buffalo-treasures）。
- **CI 半寬超過容許、第二個 seed 也跑了**：判定以兩個 seed 合併（4,000 萬局）為準，兩個都要寫進 README，不可以只挑好的那個。
- **xlsx Overview 的快測數字可能來自 C++ 的格子順序**，而 Strip 分頁（＝線上）是同符號數的另一種順序：純換格子順序就可能差 0.26pt。用同 seed 成對比較區分雜訊（white-snake），差異列 G-xx 待裁定目標。
- **C++ DEF_MAX_LINE 可能大於已初始化的線表**：多出來的零列會重複第 1 線，先拿 xlsx Paylines 核對線數。
- 線上 GHY RTP_INITIAL／RTP 砍分：kill_rtp_initial = base/10、kill_rtp = (base−sub)/10；整手換成 0 分，公式接近但仍要模擬。
- 一般／120%／道具卡 xlsx 共用輪帶時，⓪ 的吻合度分不出版本：用 FG 權重與 gate 判斷。
- 已知 kit 缺口：cpp_trace 的 main_var 正規式抓到陣列名稱時不含索引（例 `stcChanceResult.ulMainGameWin`），要在 cpp_patch.sh 補 `[2]` 之類的索引。

## W2 第 11 輪累積的規律（123／125／126／127）

- **kit 新增 `cpp/oob_layout.py`**：越界讀 odds 的值一律用它取得，不要手抄。`python3 scripts/port/cpp/oob_layout.py <trial.bin> --sym 'uwconCheckGTOddsInfo$' --rows 12,13 --width <2|4>`；width 看 Type.h 的 UWORD（GT 系常是 unsigned int → 4）。stderr 會印出緊接在後的符號，確認讀到哪個陣列。
- **xlsx Overview 的 Pay Back 可能不含 JP 提撥**（Total = Pay Back + 累積值），也可能漏掉 Top JP 底分：單機池引擎要和 Total 比；先拿分頁自己的解析「Multiple」列核對目標（diamond-billionaire 差 2.2pt）。
- **沒有砍分時 RTP 超過 100%**，代表砍分是設計的一部分：正式照 R-G1 不套，但 with_kill 必須模擬，並在 README 寫明「設計含砍分」。
- **JP 提撥在 NewHandInit（砍分之前）累積**：含池的精確 with_kill = (RTP − 提撥)×gate/max + 提撥；有池就模擬，不要只用公式。
- **開／不開 Extra Bet 兩組表**：正式跑不開（比照小押規則），開 Extra 的結果列在 README，記 G-xx 待裁定。
- 同一 GameID 的 EX 重製版（123 Crazy Wheel EX）若線上沒有對應表：不移植，記 G-xx，⓪ 目錄待裁定。

## W2 第 12 輪累積的規律（129／130／131／132）

- **GT 系 RANDOM（MSVC rand 拒絕取樣）上限 > 32767 時會溢位成 −1（存成 ULONG）**，不拒絕，直接回 raw rand()：「1/2e9」的 gate 實際是 1/32768。Go 要逐位元重現；線上與 xlsx 若是 1/20 就照線上（money-mage-130）。
- **線上預設是重調版時**，拿同一份 config-map 去跑和 C++ 相同的 AB 變體（例 ab-g2）：每個鍵都 engine_equal，就證明鍵的語意讀對了（fortune-four）。
- **無符號索引 [n−1] 在 n=0 時讀 arr[−1]**：用 `oob_layout.py --rows=-1` 看陣列前一格是什麼。
- **上升盤（3～8 格）家族**：上方獎勵與軸高跨手保留，單執行緒；replay 只顯示前幾列（已知缺口）。
- **xlsx RTP 分頁的 Total 可能含 JP 提撥**：引擎沒有付池時要扣掉再比。只有含砍分截圖、而砍分是旋轉前整手 KILL_GATE 時，目標 = 截圖 ÷ (gate/max) 是精確的。
- **C++ A／B #if 表不一定對應同字母的線上／xlsx 版**：逐格比每個分支（saint-patick：線上 B = C++ A 輪帶改 4 格）。
- Extra Bet 變體 RTP 異常高時，先關掉後加的 C++ 保底再比 xlsx 截圖（截圖可能早於保底）。
- kit 已修：cpp_trace 的 patch 腳本失敗時不再編譯、保留 patch 錯誤訊息；`--keep` 接受相對路徑。

## W2 第 13 輪累積的規律（133／134／135／136）

- **GHY 重調款越來越多**（lucky-riches、goldenhoyeah、fortune-four、songkran、onmyoji-114、mafia）：先用同一份 config-map 跑「等於 C++ 的 AB 變體」證明鍵語意讀對，再對線上預設做逐組換回 C++ 的敏感度。線上獨有的 FG 機制不模擬 → rejected 是正確結果，不要自行設計機制補齊。
- **slot_math_squad 的 `*_快測比對.xlsx` 比對頁「機率」區塊**是 C++ 快測的 A/B × Extra/NO_Extra × 1/0.952/0.95 RTP；Overview 只有開 Ex 口徑時拿它當目標。
- **C++ 權重表的 Total 欄可能沒跟著權重更新**：抽值落到 index n 變成 0 分死格。parity 前每張表都核對 Total = Σ權重。
- **#define 值寫成「10,000」放進 if**：逗號運算子讓條件恆為 0。dump 時印實際值判斷。
- **JP 提撥若在取本手押注之前**，用的是上一手的押注（第 1 手是 0），只有 LOCKJP 0 才看得到 1 分的 parity 漂移。
- **Type.h `#if 1` 可能把 UBYTE／UWORD／ULONG 全 typedef 成 long**：先看 Type.h 再決定 Go 型別，不要假設 uint16 溢位。
- **同資料夾內另一款**（人魚樂章大祕寶）對不上線上表：不移植，記 G-xx。
- kit 已修：cpp_trace 的 Big5 0x5C 處理容許反斜線後面接空白／tab。

## W2 第 14 輪累積的規律（137／139／140／141）

- **一份線上檔同時有 Extra 與不開 Extra 兩組**（main_reels 0/1、fever_reels 鍵的第一碼、extra_odds "0"/"1"）：對到 C++ DEF_EXTRABET／DEF_EX_OPEN 0/1。正式不開 Extra；⓪ R-1 常落在 EX 版 xlsx，記 G-xx 建議改指。
- **`*機率比對結果.xlsx` 有 C++ 與 Server 模擬截圖並排**：以 C++ 截圖為目標，Server 數字列參考。兩者差到 ±0.1pt（1e9 局遠超抽樣誤差）時記 G-xx，不要選比較近的那個。
- **Type.h 把 ULONG 設成有號 long long** 時，GT 系 RANDOM(n>32767) 會 top=−1 無限迴圈（和 money-mage 的無號溢位不同）：Go 引擎遇到 n>32767 直接報錯。
- **cpp_dump 用 `#define private public` 時**，std 標頭（iostream、sstream）要在 define 之前先 include，否則 g++13 會壞。
- **gate 表的 0 分母填充格**：載入時不檢查，只在真的抽到時才報錯。
- **base_game_rate 可能等於 DEF_KILL_GATE_MAX**（例 9900），而不是目標 RTP。
- C++ `long *= pow(2,n)` 要用 double→int32 飽和（cvttsd2si → INT32_MIN）重現。
- 已知 kit 缺口：trace 沒有每手押注欄，Extra Bet 的總押注倍數不在 parity 檢查範圍內，要靠 RTP 對截圖確認。
