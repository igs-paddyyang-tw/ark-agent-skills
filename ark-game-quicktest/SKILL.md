---
name: ark-game-quicktest
description: |
  C2 段「Go 快測」的膠合層：以機率工程師的 Go 快測範本（data/references/prob-workflow/quicktest-template）為 runtime，
  deterministic 做三件事——① qt_config：config-spec.yaml（P-002，value 一律 null）+ gdd-pack 符號賠率 + decisions → 範本契約的
  odds_<ver>.json 骨架（結構定案、機率參數留 null，非 null 欄位必附來源）；② qt_lint：有 null 不准跑、無來源不准填、符號/輪帶/權重自洽；
  ③ qt_run / qt_report：實例化範本、patch 常數、go run、把 report_<ver>.txt 解析成 rtp-report.json 並編成 ark-md-report（type: data），
  verdict 走 P-003 三向（RTP ±容許、觸發率對照 P-005 體感區間、config-spec 無效值阻斷）。只回報數值不下結論。
  v2.0：機率規格書（prob-spec / 參數表 / 隱性規則）職責已移至 ark-game-prob，`--probspec` 轉呼叫同層 ark-game-prob。
  使用此 skill 當使用者或 agent 提及：快測、RTP 模擬、Monte Carlo、odds.json、輪帶權重、觸發率驗證、三向守門、
  spec_lint 第二向、快測報告、report_1.0.0.txt、config-spec 轉快測設定、跑 Go 快測、RTP 誤差、體感區間。
  不適用於：機率規格書與 prob-spec（→ ark-game-prob）、設計機率架構與 K 卡取捨（→ ark-game-prob）、
  改 game_process.go 的玩法邏輯（人／工程師）、決議 Open Questions（→ ark-grill-me）、
  產 config-spec（→ ark-game-spec gs_dev）。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "2.0.0"
  updated: 2026-10-06
  outputs:
    - { format: data, audience: ai }
    - { format: md, audience: ai }
  render: none
  depends_on: [ark-game-spec, ark-game-prob, ark-md-report]
---

# ark-game-quicktest — 規格 ↔ 快測範本 ↔ 驗證報告

一句話：**範本是引擎，本 skill 保證兩頭對得回規格**——進去的 config 每個非 null 值都有決議來源，出來的報告每個數字都原樣可追，
中間的玩法邏輯（`game_process.go`）由人改。RTP 是模擬結果不是輸入（P-002 / P-003）。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `pyyaml` | 全部 | exit 8 |
| 快測範本目錄（`--template`，預設 `data/references/prob-workflow/quicktest-template`） | qt_run | exit 2 |
| Go ≥ 1.20（`go` 在 PATH，或 `--go` / `$GO_BIN`） | qt_run 實跑 | exit 8，engine/ 已實例化可拿去別台跑 |
| ark-md-report（同層） | qt_report 的 report_lint / register | 略過 lint（結果標 PASS 但未驗） |

