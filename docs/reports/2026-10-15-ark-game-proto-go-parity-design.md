---
title: "ark-game-proto 1.0.0 — 機率雛型 skill 化：Go 快測核對、逐局對照、第二款 Tiger and Dragon"
type: design
version: "1.0"
status: delivered
date: 2026-10-15
author: paddyyang
skill: ark-game-proto 1.0.0（新）
supersedes: scripts/slot-proto/（2026-10-14 雛型工具，功能已併入本 skill）
related:
  - docs/designs/2026-10-14-slot-proto-pixijs-design.md（第一版設計：架構、三原則、驗證三層）
  - docs/designs/2026-09-18-spinresult-config-contract-alignment.md（SpinResult / Config 契約；本版補上 SeededRNG 對齊）
---

# 一句話

雛型從「只讀規格書、用 §2 數字反推」升級為「**和 Go 快測引擎同 seed 逐局一致**」，並包成 skill `ark-game-proto`：
新遊戲寫一支 adapter（表格語意 + 規格缺口）即可產雛型。彌勒佛 4,020 萬手、Tiger and Dragon 2,030 萬手，**0 局差異**（含封頂與 JACKPOT 局）。

# 1. 彌勒佛：推定 → Go 已證

讀 `data/slot/milefo/quicktest/engine/game/game_process.go` 逐條核對：

| 缺口 | 雛型推定（10-14）| Go 原始碼 | 結論 |
|---|---|---|---|
| G-1 觸發 | SC+SS ≥ 6 | `:204 (scCount+ssCount) >= EnterFreeGameGate[0]`（=6）| ✅ 一致 |
| G-2 SS *k | 乘 SC 分數總和，SS 數值另加 | `:342 scTotal*totalSSMul + ssValuePart` | ✅ 一致 |
| G-3 FG 公式 | (基底+金幣+鯉魚)×(1+金龍+2·彩龍) | `:372,382` | ✅ 一致 |
| G-4 演出表 | M-2 / M-4 / F-3-1 / F-4 不影響 RTP | 設定檔有這些參數，但引擎**完全不讀** | ✅ 確定為純演出 |
| **G-6（新）MaxWin** | — | `:152` MG+FG 合計封頂 10000 倍、FG 分項不封頂；**規格書只寫「開MAXWIN」沒有值** | ⚠️ 規格書需補一列 |

規格書 ⇄ Go 設定檔（`a-standard.json`）逐鍵：**27 一致 / 0 不一致 / 1 規格書缺（MaxWin）**；10 組輪帶 × 5 軸逐格相同。

# 2. 逐局對照怎麼做到

- `go-rand.js`：Go `math/rand` rngSource（607 格 ALFG + rngCooked 表 + seedrand 播種）與 `Int31n` 逐位元移植；5 組 seed × 18 次抽值與 Go 輸出逐字相同。
- 抽值順序照 Go：輪帶組 → 停點 → 倍數 WILD → 觸發（短路求值）→ FG；權重抽法 `Intn(total)+1 / SearchInts` 與 JS 等價。
- `go_parity.py`：把 `goparity/<model>_trace.go` 注入引擎**暫存複本**（不動原引擎）→ `go run` 產逐局 trace → `tests/go_parity.js` 用同一條 GoRand 流逐局比 輪帶組 / MG / FG / 封頂後總贏分 / 組別。

| 遊戲 | seed / 手數 | FG / Bonus | 封頂 | JACKPOT | 差異 |
|---|---|---|---|---|---|
| 彌勒佛 | 42 / 200,000 | 929 | 0 | — | 0 |
| 彌勒佛 | 777 / 40,000,000（fg-only）| 179,395 | 2 | — | 0 |
| Tiger and Dragon | 42 / 300,000 | 368 | 0 | 1 | 0 |
| Tiger and Dragon | 777 / 20,000,000（fg-only）| 24,921 | 35 | 120 | 0 |

# 3. 第二款：Tiger and Dragon（qt 模式、競品反解設計局）

新增玩法模型 **coin-lock**（金幣鎖格 → 相鄰成組 → 翻值連讀、解鎖列、JACKPOT）與 MG 的**倍數 WILD**（銅鑼變身，同一 Way 倍數相加；精算用 Σ路徑因子 = Πa + Σ M_i Π_{j≠i}(a_j+w_j)，免列舉）。

