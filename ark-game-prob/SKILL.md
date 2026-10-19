---
name: ark-game-prob
description: |
  機率規格書（prob-spec）executor：遊戲開發製程 C 段「機率」的唯一產出 skill，與 ark-game-spec（遊戲規格書）、
  ark-game-quicktest（Go 快測）三件套。deterministic：① ps_extract 把機率人員的公版「機率表 xlsx」轉成 prob-data.json（每個數字附 分頁!儲存格 來源）；
  ② ps_probspec 組公版六段 Content 軌 prob-spec.md + meta（xlsx 模式＝已上線還原、qt 模式＝quicktest 的 odds + rtp-report；人工區重產保留）；
  ③ ps_html 產 View 軌 prob-spec.html（1.4 md-first：只讀 prob-spec.md 的契約表格 → 總覽 KPI、RTP 對 golden／目標、驗收守門、符號命中熱度、
  輪帶組理論 vs 實測、參數表色階、流程圖、輪帶帶面；xlsx／qt／手寫 md 三種模式同一套 View，沒有 xlsx 也能出完整報告）；
  ④ ps_lint 守門（數字不可回溯就擋；PS-HTML-EMPTY 空殼守門）；⑤ ps_diff 規格 xlsx ⇄ 快測設定檔逐鍵對照；⑥ ps_xlsx 第三 View 軌 Excel（機率表／審核簿／檢核表）。
  使用此 skill 當提及：機率規格書、prob-spec、機率表 xlsx 轉網頁／md、md 轉機率規格書網頁、手寫機率規格書、沒有 xlsx 的機率規格書、
  參數表、隱性規則、規格書公版六段、快測結果回填規格書、RTP 對 golden、規格和設定檔對不對、ps_lint、config-diff、K 卡對應表、
  機率表 Excel、審核簿、版本對照表、偏差檢核表、檢核表。
  不適用於：跑 Go 快測／odds.json 骨架／三向 verdict（→ ark-game-quicktest）、遊戲規格書／gdd-pack／競品影片分析（→ ark-game-spec）、
  機率架構設計與 K 卡取捨本身（人／agent 的判斷，本 skill 只組不寫）、一般 HTML 報告（→ ark-html-report）、決議 Open Questions（→ ark-grill-me）。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "1.4.3"
  updated: 2026-10-19
  outputs:
    - { format: data, audience: ai }
    - { format: md, audience: both }
    - { format: html, audience: human }
    - { format: office, audience: human }
  render: html
  depends_on: [ark-game-quicktest, ark-game-spec, ark-md-report]
---

# ark-game-prob — 機率規格書：xlsx → md → html ⇄ 設定檔，md 是唯一的 View 來源

一句話：**機率表是機率人員的工作面，規格書是三方的對話面，設定檔是引擎的輸入面**——本 skill 讓三者同一份數字、
互相可驗（sha 戳記 + 逐鍵 diff），人只寫「簡述、設計目的、手法對應」這些判斷，不搬數字。

> 製程位置：ark-game-spec（A/B 段：競品 → 遊戲規格書 gdd-pack，產 config-spec value=null）→ **ark-game-prob（C1：機率規格書）**
> ⇄ ark-game-quicktest（C2：Go 快測，產 rtp-report）。快測結果回填規格書（§2 數據資料）形成閉環（P-000）。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `openpyxl` | ps_extract / ps_probtable / ps_lint 的 xlsx 戳記 | exit 8 |
| `pyyaml` | ps_probspec（qt 模式）/ ps_diff（map）| exit 8 |
| ark-game-quicktest 產物（`data/quicktest/<slug>/`）| qt 模式 | 只能走 xlsx 模式 |
| 瀏覽器 | prob-spec.html 的 mermaid 流程圖（CDN）| 離線時流程圖顯示原始碼，其餘不受影響 |

全部 stdlib + 上述兩個套件；不呼叫 LLM；同輸入重產 bit-identical（人工區除外）。

