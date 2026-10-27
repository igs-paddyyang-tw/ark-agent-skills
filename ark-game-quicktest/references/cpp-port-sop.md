# C++ 快測 → Go 移植 SOP（ark-game-quicktest 路線 C，試點版）

範例（照抄結構）：`data/slot/cash-mania/`（金錢風暴，已完成：逐局 100 萬手 0 不一致）。

## 目錄（每款）

```
data/slot/<slug>/
├── ref/live/server-prob.json        線上機率（從 data/slot/<slug>/ref/live/ 複製）
└── quicktest/
    ├── quicktest.yaml               目標（target_rtp 從機率表 Overview；basis 寫來源）
    ├── README.md                    結果、參數來源表、發現 G-xx、重跑指令（照 cash-mania 格式）
    ├── engine/                      Go 移植（module 名 = slug 去掉 -；portkit/ 從 kit 複製，不改）
    ├── config/cpp-original.json     C++ 原表（用 port/cpp_dump.cpp 由 C++ 前處理後的實際陣列輸出，不手抄）
    ├── config/live.json (+ .provenance.json)  gen_config.py 依 config-map 產生（正式快測用）
    ├── _tuning/config-map.yaml      每個 config 鍵的來源（live／xlsx／engine／filled:*）
    ├── port/parity.json             cpp_parity.py 輸出（必須 mismatch 0）
    ├── port/rules.md                玩法規則逐條來源（C++ 函式名）
    ├── port/cpp_dump.cpp            輸出 cpp-original.json 的 C++ 程式
    └── qt-report/                   report_live.txt、rtp-report.json、qt_report md
```

## 步驟

1. **讀 C++**：原始碼在 `<slot_math_squad>/SLOT/<GameID>_<名>/<專案>/`（Big5 註解，用 `iconv -f big5 -t utf-8 -c` 看）。
   - 先看 `GameData.h`：`#define DEF_VERSION`、`#if` 分支（一般館／富豪館／道具卡／No Bonus）。正式移植一律用**一般館、有 Bonus** 的分支。
   - 再看 Chance／Check 的流程與每一個 RANDOM() 呼叫的順序。
   - 最後看 ChanceTest.cpp：押注（line bet、線數）、每手怎麼加總贏分、跨手狀態（收集條、彩金池）。
   - 有多個專案目錄時，挑和 ⓪ 主版機率表（`data/slot/<slug>/ref/README.md` 的 R-1）日期最接近的那個；README 記下理由。
2. **C++ 對照組**（遊戲專屬修正寫成 `quicktest/port/cpp_patch.sh`，以 `--patch` 傳給 cpp_trace／cpp_parity；kit 已自動拿掉週期報表 Print*Process 與 system()）：`python3 scripts/port/cpp/cpp_trace.py --src <專案> --n 2000 --out /tmp/x.txt` 必須 success。
   - 失敗時：在副本上修（`--keep` 看暫存目錄），把修法加進 README。**不要改 <slot_math_squad>/SLOT 原檔。**
3. **cpp_dump.cpp**：include GameData.h（及 Check.h 的靜態表），印出 JSON；每個表一個鍵；鍵名用英文 snake_case。
   - 編法照 cash-mania：`g++ -m32 -msse2 -mfpmath=sse -w -fpermissive -Iscripts/port/cpp/shim -include scripts/port/cpp/shim/trial_hook.h …`，連結 trial_hook.c 的 -m32 物件。
4. **Go 移植**：
   - `engine/main.go` 實作 `portkit.Game`（Play 回傳一手結果）。每個函式頭寫對應的 C++ 函式名。
   - 整數型別照 C++（ULONG = uint32 回繞、UWORD = uint16、UBYTE = uint8；注意 Type.h，有的遊戲 ULONG 是 long long）。
   - 浮點照 C++（整數除法先算再轉 double 等）。
   - portkit.Result.Parts 是 int64（C++ 以差額拆分可能為負）。
   - 亂數一律 `r.Intn(n)`（= getRandom／RANDOM）或 `r.MSRand()`（= rand()），**呼叫順序與次數必須和 C++ 完全一樣**，含「抽了但沒用」的。
   - 所有表格、門檻從 config 讀，不寫死。C++ 的 bug 若會影響數字：保留成 `quirk_*` 旗標（對照時開、正式關），並記 G-xx。
5. **逐局對照**：`python3 .kiro/skills/ark-game-quicktest/scripts/port/cpp_parity.py --cpp-src <專案> --engine quicktest/engine --config quicktest/config/cpp-original.json --n 1000000 --out quicktest/port/parity.json` → mismatch 必須 0。
   - 不一致時看 first_mismatch：第 4 欄（SFMT 次數）不同 = 抽值順序或次數錯；次數同、贏分不同 = 結算或整數語意錯。