| 指標 | 規格 §2（2,000 萬手快測）| 雛型精算 | 判定 |
|---|---|---|---|
| 主遊戲 RTP | 70.29% | 70.38% | PASS（快測自身 ±0.3）|
| Bonus 觸發率 | 0.1241% | 0.1251% | PASS |
| Tiger / Dragon / T&D 每幾局 | 1,661 / 1,656 / 28,777 | 1,643 / 1,643 / 29,335 | PASS |
| Tiger / Dragon / T&D 均倍 | 343.79 / 0.54 / 1,570.27 | ≈339 / ≈1 / ≈1,559（抽樣 ±CI）| PASS |
| 平均局數 | 11.63 / 1 / 19.11 | 11.64 / 1.00 / 18.97 | PASS |
| 總 RTP | 96.49% | ≈96.3%（Bonus 抽樣估計）| PASS（容許 ±1）|

規格書 ⇄ Go `odds_1.0.0.json`：**32 一致 / 0 不一致**。找到 8 條缺口（全部 Go 已證），其中三條值得回頭改規格書：

| 缺口 | 發現 |
|---|---|
| G-TD-7 | §2 的 Ultra / Strong / Normal 列**就是** Tiger / Dragon / Tiger&Dragon（recorder index 0/1/2）；人工區寫「範本殘留、勿誤讀」**是錯的**——雛型三種 Bonus 的觸發率、均倍、平均局數逐列對上 |
| G-TD-2 | 倍數 WILD：Go 為均勻 x2～x10；參數備註（規格書附錄 E）假設權重 46/24/11/7/4/3/2/1/1 → **兩者不一致，需決議** |
| G-TD-3 | 隨機觸發用的 `extra_rate` 在 §4 被標成「額外押注倍率（Extra Bet）」，欄名誤導 |
| G-TD-1 | 基礎押注 75 只在 §1 人工區文字（Go 硬編 ConstBetCost，不在 odds.json）|
| G-TD-4/5/6 | 金幣鎖格流程、結算（最左不可箭頭、箭頭加到最左位、兩位數佔兩位）、T&D 起始 3 列 → 只在 Go 與規格書文字 |
| G-TD-8 | MaxWin 對（MG + 該次 Bonus）合計封頂、扣在 Bonus；與彌勒佛的封頂語意不同 |

# 4. ark-game-proto skill

```text
ark-game-proto/
├── SKILL.md                         決策樹 / 資產地圖 / 守門 / 邊界（prompt_lint 100、audit P0/P1 = 0）
├── scripts/proto_build.py           md → game-config.json → index.html；--go-config / --go-parity / --strict / --inline-pixi
├── scripts/proto_common.py          通用段（ps_mdview）+ §2 目標
├── scripts/adapters/{milefo,tiger_dragon}.py   玩法語意 + GAPS（含 Go 證據）+ go_rules
├── scripts/src/{slot-core,go-rand,app,art}.js + template.html
├── scripts/go_parity.py + goparity/{collect-mult,coin-lock}_trace.go + tests/go_parity.js
├── scripts/tests/{test_proto_build.py, core_test.js}    pytest 8 passed（3.11 / 3.13）；core_test 兩款各 10+ 條 PASS
├── references/{architecture,adapter-guide,go-parity}.md
├── assets/slot-proto-arch.svg
└── golden/{milefo,tiger-and-dragon}/   md · Go 設定檔 · parity 記錄 · 期望 config
```

依賴 ark-game-prob 1.4+（ps_mdview；實測 1.4.0 即可——原標「1.4.1」為超前標註，該版不存在；自動找同層 skill / `.kiro/skills` / `ARK_GAME_PROB_SCRIPTS`）。
安裝走 ark-skills-align：整個目錄放到 `.kiro/skills/ark-game-proto`（kiro-cli 根與 aidev 兩邊）；`skills-matrix.yaml` 加一列（C3 演出驗證）。

# 5. 下一步（決策）

1️⃣ 規格書回寫：彌勒佛補 MaxWin 列與 G-1～G-3 規則句；Tiger and Dragon 更正 G-TD-7 註記、決議 G-TD-2 倍數分佈、改 G-TD-3 欄名
2️⃣ 安裝 ark-game-proto + ark-game-prob 1.4+ 到兩邊 `.kiro/skills`，並重產 milefo prob-spec.md（1.4 格式）
3️⃣ 第三款或 Go slotcore：把 go-rand + SpinResult 契約接到 slot-bot server 端，做同 seed 上線前對帳
