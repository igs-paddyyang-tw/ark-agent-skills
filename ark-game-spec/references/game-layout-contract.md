# 遊戲產出佈局契約（game-layout contract v3.4）

> **單一來源（SSOT）**：一款遊戲從競品到上線的所有產出放哪，以本檔為準；機器可讀版是同目錄的 `game-layout.yaml`。
> 擁有者：**ark-game-spec**（製程入口）。ark-game-prob（`ps_layout` 守門）、ark-game-quicktest、ark-game-proto 依本契約讀寫路徑。
> 前版：`docs/designs/2026-10-07-game-pipeline-output-layout.md`（v2，6 階段）、`data/slot/_schema/layout.md`（v1 提案稿）——兩者改為指向本檔。
> 制定：2026-10-16，aidev-agent（樂奇）／使用者核可目錄規劃（遊戲實作改為 `game/{go-server, pixi-client}`）。
> v3.1（同日）：階段編號對齊知識庫九階段 SSOT（`knowledge/slot/raw/methodology/slot-pipeline-output-checklist.md`：⑦ 試玩版 Stage、⑧ Game Server、⑨ 上線成效）。
> v3.3（2026-10-19）：新增定版家 `review/` 拍板包（另計 < 5 MB）——給人拍板／demo 的成品進 data，`output/` 只留中間檔、二進位、大素材（使用者決議；分析見專案 `docs/reports/review/2026-10-19-data-output-review-layout.md`）。
> v3.4（2026-10-19）：閉環 **九→十階段**（使用者決議「送審＝上線前」）：`review/` 拍板包正式編為 **⑨ 送審拍板（上線前）**，原 ⑨ 上線成效改為 **⑩**（路徑與 skill 不變，仍為 ark-game-report）；stages 鍵 `拍板` → `⑨`、`⑨` → `⑩`。設計見專案 `docs/designs/2026-10-19-slot-pipeline-workflow-final-design.md`。

## 1. 兩個家與判準

| 家 | 路徑 | git | 放什麼 |
|---|---|---|---|
| 定版家 | `data/<domain>/<slug>/`（slot 為 `data/slot/<slug>/`） | ✅ | 人工決議過的定版件、定版數字與來源、原始碼現行版、正本報告、sha 清冊 |
| 工作檯 | `output/<domain>/<slug>/` | ❌ | 能重產的中繼與 View、二進位、大檔、影片與抽幀、試跑、舊版 |

🔴 硬規則：定版家目標 **< 1 MB（不含 `game/`）、不得有二進位（exe／影片／大圖）**；單檔 > 500 KB 要說明理由。
`game/`（⑦ 用戶端、⑧ Server 原始碼）另計額度 **< 1 MB**：1 MB 規則源自 milefo（4.8 MB 中 exe 佔 70%），要擋的是二進位與可重產大檔，不是原始碼；`prob-spec.html` 等受 ps_lint 戳記／空殼守門的 View 仍留定版家（v3.2，2026-10-19）。
`review/`（拍板包）另計額度 **< 5 MB**（v3.3，2026-10-19 使用者決議）：研發產物是給人拍板的，**人會打開、會拿去 demo 的成品**（⑦ 雙擊可玩的試玩單檔、② 素材總覽自足版、⑥⑦ 真瀏覽器驗收報告與代表截圖、導覽頁）即使能重產也進定版家，換機器、傳給人都打得開；仍禁二進位與影片。只在**送審前**用 `review_build` 發布一次，不是每次 build 都更新（控制 git 膨脹）。
判準一句話：**「刪掉之後能用指令重產」→ 工作檯；「刪掉就要人重做判斷」→ 定版家；「要拿給人拍板／demo」→ 定版家 `review/`。**

## 2. 十階段 × 子目錄

