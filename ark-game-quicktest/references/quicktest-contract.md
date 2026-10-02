# ark-game-quicktest 契約 v1

## quicktest.yaml（目標；企劃／prob-architect 填）

```yaml
game: 魔龍寶藏
slug: dragon-treasure
target_rtp: 0.96          # 目標 RTP（Math 拍板）；缺 → 第①向 SKIP
rtp_tolerance: 0.005      # 預設 ±0.5%
feel:                     # 第②向；game = 報告 BASE INFO 列名（SpecialGameTotal / Ultra / Strong / Normal / Weak…）
  - {game: SpecialGameTotal, preset: 標準節奏}     # P-005：1/150 ~ 1/80
  - {game: Ultra, band: [0.002, 0.004]}           # 自訂區間（觸發率 = 1/Freq）
```

## qt-config.yaml（qt_config 產；人可補 provenance）

```yaml
structure: {reels, rows, pay_mode: line|ways|null, lines, bet_cost, symbols: [{code, sym_id, name, group, odds}], wild_id, scatter_id}
engine: {customized: true, note: "…"}   # 選配：工程師已改 engine/ 支援非範本結構時宣告，QT-ENGINE 降為警告
sources: {config_spec, gdd, decisions}
provenance:               # 每個非 null 欄位一行；值 = 決議 D-id / gdd.symbols[…].odds / competitor_reference(E…) / template:…
  extra_odds.free_game_num: D007
  structure.reels: competitor_reference(E001,E002)     # 結構可由 OBSERVED 定案（P-002）
notes: [...]
```

## odds_<ver>.json（範本契約；語意由範本 odds_1.0.0.go 與 game_process.go 定）

| 欄位 | 語意 |
|------|------|
| `main_game_reel_data[g][r][]` | 主遊戲第 g 組、第 r 軸的輪帶（符號 ID 序列） |
| `main_game_fake_reel_data[r][]` | 演出用假帶 |
| `free_game_reel_data[g][r][]` / `free_game_fake_reel_data` | 免費遊戲同上 |
| `extra_odds.odds[sym] = [k1, k2, …, kReels]` | k-of-a-kind 單線賠付（index k−1）；3 軸 `[0,0,x3]`，5 軸 `[0,0,x3,x4,x5]` |
| `extra_rate` | 額外押注倍率 |
| `enter_free_game_gate` / `free_game_num` / `free_game_retrigger_gate` / `free_game_retrigger_spin_num` | 進 FG 門檻 / 手數 / retrigger 門檻 / 加手 |
| `is_item_card` / `max_win` | 道具卡（0/1）/ MaxWin |
| `jackpot_multiple[]` / `jackpot_acc_rate[]` | JP 基底倍數 / 累積率（範本未啟用） |
| `main_game_reel_index_set[i] = [g_r1, g_r2, …]` | 第 i 個「輪帶組合」在每一軸用哪組帶（長度 = reels） |
| `main_game_reel_set_weight[i]` | 組合 i 的抽選權重（K-022 的 RTP 旋鈕） |
| `free_game_type_weight[4]` | 超強 / 強 / 中 / 弱 四型權重 |
| `free_game_reel_index_set[j]` / `free_game_reel_set_weight[type][j]` | 免費遊戲組合與每型對組合的權重 |

`null` = TO_BE_DECIDED_BY_MATH；qt_lint 有 null 不放行。

## rtp-report.json（qt_report 產）

```
version / generated_at / spins / total_win / total_bet
games{MainGame|SpecialGameTotal|<FG 型>|Total}{rtp, hitrate, freq, multi, playtimes, retrirate, maxmulti}
detail{sd, confidence{90,95,99:[lo,hi]}, pi, pay_out_rate, avg_cashout_players, high_avg_rate, mid_avg}
symbol_hit_rate{sym}{x2..x5,total} / symbol_hit_rtp{…} / reel_set_rtp{set: rtp|null}
asset_100[] / multiple[{range, spins_per_hit, ge, spins_per_hit_ge}] / special_range[{range, appear{total,main,free}, rtp{…}, fg_avg_spin}]
decile{D1..D9, Maximum, Mean, S.D.}{total, main, free, fspin} / award_range[] / gate{checks[], verdict}
rtp_total / rtp_main / rtp_special / special_trigger_rate (= 1/SpecialGameTotal.freq)
```
百分比一律轉成 0~1 小數；`NaN%` / `+Inf` / `-` → null。

