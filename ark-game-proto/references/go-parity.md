# 與 Go 快測引擎逐局對照

## 為什麼能逐局一致

1. **RNG 逐位元移植**：`src/go-rand.js` = Go `math/rand` 的 rngSource（607 格 ALFG、seedrand 播種、rngCooked 表）+ `Int31n` / `Intn` 拒絕取樣。
   `rand.New(rand.NewSource(seed)).Intn(n)` 與 `GoRand.create(seed).int(n)` 逐值相同（Go 1.20+ 的 `rand.New(NewSource)` 仍是 rngSource）。
2. **權重抽法同語意**：Go `GetIndexByWeight` = `Intn(total)+1` 再找第一個累計 ≥ 值；JS `pick` = `int(total)` 找第一個累計 > 值，等價。
3. **抽值順序同 Go**：輪帶組 → 各軸停點（Intn(len)，視窗由上而下）→ 倍數 WILD（逐軸逐列）→ 觸發（只在條件成立時才呼叫 Intn）→ FG / Bonus（照 Go 函式內順序）。
4. **同一條流跨局**：Go 每個 worker 一條 rand 流連續跑；JS 對照時 `spin(C, i, {rng})` 共用同一個 GoRand。
5. **單位一致**：Go 贏分 × Line_bet；兩款試點 Line_bet = 1。

## trace 格式

`# seed=… n=… line_bet=… bet_cost=… max_win=… fg_only=…` 後每行 `i set mg fg total group sp`：
set = 輪帶組（-1 不比）、group = FG 組別 / Bonus 類型（-1 無）、sp = 觸發顆數（0 不比）。`--fg-only` 只列 FG 局，JS 端仍逐局跑、未列出的局必須無 FG。

## 試點結果

| 遊戲 | 模型 | seed / 手數 | FG | 封頂 | JACKPOT | 差異 |
|---|---|---|---|---|---|---|
| 彌勒佛 | collect-mult | 42 / 200,000 | 929 | 0 | — | 0 |
| 彌勒佛 | collect-mult | 777 / 40,000,000（fg-only）| 179,395 | 2 | — | 0 |
| Tiger and Dragon | coin-lock | 42 / 300,000 | 368 | 0 | 1 | 0 |
| Tiger and Dragon | coin-lock | 777 / 20,000,000（fg-only）| 24,921 | 35 | 120 | 0 |

## 出現差異時

| 現象 | 多半原因 |
|---|---|
| 第一個差異就在第 0 局 | seed 語意不同（Go 多 worker 時 seed + i×1000003）、或設定檔不是同一份 |
| 差異從某個 FG 局開始、之後全錯 | FG 內抽值順序 / 次數不同（多抽或少抽一次 Intn）|
| 只有 total 不同、mg/fg 相同 | MaxWin 封頂語意（彌勒佛：MG+FG 合計封頂、FG 分項不封頂；T&D：扣在 Bonus、Bonus 統計記封頂後）|
| MG 贏分不同 | 第一軸符號規則、WILD 倍數相加 / 連乘、Line_bet |
| 觸發局不同 | 觸發只在條件成立時才呼叫 Intn（短路求值）|