## 資產地圖

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/qt_config.py` | config-spec + gdd symbols + decisions → `odds/odds_<ver>.json` + `qt-config.yaml`（結構、符號表、provenance）；v1.2 另寫 `structure.pay_mode / lines / bet_cost`（gdd「對獎方式 / 收費」或 `--pay-mode --lines --bet-cost`）。**符號分類（ISSUE-QT-001）**：只有線賠符號（group==normal 或無 group 但有 odds）進 `extra_odds.odds`；WILD/trigger/collectible/jackpot 不進 odds 表、改記 `symbols[].role`，不被當線賠要值 | 規格決議完、要開快測 |
| `scripts/qt_lint.py` | QT-NULL / QT-PROV / QT-SYM / QT-REEL / QT-RANGE；v1.2 加 **QT-ENGINE**（結構超出範本 3×3 線型 5 線收費 5 → error，`engine.customized: true` 降警告）/ **QT-CAP**（sym_id ≥ 32、主遊戲組合 > 11、FG 型 > 4 → error）/ QT-SYMID（警告）→ `lint-report.json`；error exit 3 | 任何人手填 odds.json 後必跑 |
| `scripts/qt_run.py` | lint → 複製範本到 `engine/` → patch main.go（含 v1.2 的 odds 載入路徑跟版本、固定 seed `--seed`）/ game_process.go 常數 → `go run .` → qt_report | 跑快測 |
| `scripts/qt_report.py` | `report_<ver>.txt` → `rtp-report.json` → md-report（三向 verdict）；v1.2 加 `template_caveats`（偵測範本已知偏差 F-1/F-2/F-5/F-6/F-7，md「範本已知偏差」節）；`--publish docs/reports/data` | 已有報告檔、只要驗證 |
| `references/quicktest-contract.md` | quicktest.yaml（目標）/ odds.json 語意 / rtp-report.json / 三向規則 | 建目標檔、改 lint 時 |
| `scripts/tests/` | golden：範本 `report_1.0.0.txt` 解析與三向、範本 odds 通過 lint、null/provenance 阻斷、決議填值 | 改腳本後 |

## 決策樹

```
拿到一款遊戲的規格
├─ 還沒決議（game-spec.draft）→ 先 ark-grill-me → gs_decide → gs_dev（config-spec.yaml）
├─ python scripts/qt_config.py --out data/quicktest/<slug> --config-spec <run>/dev-spec/config-spec.yaml --gdd data/gdd/<slug> --decisions <decisions.yaml>
│     └─ 看 qt-config.yaml.notes：盤面未定 / 符號無 sym_id / 賠率缺 → 回規格補，不手填
├─ 輪帶、權重、門檻 → 機率工程師依 K 卡設計後填進 odds.json，每個值在 qt-config.yaml.provenance 記決議 D-id
├─ python scripts/qt_lint.py --dir data/quicktest/<slug>
│     ├─ QT-NULL → 還有未定參數，回決議；QT-PROV → 有值沒來源，補 D-id 或改回 null
│     ├─ QT-ENGINE → 盤面 / 對獎 / 線數 / 收費 / Wild·Scatter ID 超出範本；工程師改 engine/ 後在 qt-config.yaml 加 `engine: {customized: true, note: …}`
│     ├─ QT-CAP → 範本 Recorder 陣列會越界 panic；sym_id 改到 ≤ 30 或請工程師擴陣列
│     └─ PASS → 可跑
├─ 玩法不是範本的 3×3 線型 → 工程師改 engine/game/game_process.go（P-004 K 卡→Go 映射），本工具不碰邏輯
├─ python scripts/qt_run.py --dir data/quicktest/<slug> --rounds 10000000 --targets quicktest.yaml --config-spec <config-spec.yaml>
│     ├─ 沒 go → engine/ 已就位，拿去 daemon 主機（~/.local/go）跑，再 qt_report --report engine/report_<ver>.txt
│     └─ qt-report/<date>-quicktest-<slug>.md：verdict confirmed / inconclusive / rejected
├─ rejected → 看 Findings（P0 RTP 偏離 / null 偷渡；P1 體感區間）→ 調參重跑；confirmed → 審核後彙整
└─ 要機率規格書 / 參數表 / 隱性規則 → 用 **ark-game-prob**（`ps_run.py --qt data/quicktest/<slug>`）；本 skill 的 `qt_run --probspec` 會轉呼叫同層 ark-game-prob
```

## 目錄

```text
data/quicktest/<slug>/
├── quicktest.yaml        目標：target_rtp / rtp_tolerance / feel[{game, preset|band}] / game / slug
├── qt-config.yaml        structure{reels, rows, symbols[code, sym_id, odds], wild_id, scatter_id} / provenance{欄位: D-id|來源} / notes
├── odds/odds_<ver>.json  範本契約（main/free reel_data、extra_odds{odds, gates, weights…}）
├── lint-report.json
├── engine/               範本實例（勿手改 odds；玩法改 game/game_process.go）
│   └── report_<ver>.txt、AwardRangeData_<ver>.csv、ReelSetData_<ver>.csv
└── qt-report/            rtp-report.json、<date>-quicktest-<slug>.md
```

## 三向守門（P-003）

| 向 | 規則 | 結果 |
|----|------|------|
| ① RTP | \|Total RTP − target_rtp\| ≤ rtp_tolerance（預設 0.005） | FAIL → P0 |
| ② 體感 | 各特殊遊戲 1/Freq 落在 P-005 區間（preset：驚喜型/期待型/節奏型/核心體驗型/稀有大事件/標準節奏/高頻小獎，或自訂 band） | FAIL → P1 |
| ③ 無效值 | config-spec parameters 有 value 且無 decision | FAIL → P0 |

verdict：任一 FAIL → rejected；全 PASS → confirmed；有 SKIP（缺目標）→ inconclusive。信心：樣本 ≥ 1e7 high / ≥ 1e6 medium / 其餘 low。

## 邊界

- **不決定數值**：qt_config 只搬結構與有決議的值；輪帶、權重、門檻由機率工程師填，沒來源的值 lint 擋。
- **不改玩法**：範本 `game_process.go` 是 3×3 線型；新機制靠人改。patch 只動 engine 副本的常數（軸數、列數、Wild / Scatter ID、回合數、版本、odds 載入路徑、seed），`data/references` 範本本身不改。
- **範本已知偏差**：見 `docs/reports/review/2026-10-01-quicktest-template-review.md`（F-1～F-11）與設計文件 `docs/designs/2026-10-01-quicktest-template-design.md`；qt_lint 擋會讓結果錯或 panic 的（F-3、F-4），qt_report 對只影響解讀的加註（F-1、F-2、F-5、F-6、F-7）。
- **可重現**：`--seed` 固定時，同設定 + 同 CPU 數結果相同（worker 數 = NumCPU）；`--seed 0` 回到範本的時間 seed。
- **報告只回報**：verdict 是守門結果，不是設計結論；Volatility / Percentiles 定義待 math-reviewer（Stage 1a Accumulator 日後當外掛接上）。
- **Jackpot / 道具卡**：範本未啟用，報告段為「尚無資料」，解析保留原樣。
- **機率規格書已移出**：prob-spec / 參數表 / xlsx / 隱性規則等機率規格書產出職責在 v2.0 移至 **ark-game-prob**（`ps_run.py`）；本 skill 只產快測與 rtp-report，`qt_run --probspec` 轉呼叫同層 ark-game-prob。