## 資產地圖（先讀這張表再動工）

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/ps_run.py` | 一鍵：`--xlsx` → extract → probspec → html → lint [→ diff]；`--qt` → probspec → html → lint；**`--md <prob-spec.md>`（1.4）→ mdmeta → html → lint**（沒有 xlsx / 快測也能出 View）| 平常只跑這支 |
| `scripts/ps_extract.py` | 公版機率表 xlsx → `prob-data.json`：參數表以「表 X-n」標籤為錨 generic 切表 + recognizer（表M-1 輪帶組 / F-1 權重表 / SC·SS 雙欄 / 是否表 / 組別×欄矩陣 / 橫向序列 / 單值）；數據資料 FastTest 報表逐段解析；Strip 區塊 | 拿到機率表 xlsx |
| `scripts/ps_probspec.py` | Content 軌：`--data`（xlsx 模式，轉呼叫 `ps_probspec_xlsx.py`）或 `--qt`（qt 模式）→ `prob-spec.md` + `prob-spec.meta.json`；人工區 `<!-- human:id -->` 重產保留 | 要規格書 |
| `scripts/ps_html.py` | View 軌（**md-first**）：`--dir` 或 `--md` → 只讀 `prob-spec.md` 的契約表格（`ps_mdview` 分類：summary / base / symhit / reelsets / weights / dual / yesno / matrix / series / kv / paytable / odds / strip_counts / …）→ `prob-spec.html`（戳記 content-src）；prob-data.json 只拿 raw_log 摺疊區；任一表渲染失敗退回通用表；`--body-only` 給發佈端 | 要給人看；三種模式都走這支 |
| `scripts/ps_mdview.py` | md → 文件模型（frontmatter / 章節 / 表格 / 人工區 / ```strip 帶面）+ `classify()` 表型分類 + `summary_of()`（快測摘要 → KPI；舊 md 無摘要表時從 BASE INFO 回推）| 改渲染或新增表型 |
| `scripts/ps_mdblocks.py` | 兩種產生模式共用的契約表格 writer：快測摘要、符號命中、輪帶組 RTP、贏分分布、FG 詳細、§4 辨識區塊（輪帶組 / 權重 / 雙欄 / 是否 / 矩陣 / 序列 / 單值）、輪帶 Strip 附錄；每個數字經 dv() 登記派生值 | 改 md 輸出格式 |
| `scripts/ps_mdmeta.py` | md 模式：手寫 `prob-spec.md` → `prob-spec.meta.json`（mode: md、sections、pending、frontmatter sources 的 sha）| `ps_run --md` 自動呼叫 |
| `scripts/ps_lint.py` | PS-SECTIONS / PS-NUM（md 模式降 warning；```strip 帶面不算數字）/ PS-PROV / PS-STALE / **PS-HTML-EMPTY**（去標籤純文字命中六段標題 < 4 判空殼 error、< 6 warn）/ PS-HUMAN / PS-INJECT → `lint-report.json`；error exit 3 | 任何人手改 md 後必跑 |
| `scripts/ps_diff.py` | `prob-data.json` ⇄ 設定檔 JSON 逐鍵對照（map：`references/config-map.fasttest.yaml`）→ `config-diff.md/.json`；不一致 exit 3（`--warn-only` 降 0）| 跑快測前、或規格 / 設定檔任一改了 |
| `scripts/ps_layout.py` | 一款遊戲的產出佈局守門：讀 `--game` 遊戲目錄（`output/games/<slug>` 或已畢業的 `data/slot/<slug>`）的 `{analysis,spec,prob,quicktest,server,docs}/` 實檔比 sha / 數字 → `layout-report.json`（`--write-md` 重寫 LAYOUT.md）；規則 L-DIRS / L-STRAY / L-PROB / L-STAMP / L-SPEC / L-QT / L-DIFF / L-SIZE（擋 exe、>500KB、多設定檔）/ L-SERVER（handoff sha 對帳）/ L-REVIEW（契約 v3.3 拍板包 review/ 另計 5 MB、禁二進位影片、清冊過期）/ L-RTP；`--mode restore\|design`；error exit 3 | 畢業前（進 `data/` 前）|
| `scripts/ps_probtable.py` | qt 模式來源 → 公版 `prob-spec.xlsx`（COUNTIF 活公式、`_meta` 戳記）| 要給機率同仁 Excel 版（xlsx 模式本身就是公版表，免跑）|
| `scripts/ps_common.py` | envelope / sha16 / yaml / atomic_write / `resolve_out`（G-2 落點）/ `slug_of` | 被所有腳本 import |
| `references/prob-spec-contract.md` | 六段契約、frontmatter、meta.json、人工區、prob-data.json schema、戳記規則、xlsx / qt / md 模式差異、**§表格契約**（表頭 → 表型 → 元件）| 改任何腳本或手寫規格書前 |
| `references/xlsx-layout.md` | 公版機率表的讀取約定：分頁名候選、標籤錨、表頭 / caption 判定、數據資料段落、Strip 區塊、已知陷阱 | 新遊戲 xlsx 抽不出來時 |
| `references/view-contract.md` | HTML 頁面章節、表格 → 元件對照、token 契約（ark-html-report 同名變數）、戳記、無外連原則 | 改 ps_html / 換風格 |
| `references/xlsx-build-rules.md`、`references/checks/*.yaml` | ps_xlsx 第三 View 軌（Excel）建表規則與檢核表 YAML 規格 | 跑 ps_xlsx / 新增檢核表 |
| `references/kcard-mapping.md` | 機制 → K 卡對照指引、隱性規則「設計目的」寫法、彌勒佛範例 | 填 §5 / §6 人工區 |
| `references/config-map.fasttest.yaml` | ps_diff 對照規則（FastTest 參數外部化 ProbSetting 鍵名）；換遊戲複製改表編號 / 鍵名 | 跑 ps_diff |
| `assets/view.css` | View 軌樣式（light / dark token）| ps_html 預設載入 |
| `assets/prob-spec.template.md` | md 模式範本：六段 + 每種契約表頭各一例 + 人工區 + ```strip 帶面（照表頭寫就有完整 View）| 沒有 xlsx 也沒有 qt 時 |
| `assets/server-handoff.template.md` | ⑥ Game Server 交付單樣板：設定檔 / rtp-report sha、prob-spec 版本、K 卡 → Go 映射注意、上線對帳欄位（L-SERVER 比對本單 sha）| 交付工程端上線時 |
| `scripts/tests/` | `test_ps_pipeline.py`（合成迷你 xlsx → 全鏈 → lint PASS / 竄改擋下 / diff 抓不一致 / 人工區保留 / CLI --help）、`test_ps_probspec_qt.py`（qt 模式六段 / null → 待決議 / STALE）、`test_ps_mdview.py`（22 種表頭分類、md 模式一鍵、三種模式同一套 View、壞表不炸頁）、`test_game_root.py`（G-2 落點優先序）| 改腳本後 `python -m pytest -q scripts/tests` |

## 決策樹

```
手上有什麼？
├─ 機率人員的公版「機率表 xlsx」（已上線還原 / 機率人員已做好表）→ xlsx 模式
│   python scripts/ps_run.py --xlsx <機率表.xlsx> --slug <slug> --game <名> [--config <設定檔.json>]
│   ├─ ps_extract 抓不到某張表 → 看 prob-data.json params.blocks 是否有該區塊；沒有 → xlsx 標籤不是「表 X-n」格式，
│   │     照 references/xlsx-layout.md 補標籤，或先用 generic 表（View 會照原樣列出，只是沒有長條 / 色階）
│   ├─ ps_lint PS-NUM → 不要改文，回 xlsx 改（文中數字只能來自 xlsx / 派生值）
│   ├─ ps_diff 🔴 → 規格與設定檔不一致：找機率人員 + 工程師裁定哪邊對，改完重跑；這是跑快測前的硬門
│   └─ 機率人員只動人工區：summary / flow-notes / param-notes / competitor / hidden-rules（重產保留）
├─ 走 ark-game-spec → ark-game-quicktest 的新遊戲設計鏈（有 data/quicktest/<slug>/）→ qt 模式
│   python scripts/ps_run.py --qt data/slot/<slug>/quicktest [--xlsx-view]
│   ├─ 參數 null → §4 顯示「待決議」（P-002），frontmatter pending_params > 0；不是錯，是還沒決議
│   └─ 還沒快測 → §2 整表「—」標未快測；qt_run 跑完重產，§2 自動填入
├─ 兩者都沒有（設計局 / 競品反解 / 只有 Go 報表）→ md 模式：複製 assets/prob-spec.template.md，表頭照範本命名
│   python scripts/ps_run.py --md <prob-spec.md> --dest data/slot/<slug>/prob     → 同一套 html（KPI / 長條 / 色階 / 帶面）+ lint
│   ├─ PS-NUM 只警告：手寫數字請在「來源」欄標出處（決議 D-id / 規格書章節 / 設定檔鍵）
│   └─ 之後拿到 xlsx 或快測 → 改跑 xlsx / qt 模式重產；人工區保留
└─ 快測結果出來要回填 → 把報表貼回 xlsx「數據資料」分頁（xlsx 模式）或 qt_report 產 rtp-report（qt 模式）→ 重跑 ps_run
```

## 目錄

落點（1.3，G-2）：`--dest` > `--out`（`<out>/<slug>`）> 環境變數 `ARK_GAME_ROOT`（`<root>/<slug>/prob/`）> 舊預設 `data/prob/<slug>/`（相容一版）。
`--qt` 指到 `<game>/quicktest` 時 slug 取上一層名。下面以舊預設示意，檔案組成相同。

```text
data/prob/<slug>/
├── prob-data.json        xlsx 模式中繼層（參數區塊 / 辨識結果 known / 快測報表 report / 輪帶 strips / 原始 log）
├── prob-spec.md          Content 軌：frontmatter（kind: prob-spec, mode, verdict, pending_params, sources）+ 六段 + 邊界聲明
├── prob-spec.meta.json   sources{path, sha256_16} / derived[{value, from}]（PS-NUM 允許集）/ md_sha256_16
├── prob-spec.html        View 軌（頁首 <!-- content-src: prob-spec.md sha256:… -->）
├── prob-spec.xlsx        （qt 模式選配）公版表，隱藏分頁 _meta 戳記
├── config-diff.md/.json  （有 --config 時）規格 ⇄ 設定檔對照
└── lint-report.json
```

## 守門

| 規則 | 條件 | 嚴重度 |
|------|------|--------|
| PS-SECTIONS | 六段齊全、順序固定 | error |
| PS-NUM | 人工區外每個數字 ∈ 來源檔（JSON 走結構化值；xlsx 等二進位只驗 sha）∪ meta.derived；sha / id 類不算數字 | error |
| PS-PROV | §4 有值必有來源；標待決議卻帶來源 | error / warn |
| PS-STALE | 來源 sha 變了未重產；html 戳記 ≠ md sha；xlsx `_meta` 戳記不符 | error |
| PS-HUMAN | 人工區含數字（不受保護，請標來源）| warn |
| PS-INJECT | 指令覆寫句型 / 零寬字元 | error |
| ps_diff | map 任一規則 mismatch | exit 3（`--warn-only` 僅報告）|
| ps_layout | L-* 任一 error（restore 模式缺可解析的 config.json → L-SPEC error，屬遊戲未做參數外部化，非 skill 壞）| exit 3（`--strict` 時 warning 也算）|
| L-SIZE | 遊戲目錄進二進位（exe/dll/bin）或多版本設定檔 → error；單檔 > 500 KB（排除 html）→ warning | ps_layout 子規則 |
| L-SERVER | `server/handoff.md` 宣告的 config / rtp-report sha ≠ 現檔 → error（只對帳不改 server code）| ps_layout 子規則 |
| L-REVIEW | `review/` 拍板包總量 > 5 MB 或含二進位／影片 → error；缺 index.html、review-manifest 列的檔過期 → warning；review 內 HTML 不觸發 L-SIZE 500 KB（1.4.3）| ps_layout 子規則 |

## 邊界

- **只組不寫**：簡述、設計目的、競品評語、K 卡取捨是機率人員（人或 agent）在人工區寫；腳本只搬來源、算派生值。
- **不決定數值、不跑快測**：數值來自 xlsx（定案）或 odds.json（決議 / null）；快測與三向 verdict 在 ark-game-quicktest。
- **xlsx 是機率人員的工作面，不替人改**：樣板殘留分頁（如彌勒佛 v3 的「規格簡述」是 5×5 寶箱範本）會原樣列出並提醒，由人回填。
- **三種來源一套契約**：xlsx / qt / md 模式產同一份六段 md 與 meta；差別只在 frontmatter `mode` 與來源鍵；md 模式沒有派生值表，PS-NUM 降為警告。
- **View 只讀 prob-spec.md**（1.4 md-first）：數字、表格、文字都從 Content 軌的契約表格來；三種模式同一套 html；qt 模式不再經 prob-data adapter（1.3 的 ps_qtdata 已移除，單位錯置的根因）；不要為了好看在 HTML 手填任何東西。
- **mermaid 用 CDN**：單檔 html 唯二外連是 Google Fonts 與 mermaid；離線看得到原始碼。
- **ps_diff 的 map 是遊戲專屬**：表編號與設定檔鍵名跟著遊戲走；FastTest 參數外部化版以 `config-map.fasttest.yaml` 為起點。