| # | 階段 | 子目錄 | 負責 skill |
|---|---|---|---|
| ① | 競品分析 | `analysis/` | ark-game-spec（analyze → publish） |
| ② | 遊戲規格書 | `spec/` | ark-game-spec（draft → decide → dev → gdd → publish） |
| ③⑤ | 機率規格書（骨架 → 報告，同一份檔） | `prob/` | ark-game-prob |
| ④ | Go 快測程式 | `quicktest/` | ark-game-quicktest |
| ⑥ | 機率可視化驗證 | `proto/` | ark-game-proto（驗證台） |
| ⑦ | 遊戲試玩版（Stage 正式演出版型） | `game/pixi-client/` | ark-game-proto 1.1（`stage_build`） |
| ⑧ | Game Server | `game/go-server/` ＋ `game/handoff.md` | 工程（規劃中 skill `ark-game-code`） |
| ⑨ | 送審拍板（上線前；彙整 ②⑤⑥⑦⑧ 成品＋驗收＋拍板書） | `review/` | ark-game-proto（`review_build.py`）＋ ark-book（拍板書） |
| ⑩ | 上線成效 | `report/report-d<N>.yaml`（設定）＋ `docs/reports/<資料日>-<slug>-d<N>.html／.json`（定版報告） | ark-game-report（D+7／D+14／D+30；結論由人確認）＋ math-reviewer |
| — | 本款專屬文件正本 | `docs/` | 各階段 |
| — | 逆向知識卡（還原局） | `kb/` | 人工 ＋ `data/slot/_schema/tools/sg_*` |

## 3. 定版家目錄樹（設計局）

```
data/slot/<slug>/
├── README.md                          遊戲卡（doc_role: index；模式、版本、①～⑩ 狀態）
├── LAYOUT.md · layout-report.json     ps_layout 產物（勿手改）
├── publish-manifest.json              gs_publish 的 sha 清冊
├── analysis/                     ①
│   ├── game-analysis.yaml · kb-refs.yaml · evidence.jsonl
│   ├── report/<date>-game-analysis-<run>.md
│   └── source/                        競品素材登錄（不放素材本體）
│       ├── manifest.json              素材路徑 ＋ sha256 ＋ 用途
│       └── competitor-spec-<ver>.md   人工競品規格書（內容不改，只複製）
├── spec/                         ②
│   ├── game-spec.v1.md · decisions.yaml · decisions-applied.json · config-spec.yaml
│   ├── dev-spec/                      game-spec · feature-spec · state-machine · ui-spec · qa-checklist（config-spec 由 gs_publish 提到 spec/ 根層）
│   └── gdd/                           gdd.yaml · symbols.yaml · screens.yaml · info.yaml · i18n.csv · rules/*.md
├── prob/                         ③⑤
│   └── prob-spec.md · prob-spec.html · prob-spec.meta.json · [prob-spec.xlsx] · [config-diff.*] · lint-report.json
├── quicktest/                    ④
│   ├── quicktest.yaml · qt-config.yaml · symbols.tsv · lint-report.json
│   ├── odds/odds_<ver>.json · [config/<A版>.json]
│   ├── engine/                        Go 快測原始碼快照（含 MANIFEST.json）
│   ├── qt-report/                     rtp-report.json · <date>-quicktest-<slug>.md
│   └── _tuning/                       本款專屬推導／調參腳本（不上游）
├── proto/                        ⑥
│   └── game-config.json · index.html · go-parity.* · gaps.md
├── game/                         ⑦⑧
│   ├── pixi-client/              ⑦   PixiJS 試玩版遊戲包（ark-game-proto Stage：game.js、stage.yaml、stage-build.json、建置腳本）
│   ├── go-server/                ⑧   Go Server 原始碼（雛型或正式）
│   └── handoff.md                ⑧   工程交付單（設定檔 sha、prob-spec 版本、rtp-report sha、K 卡 → Go 映射）
├── review/                       ⑨ 送審拍板包（v3.3；額度另計 < 5 MB；送審前 review_build 發布）
│   ├── index.html                     拍板書（ark-book book_build 產物：封面、書脊目錄、每個待拍板事項一章、附錄；自足、離線可開）
│   ├── <slug>-decision/               拍板書原稿（ark-book 契約）：book.yaml · 00-preface · 0N-<R-x 章>（人工，含拍板欄）· 99-appendix-artifacts（review_build 每次重產）
│   ├── play.html                 ⑦   試玩版單檔（= stage_build --single，雙擊可玩）
│   ├── gdd-overview.html         ②   素材總覽自足版（縮圖內嵌 WebP）
│   ├── checks/                   ⑥⑦ browser-check.json · stage-smoke.json · 代表截圖 *.webp
│   └── review-manifest.json           來源路徑＋sha16＋大小
└── docs/
    ├── decisions/                     OQ 清單、決策摘要（type: decision）
    ├── designs/                       機率架構設計、引擎缺口交接單
    ├── reports/                       交叉比對、快測審核、試玩紀錄、⑩ 上線成效報告（ark-game-report）
    └── versions/                      版本沿革
```

