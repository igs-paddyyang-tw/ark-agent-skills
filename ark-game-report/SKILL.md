---
name: ark-game-report
description: |
  Slot 新機上線成效報告 executor：把一款新機的上線表現做成標準格式報告（D+7 上線初判 / D+14 檢查點 / D+30 穩態定調），
  並帶出分析思維與策略方向。一個入口 gr_run 串六段：init（report.yaml 設定）→ query（依 adapter 產 SQL，
  交 ark-db-query 匯出標準資料集）→ probe（盤點拿得到哪些數據，產能力矩陣，缺的區塊自動降級）
  → build（資料集 → 指標、歷史新機同期分位數、燈號 → report.json）→ insight（metrics × playbook：
  發現、假設、要查什麼、建議方向、知識庫參考 → insights.md 與結論草稿）→ render（單檔 HTML，可離線開、轉 PDF）
  → closeout（工作流最後產出：十階段結案報告，彙整 ①～⑩ 狀態、快測、⑨ 拍板、⑩ 成效 → ark-md-report 契約 md＋HTML）。
  分析框架固定為六問加健康觀察：規模、玩家結構、黏著、深度、機率表現（實際 RTP vs 信賴帶、觸發率 vs 規格）、
  增量與侵蝕；設定、adapter、playbook 都是 yaml，依實戰可取得的數據調整，不用改程式。只算數字與草擬，結論由人確認。
  使用此 skill 當提及：上線成效、成效報告、新機表現、上線報告、D+7、D+30、7 日／30 日趨勢、押注佔比、試玩率、
  機台回訪率、留存、侵蝕率、新機吃舊機、實際 RTP 對帳、觸發率對帳、玩家分層、VIP 組成、成效分析思維、上線後要調什麼。
  不適用於：每日大螢幕觀測看板（現行 live-dashboard）、上線前的機率規格書（→ ark-game-prob）、
  Go 快測與 RTP 模擬（→ ark-game-quicktest）、任意 SQL 查詢（→ ark-db-query）、一般 HTML 報告排版（→ ark-html-report）。
metadata:
  schema_version: "1.1"
  status: experimental
  author: paddyyang
  category: executor
  version: "0.2.0"
  updated: 2026-10-19
  outputs:
    - { format: data, audience: ai }
    - { format: md, audience: both }
    - { format: html, audience: human }
  render: html
  depends_on: [ark-db-query, ark-wiki-engine]
---

# ark-game-report — 老虎機上線成效報告

一句話：**格式固定、資料可變、結論由人定。** 版面與分析框架標準化；能撈到什麼數據，就產出哪些區塊；
數字與燈號由腳本算，發現與建議由 playbook 草擬，最後人工確認後才定版。

> 製程位置：slot AI 開發製程 ⑩ 上線成效（⑨ 送審拍板、上線之後的「成效回饋」）。D+30 的結論回寫到機率設計參考（K 卡、設計指南），形成閉環。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `pyyaml` | 全部 | exit 8 |
| ark-db-query（同層）＋ BigQuery 憑證 | `query --run` | 只產 SQL，自己執行後把 CSV 放進 data_dir |
| ark-wiki-engine（同層）＋ knowledge/ | `insight` 的知識庫補搜 | 只列 playbook 的固定參考頁 |