6. **線上對照表（config-map）**：比對 `ref/live/server-prob.json` 與 C++ 表。
   - **符號碼**用輪帶逐格比對找出（線上碼 → C++ 碼），寫進 `symbol_map`。
   - 每個鍵：值與 C++ 一致或可清楚對應 → `src: live`（附 path／transform）。
   - 線上沒有 → `src: engine`（附 note）。
   - 語意不確定 → `src: live` 加 `semantic: inferred`，並記 G-xx。
   - 押注、線數、目標 → `src: xlsx`（ref 寫表名與欄位）。
   - AI 決定的值 → `src: filled:designed|inferred|default`，必填 reason、check。
   - 跑 `python3 .kiro/skills/ark-game-quicktest/scripts/port/gen_config.py --map … --root data/slot/<slug> --engine … --out quicktest/config/live.json`；diff 清單逐項在 README 解釋。
7. **快測**：目標 RTP 取法——Overview 的 Pay Back 若只含主遊戲（例 forest-bash），改用「快測結果」等含特色的總表；quicktest.yaml basis 寫明出處。先跑 C++ 原表、改成機率表押注的版本，和機率表 Overview 的分項 RTP 對照（證明移植＋押注正確）。
   - 再跑 `live.json`，2,000 萬局（`-workers 2 -seed 20261022 -version live -report ../qt-report/report_live.txt`）。
   - 然後跑 `python3 .kiro/skills/ark-game-quicktest/scripts/qt_report.py --report quicktest/qt-report/report_live.txt --targets quicktest/quicktest.yaml --out quicktest/qt-report --no-discover`。
8. **鐵則**：
   - 上線遊戲**不准為了過三向而改線上值**。對不上就做敏感度分析，找出哪個鍵造成差異，記 G-xx 等人裁定。
   - 線上機率不得寫進 kit、skill 或任何 repo 外的地方。

## 回報（給 orchestrator）

一段 JSON：

```json
{"slug": "…", "cpp_project": "…", "parity": {"hands": 0, "mismatch": 0}, "rtp": {"cpp_xlsx_bet": 0, "live": 0, "target": 0}, "verdict": "…", "provenance": {"live": 0, "xlsx": 0, "engine": 0, "filled": 0}, "findings": ["G-xx …"], "kit_issues": ["…"], "hours": 0}
```

`kit_issues`：kit 不夠用、需要改的地方，例如 cpp_trace 的 patch 抓不到。

## Go 世代（A 軌：引擎已是 Go，不必移植）

引擎在 `<slot_math_squad>/SLOT/<GameID>_<名>/…`（slot_math_squad 原樣，含多個 `odds/odds_<ver>.go`，只有一份未註解）。
1. 複製引擎到 `quicktest/engine/`（排除 *.exe、*.txt、*.csv、*.png）。`go.mod` 版本高於本機 → 降成本機版本、`GOTOOLCHAIN=local`；下載不到的產圖模組 → 參考 `.kiro/skills/ark-game-proto/scripts/engine_trace.py` 的 stub 做法。
2. **讀 json**：在 odds 套件加 `config_json.go`。`NewProbSetting()` 先建原值，若環境變數 `QT_CONFIG` 有值就把 json **覆蓋**到同一個 struct（`json.Unmarshal` 到 *ProbSetting，鍵 = 欄位名）。另加 `cmd/dump`：把原 `NewProbSetting()` 以 json 輸出成 `config/engine-original.json`。
3. **固定 seed**：main.go 的 `rand.Seed(time…)`／`rand.New(...)` 改讀 `QT_SEED`（沒有就維持原行為）；局數讀 `QT_N`。
4. **回歸**：不帶 QT_CONFIG 與帶 `engine-original.json` 各跑 100 萬局（同 seed），報表 Times／TotalWin 必須逐字相同 → `port/config-regression.json`。這取代 C++ 的逐局對照。
5. **關掉試玩開關**：道具卡、Buy Bonus、保底等一律以 config 鍵關閉（src 依來源），不改程式。
6. config-map、quicktest.yaml、快測、qt_report、README 同 C++ 流程。引擎報表若本來就是 Go 快測範本格式，直接給 qt_report。
7. 引擎的 odds 版本若不是線上版（⓪ R-1 主版），以線上值覆蓋；結構撐不住的鍵 → G-xx。

## 已知的跨款規律（先查，省時間）

- 線上 `game_rate.sub_game_rate`／`base_game_rate`（例 480／10000）在 forest-bash 推定為 C++ `KILL_GATE`：每手有 4.8% 機率「有贏就重轉到沒贏為止」。這會大幅影響 RTP，見 `data/slot/forest-bash/quicktest/README.md` G-FB-1；新款遇到時沿用同一解讀，並記成同一條待裁定。
- 線上 `fake_*_reels` 是假輪帶（客戶端顯示用），不要當成快測輪帶。