## md-report（type: data）

必要章節 Verdict / 假設與方法 / Findings / Evidence / 邊界聲明，加「驗證報告 (Verification Report)」（P-003 格式）、RTP 拆解、符號命中、輪帶組、倍數分佈、特殊遊戲區間、十分位。
日期取報告產生時間；同報告重編 bit-identical。`tags: [rtp, case]`。

## 三向規則與 Finding 嚴重度

| 檢查 | FAIL 嚴重度 | 建議動作 |
|------|-------------|----------|
| rtp | P0 | 調輪帶 / 權重；先看 Reel Set RTP 哪組偏 |
| feel:<game> | P1 | 調觸發帶 Scatter 權重，對照 P-005 區間 |
| null | P0 | 補 Decision Record 或改回 null |
| SKIP（缺目標） | P3 | 補 quicktest.yaml / config-spec |
| 樣本 < 1e7 | P2 | TotalRound ≥ 1e7 |

## prob-spec（機率規格書 Content 軌，v1.1）

落點 `data/prob/<slug>/`。`qt_probspec.py --qt data/quicktest/<slug> [--gdd] [--run] [--out data/prob] [--slug] [--version]`；gdd / run 預設由 `qt-config.yaml.sources`（gdd、config_spec 的上兩層）推；decisions 取 `sources.decisions` 或 `<run>/decisions.yaml`。

frontmatter：`title, contract: "1", kind: prob-spec, slug, game, odds_version, status: draft|review（有 rtp-report → review）, distribution: internal, date, author, source_skill, verdict: <三向 verdict|未快測>, pending_params, sources{key: 相對專案根路徑}`。

六段（順序固定，對應公版「製作方針」）：