## 資產地圖

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/gr_run.py` | 單一入口：init / query / probe / build / insight / render / all | 一律從這裡呼叫 |
| `scripts/gr_init.py` | 產 `report.yaml`（樣板 `assets/report.yaml.tmpl`）| 新報告 |
| `scripts/gr_query.py` | 依 adapter 產 5 個資料集的 SQL；`--run` 交 ark-db-query 匯出 CSV；`--bench` 為歷史新機產基準資料 | 要撈資料 |
| `scripts/gr_probe.py` | 盤點資料集與欄位 → `capability.json`（每節 ok / partial / skip 與原因），列出 adapter 的 TODO 欄位 | 每次撈完資料、改設定後 |
| `scripts/gr_build.py` | 資料集 → `report.json`（報告契約）＋ `metrics.json`（給 insight）；計算歷史分位數與燈號 | 算指標 |
| `scripts/gr_insight.py` | metrics × `assets/playbook.yaml` → `insights.md`、結論草稿；查知識庫 | 寫分析 |
| `scripts/gr_render.py` | `report.json` → 單檔 HTML；`--check` 驗一致性 | 出報告 |
| `scripts/gr_closeout.py` | **十階段結案報告**（工作流最後產出）：定版家檔案 → ①～⑩ 狀態、④ 快測、⑥ 對帳、⑨ 拍板欄、⑩ 各 D+N verdict → `docs/reports/<日>-<slug>-closeout.md／.html`；Findings 規則判定、verdict 草擬；`<!-- human:notes -->` 重產保留；自動 report_lint ＋ report_pair stamp | ⑩ 定版後、送審或結案時 |
| `assets/report_template.html` | 報告版面（資料驅動，缺區塊顯示「尚無資料」）| render |
| `assets/adapters/*.yaml` | 平台對接：表名、欄位對照、GID 格式；`TODO:` 表示待確認 | query / probe |
| `assets/playbook.yaml` | 策略 playbook：症狀 → 假設 → 要查什麼 → 建議 → 知識庫頁 | insight；實戰後增修 |
| `references/analysis-thinking.md` | 分析思維：六問、比較基準、拆解樹、常見誤判、結論寫法 | 寫結論前必讀 |
| `references/metrics.md` | 指標字典與燈號規則 | 對口徑 |
| `references/data-contract.md` | 5 個標準資料集與 report.json 契約 | 接新平台、手動準備資料 |
| `references/adapter-guide.md` | 新增 adapter、回填 TODO 欄位、實戰驗證清單 | 第一次在新平台用 |

## 決策樹

```
要做一份上線成效報告
├─ 1. gr_run.py init --slug <slug> --name <名稱> --game-id <id> --launch-date <日> --stage 7 --adapter bigquery-igs
│     └─ 編輯 report.yaml：game.ids（所有子 ID）、spec（目標 RTP、σ、觸發 1/Freq）、views、composition、benchmark_games
├─ 2. 撈資料
│     ├─ 有 BigQuery：gr_run.py query --config <yaml> --dry-run → 看掃描量 → --run（--bench 一併撈歷史新機）
│     └─ 沒有：照 references/data-contract.md 準備 CSV 放進 data_dir（最少 game_user_daily.csv）
├─ 3. gr_run.py probe：看每節 ok / partial / skip
│     ├─ skip 或 partial 的原因是 adapter TODO → 用 ark-db-query bq_schema.py 查欄位，回填 adapter 後重撈
│     └─ 確實拿不到的數據 → 接受降級，報告會註明
├─ 4. gr_run.py build → 看 data.lights 與 capability
├─ 5. gr_run.py insight → 讀 insights.md：照「要查什麼」驗證假設（必要時回到 2 補撈）
│     └─ 驗證後改寫 report.json 的 views.<切分>.verdict（headline、next），去掉「草稿」
├─ 6. gr_run.py render → <out_dir>/<資料日>-<slug>-d<stage>.html（同名 .json 一起定版）
├─ 7. gr_run.py closeout --slug <slug> → <out_dir>/<日>-<slug>-closeout.md／.html（十階段結案報告；補人工區後定版）
└─ D+30 結論 → 有設計啟示就回寫知識庫（走 ark-wiki-engine 蒸餾流程，不直接手寫 wiki）
```

## 目錄

```text
data/slot/<slug>/report/report-d7.yaml          設定（入 git）
output/slot/<slug>/report-data/d7/              工作檯（不入 git）
├── sql/*.sql                                   gr_query 產的 SQL
├── game_user_daily.csv · slot_daily.csv · slot_users.csv · erosion.csv · hours.csv   標準資料集
├── benchmark.csv 或 bench/<遊戲>/*.csv          歷史基準（二擇一）
├── capability.json · metrics.json · report.json · insights.md · insights.json
data/slot/<slug>/docs/reports/<資料日>-<slug>-d7.html／.json     定版報告（入 git；佈局契約 ⑩）
```

## 守門

| 段 | 擋什麼 | 結果 |
|----|--------|------|
| init | 日期格式、adapter 不存在、覆寫既有設定 | exit 2／3 |
| query | adapter 欄位 TODO → 該資料集或欄位略過並列出；查詢失敗 | 列 skipped；exit 6 |
| probe | 沒有 game_user_daily.csv | exit 3 |
| build | 切分欄位不存在 → 該切分略過並寫進 footnote；全部切分無資料 | exit 3 |
| render | 序列長度不一致、世代欄數不符、組成加總 ≠ 1 | exit 3 |

## 燈號（細節見 references/metrics.md）

| 問題 | 判定 |
|------|------|
| Q1 規模、Q3 黏著、Q4 深度 | 有歷史基準時看分位數：≥ P60 綠、P30～P60 黃、< P30 紅；D+7 看平均與 D1 回訪，D+30 看最後 7 日與 D7 回訪 |
| Q2 玩家結構 | 最高等級組在本機的佔比 ÷ 在全虎機的佔比，門檻見 report.yaml `lights` |
| Q5 機率表現 | RTP 連續 N 日在信賴帶外，或觸發率偏離 > 門檻（期望次數 ≥ 30）→ 紅 |
| Q6 增量 | 侵蝕率（越低越好） |
| 健康觀察 | 押量集中度、高強度玩家比例 |

沒有基準或缺資料一律「資料不足」，不用猜的。

## 邊界

- **只算與草擬，不下定論**：insight 產的是「待驗證的起點」；結論要照 checks 驗證後人工改寫。
- **不改機率、不碰線上**：Q5 異常只產通知與對帳方向，交機率人員與 ark-game-quicktest 對照。
- **健康觀察不是 KPI**：用來防止「成效其實是少數玩家過度遊玩撐起來的」，對應知識庫的設計紅線。
- **數據可變、格式不變**：新增欄位改 adapter、新增判斷改 playbook、新增切分改 report.yaml；都不用改程式。
- **營運數據不外流**：報告 HTML 只在公司內部流通。

## 版本

| 版本 | 日期 | 變更 |
|------|------|------|
| 0.2.0 | 2026-10-20 | 新增 `closeout`：十階段結案報告（工作流最後產出，ark-md-report 契約雙軌）；Q5 暫定基準：spec 無目標 RTP 時改用同期新機實際 RTP P10～P90（燈號最高「觀察」、圖例與註記標「暫定」）；健康觀察門檻改同期 P80（`lights.h_bench_q`，無基準時才用固定值），playbook CONCENTRATION／INTENSE_PLAYERS 同步改比 `h_top1_cut`／`h_intense_cut` |
| 0.1.1 | 2026-10-19 | 首次實戰（吉屋出豬 617／618 D+7、D+30，同期新機 12 款基準）：bigquery-igs adapter 實查回填（UserID／CoinBet／CoinBetTimes／CoinWin／Country／CreateDate；查無觸發次數與時段表）、加 `max_bytes_billed`；`slot_users` 改取期間內最後一筆快照（只取期末那天會讓約 59% 玩家分層欄位空白）；匯出逾時 300 秒＋重試 2 次（bq_export 偶發卡住）；D+30 的同期 P50 改與 P30／P60 同窗口（最後 7 日）；子程序加 `-X utf8`（Windows cp950）；樣板 out_dir 改 `docs/reports/`（佈局契約 ⑩） |
| 0.1.0 | 2026-10-19 | 初版 |
