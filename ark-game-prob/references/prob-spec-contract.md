# ark-game-prob 契約 v1 — prob-spec（機率規格書）Content 軌 / View 軌 / 中繼層

> 延續 ark-game-quicktest v1.1 的 prob-spec 契約（六段、人工區、meta.derived、ps_lint），加上 xlsx 模式與 prob-data.json。
> 兩種模式產**同一份**契約的 md / meta / html，下游（wiki ingest、日報、ark-game-quicktest 回填）不需分辨。

## 1. 兩種來源模式

| | xlsx 模式 | qt 模式 |
|---|---|---|
| 場景 | 已上線遊戲還原、機率人員已完成公版機率表 | 新遊戲設計鏈：ark-game-spec → config-spec（value null）→ quicktest |
| 來源 | `機率表.xlsx` → `prob-data.json` | `data/quicktest/<slug>/`（qt-config.yaml、odds_<ver>.json、quicktest.yaml、qt-report/rtp-report.json）+ gdd-pack + run（decisions / state-machine / kb-refs）|
| 數值狀態 | 定案值（source: xlsx 座標）| 決議值（source: D-id）或 `null` → **待決議** |
| 入口 | `ps_probspec.py --data <prob-data.json>` | `ps_probspec.py --qt <dir>` |
| frontmatter | `mode: xlsx`、`sources.xlsx / sources.prob-data` | `odds_version`、`sources.qt-config / odds / quicktest / gdd / decisions …` |
| §2 數據資料 | xlsx「數據資料」分頁的快測報表（FastTest 格式）| rtp-report.json + 三向 checks |
| §4 來源欄 | `參數表!C22` 這類座標 | qt-config.provenance（D-id / competitor_reference / template）|

## 2. prob-spec.md

frontmatter：`title, contract: "1", kind: prob-spec, slug, game, [mode], [odds_version], status: draft|review（有快測結果 → review）, distribution: internal, date, author, source_skill: ark-game-prob, verdict: confirmed|inconclusive|rejected|未快測, pending_params, sources{key: 路徑}`。

六段（順序固定，對應公版「機率規格書製作方針」）：

| 段 | 內容 | 標記 | 人工區 id |
|---|---|---|---|
| 1. 規格簡述 | 基本規格表、Pay table、（xlsx 模式）「規格簡述」分頁原文、機率人員簡述 | **SPEC** | `summary` |
| 2. 數據資料 | BASE INFO 表（階段 / RTP / Freq / Trigger / 倍率 / 最大倍率）、快測執行資訊、golden 對照與誤差、FG 強中弱實測分佈；未快測 → 整表「—」 | — | — |
| 3. 機率流程圖 | mermaid（qt 模式取 dev-spec/state-machine.md 原樣；xlsx 模式由表編號自動帶骨架）+ 流程補充 | — | `flow-notes` |
| 4. 參數表 | 每張表 + 「來源」欄；null → **待決議**（不帶來源）| — | `param-notes` |
| 5. 競品資料／手法對應 | 機制 → K 卡；qt 模式自 kb-refs 帶 FROM_KB / PROPOSED | FROM_KB / PROPOSED | `competitor` |
| 6. 隱性規則 | qt 模式自 decisions 帶 DECIDED；xlsx 模式列「隱性規則」分頁原文；人工區填 規則 / 設計目的 / 對應表 / 更改需同步 | **DECIDED** | `hidden-rules` |
| 邊界聲明 | 來源 sha、程式化轉出聲明、人工區規則 | — | — |

人工區：`<!-- human:<id> -->…<!-- /human -->`；重產時以 id 對應保留原文；人工區內的數字不受 PS-NUM 保護（PS-HUMAN warn）。

**數字格式**：浮點數以 `repr` 輸出（與 JSON 來源逐字相同），整數可帶千分位（lint 比對前去逗號）。這是 PS-NUM 能回溯的前提。

## 3. prob-spec.meta.json

```json
{"contract":"1","kind":"prob-spec","mode":"xlsx|qt","slug":"…","game":"…",
 "sections":["1. 規格簡述","2. 數據資料","3. 機率流程圖","4. 參數表","5. 競品資料／手法對應","6. 隱性規則"],
 "pending_params":0,"verdict":"confirmed",
 "sources":{"xlsx":{"path":"…","sha256_16":"…"},"prob-data":{"path":"…","sha256_16":"…"}},
 "derived":[{"value":"99.9395","from":"數據資料 總計"},{"value":"-0.088","from":"rtp_total − golden"}],
 "md_sha256_16":"…","generated":"2026-10-06T17:19:00"}
```
`derived` = 腳本算出或轉格式的每個數字與公式來源，ps_lint 當允許集；`sources` 的 path 相對專案根，lint 從任何 cwd 都能定位。