| 段 | 內容 | 來源 | 標記 |
|---|---|---|---|
| 1. 規格簡述 | 基本規格表（gdd.yaml.spec，kv:false 除外）；每個 feature 一節，rules/*.md 逐條；「機率人員簡述」人工區 | gdd-pack | **SPEC** |
| 2. 數據資料 | 公版表：階段 / RTP / Hit% / 觸發率(=1/freq) / 平均觸發局數 / 平均倍率 / 最大倍率 / 平均局數；三向 checks；目標 RTP（quicktest.yaml） | rtp-report.json | 無報告 → 整表「—」+「未快測」 |
| 3. 機率流程圖 | dev-spec/state-machine.md 的 mermaid 原樣；「流程補充」人工區 | run | 無 → UNKNOWN |
| 4. 參數表 | 基本資訊（盤面、對獎、收費）/ Odds 表（x1..xReels）/ 觸發與上限參數 / 輪帶組 index_set × weight / 四型權重 / 輪帶符號顆數；每列「來源」= qt-config.provenance | odds.json + qt-config | null → **待決議**（不帶來源） |
| 5. 競品資料／手法對應 | kb-refs.yaml 每個 item：知識庫命中 → **FROM_KB**；無 → **PROPOSED** 新設計；「競品」人工區 | run | — |
| 6. 隱性規則 | decisions 中非 defer 且 value 非 null：編號 / topic / 值 / reason（設計目的）/ decided_by；defer 計數；「hidden-rules」人工區 | decisions.yaml | **DECIDED** |

人工區：`<!-- human:<id> -->…<!-- /human -->`（id：summary / flow-notes / param-notes / competitor / hidden-rules）；重產時以 id 對應保留原文。

`prob-spec.meta.json`：`{contract, slug, game, odds_version, sections[6], pending_params, verdict, sources{key:{path, sha256_16}}, derived[{value, from}], md_sha256_16, generated}`。`derived` 是腳本算出的每個數字（百分比、1/freq、顆數、長度、defer 數）及其公式來源，供 ps_lint 當允許集。

ps_lint：PS-SECTIONS（六段順序）/ PS-NUM（人工區外每個數字 ∈ 來源檔全文 ∪ derived；id 類 D001 / E001 / R1 / x3 / K-022 不算數字）/ PS-PROV（§4 有值必有來源；待決議不得帶來源→warn）/ PS-STALE（來源 sha、html 戳記；來源路徑相對專案根，lint 從任何 cwd 都能找）/ PS-HUMAN（人工區含數字 warn）/ PS-INJECT。

html：單檔、planner 暗金 token、mermaid CDN、人工區虛線框、待決議紅字；頁首 `<!-- content-src: prob-spec.md sha256:<16> -->` 與 ark-md-report report_pair 同格式。

### prob-spec.xlsx（View 軌公版，qt_probtable）

分頁與公版對照：`機率規格書製作方針`（固定文字）/ `規格簡述`（gdd spec + rules 逐行，來源欄）/ `數據資料`（公版座標：G2 表頭 RTP·Hit%·觸發率·平均觸發局數·倍率·最大倍率·平均局數，F3 起各階段；觸發率 = 1/freq；未快測整列 `--`）/ `機率流程圖`（mermaid 原文，drawio 待）/ `參數表`（基本資訊 C2:D、Odds 表 C8 起 Description·Symbol·sym_id·1..N·來源、表P-1 觸發與上限參數、表M-1 主遊戲 index_set × Weight + SUM、表F-1 四型權重 + SUM、表F-2 免費 index_set × 四型 Weight）/ `Main Game Strip`·`Free Game Strip`（每組一塊：Reels_g、R1..Rn 符號 code、右側「總顆數」COUNTIF 活公式 + Total SUM）/ `轉置 Strip`（Symbol / 轉換用Code = sym_id / 名稱 / 組）/ `隱性規則`（編號 / 情況 / 說明 / 設計目的 / 來源）/ `_meta`（隱藏：content-src md sha16、odds sha16、產生者）。
null → 「待決議」黃底；ps_lint 以 `_meta` 戳記驗 xlsx ↔ md ↔ odds 一致。

## v1.2 範本相容性守門

### qt_lint 新規則

| 規則 | 條件 | 嚴重度 | 依據 |
|---|---|---|---|
| QT-ENGINE | `structure.{reels, rows, pay_mode, lines, bet_cost, wild_id, scatter_id}` ≠ 範本 `{3, 3, line, 5, 5, 1, 2}` | error（`engine.customized: true` 時 warning）；欄位為 null → warning | 審查報告 F-3；設計文件 §4.2 |
| QT-CAP | sym_id ≥ 32；`main_game_reel_index_set` > 11 組合；`free_game_type_weight` > 4 型 | error；sym_id = 31 → warning | F-4；設計文件 §7.3 |
| QT-SYMID | sym_id 不在公版區段（1 Wild、2 Scatter、3～10 特殊、11～20 高倍、21～30 低倍；group=normal 應在 11～30） | warning | 設計文件 §4.1 |

`first_errors` 排序：非 QT-NULL 的 error 在前（結構性問題比缺值優先處理）。

### qt_run patch（engine 副本）

| 檔案 | patch | 依據 |
|---|---|---|
| main.go | `GameName`、`OddsVersion`、`TotalRound` | v1.0 |
| main.go | `odds.LoadProbSetting("odds/odds_<ver>.json")`（範本寫死 1.0.0） | F-3 |
| main.go | `seed := int64(<--seed>) + int64(i)*1000003`（預設 20261001；`--seed 0` 不 patch） | F-9 |
| game/game_process.go | `ReelAmount / FreeReelAmount / ReelLength / FreeReelLength / SymbolWild / SymbolScatter` | v1.0（只在 engine.customized 時有意義） |

範本預設位置 `data/references/prob-workflow/quicktest-template`（2026-10-01 起；舊 `data/dev-sample/機率工作流/快測範本` 已移除）。main.go 任一必要 patch 未命中 → `QUERY_FAILED`。

### rtp-report.json `template_caveats[]`

`[{id, finding, row, msg}]`；`id`：`fg-type`（F-1，某 FG 型列與 SpecialGameTotal 逐欄相同）/ `retrigger`（F-5，RetriRate = 0）/ `scatter-column`（F-6，Scatter 在 x2 欄有值）/ `multiple-cumulative`（F-7，第一列「倍以上」= 第二列）/ `maxwin-count`（F-2，maxwin 有次數）。只加註，不改 verdict；md 報告與 prob-spec §2 會列出。