## 4. 工作檯目錄樹

```
output/slot/<slug>/
├── runs/<run_id>/                ①② 影片 run（含 video/、frames/；gs_run 的工作目錄）
├── analysis/                     ① 競品規格書單檔 View（圖片內嵌的大 html）
├── gdd/                          ② gdd 的 View：素材總覽.html ＋ assets/（圖檔）＋ export/
├── game/
│   ├── pixi-client/              ⑦ Stage 建置輸出（single/index.html、folder/）
│   └── go-server/                ⑧ Server 二進位與執行產物
├── proto/                        ⑥ 雛型建置中間檔
├── build/ · qt-runs/             ④ exe、試跑
├── sandbox/                      實驗、重跑驗證
└── _retired/                     退役件
```

## 5. 還原局（已上線遊戲）

必有：`README.md`、`kb/`（spec · prob · code · qt-result · versions · methods ＋ `xlsx/` ＋ `paramcheck/` ＋ `notes/`）、`quicktest/engine/`、`quicktest/qt-report/`。
選配：`prob/`（`ps_run --xlsx`）、`spec/config-spec.yaml`（`gs_run --stage restore`，mode: restore-live）、`docs/`。
`kb/` 由 `sg_lint.py` 守門；佈局由 `ps_layout --mode restore` 守門。

## 6. 跨遊戲的東西不放遊戲資料夾

| 東西 | 位置 |
|---|---|
| 執行計畫、pipeline 狀態檔 | 專案層 `docs/plans/`、`docs/pipeline/<slug>.yaml` |
| skill 規格／設計（例：pack 擴充） | 專案層 `docs/specs/`、`docs/designs/` |
| 手法卡、方法論 | `knowledge/slot/` |
| 競品素材本體（影片、裁圖、試玩） | 原始位置（例：`D:\kiro-cli\data\<競品>`），只在 `analysis/source/manifest.json` 登錄 |

## 7. 各 skill 的讀寫點

| skill | 寫入 | 讀取 |
|---|---|---|
| ark-game-spec | `gs_run --slug <slug>` 預設 run 在 `output/slot/<slug>/runs/`；`publish` → `analysis/`、`spec/`（含 `spec/gdd/`）、`analysis/source/` | 本契約 |
| ark-game-quicktest | `quicktest/` | `spec/config-spec.yaml`、`spec/decisions.yaml` |
| ark-game-prob | `prob/`；`ps_layout` 產 `LAYOUT.md` | `quicktest/`、`spec/`、`analysis/` |
| ark-game-proto | 驗證台 → `proto/`；Stage → `game/pixi-client/`（清冊）＋ `output/slot/<slug>/game/pixi-client/`（建置） | `prob/prob-spec.md` |
| 工程 | `game/go-server/`、`game/handoff.md` | `quicktest/odds/`、`prob/` |

## 8. 相容與遷移

- 舊路徑在一個版本內仍可讀：`proto/stage/`（→ `game/pixi-client/`）、`server/`（→ `game/`；`server/handoff.md` → `game/handoff.md`）、`docs/report/`（→ `docs/reports/`）、`data/gdd/<slug>/`（→ `spec/gdd/` ＋ `output/slot/<slug>/gdd/`）、`artifacts/cva/<run>/`（→ `output/slot/<slug>/runs/`）。
- 遷移只搬不刪；搬完跑 `ps_layout --game data/slot/<slug> --mode design`，error = 0 才算完成。
- 本契約改版時同步 `game-layout.yaml`，並在 `data/slot/_schema/layout.md` 與 `knowledge/slot/raw/methodology/game-pipeline-layout.md` 更新指標。