## 4. prob-data.json（xlsx 模式中繼層，ps_extract 產）

```
contract "1" / kind "prob-data" / slug / game / source{path,name,sha256_16} / generated / sheets[{name,hidden,dims}]
params{sheet, blocks[{id:"M-1"|"F-2"|"基本資訊"|"Odds表", title, anchor:"參數表!A20", tables[{c0, rows[{r, cells[]}]}]}]}
known{board{k:v}, paytable[{tier,sym,odds{"3":..}}], reelsets{block,sets[{idx,flags[],weight,extra{},row}],totals{TOTAL RTP,FG RTP,weight_sum}},
      weights[{block,head,items[{label,weight,rest[]}]}], dual[{block,names[],columns[{col,pairs[[v,w]],total,extra{}}]}],
      yesno[{block,rows[{name,yes,no}]}], matrix[{block,caption,head[],groups[{name,values[]}]}],
      series[{block,head,rows[{label,values[]}]}], scalars[{block,title,label,value}]}
report{run{workers,rounds_per_worker,total,seconds,version,timestamp,times,total_win,total_bet,speed,flag},
       base{Main|Free|Feature|GRAND|Total:[GAME%,Freq,Trigger%,Multi,PlayTimes,RetriRate,MaxMulti]},
       symbol_hit_rate{sym:[x2..x5,total]}, symbol_hit_rtp{…}, reel_set_rtp[{set,spins,total,fg}],
       asset_100[{range,pct}], multiple[{range,spins_per_hit,ge,spins_per_hit_ge}], special_range[{range,appear[3],rtp[3],fg_avg_spin}],
       decile[{label,vals[]}], summary{rtp_main,rtp_free,rtp_total,fg_trigger,fg_avg,mg_max,fg_max,total_max}, fg_detail{…}, sections_found[]}
strips{main_strip|free_strip|fake_strip:{Reels_g|假轉:{reels[[sym…]×n], counts[[label,R1..Rn]], anchor}}}
raw_log / guide[] / brief[] / hidden[] / notes[]
```
百分比在 `report` 內保留**原數值（單位 %）**；`known` 內的 RTP 若 < 5 視為小數（×100 顯示）。

## 5. View 軌（prob-spec.html）

- 頁首第一行 `<!-- content-src: prob-spec.md sha256:<16> -->`（與 ark-md-report report_pair 同格式）；ps_lint PS-STALE 據此驗。
- 只讀 prob-data.json（數字）與 prob-spec.md（人工區文字）；章節見 `view-contract.md`。
- 單檔；外連只有 Google Fonts 與 mermaid CDN；light / dark 皆設計；手機寬不橫向捲動。

## 6. prob-spec.xlsx（qt 模式選配，ps_probtable）

分頁：製作方針 / 規格簡述 / 數據資料 / 機率流程圖 / 參數表 / Main·Free Game Strip / 轉置 Strip / 隱性規則 / `_meta`（隱藏：content-src md sha16、odds sha16、產生者）。總顆數與權重合計為 COUNTIF / SUM 活公式；null → 「待決議」黃底；ps_lint 以 `_meta` 驗 xlsx ↔ md ↔ odds。

## 7. config-diff（ps_diff）

`config-diff.json`：`{contract, kind:"config-diff", data{path,sha}, config{path,sha}, map, summary{rules,match,mismatch,missing}, rows[{rule,xlsx,config,status,xlsx_value,config_value,note}]}`；`config-diff.md` 同內容表格。status ∈ match / mismatch / missing-xlsx / missing-config / missing-both。map 格式見 `config-map.fasttest.yaml` 檔頭。

## 8. ps_lint 規則

PS-SECTIONS / PS-NUM（JSON 來源走結構化值並略過座標鍵 r / c0 / col / anchor；xlsx 等二進位只驗 sha；sha / 16 位以上 hex 不算數字）/ PS-PROV / PS-STALE / PS-HUMAN / PS-INJECT。error exit 3；`lint-report.json` 含 summary{errors, warnings, pending_marks, sections, sources}。
