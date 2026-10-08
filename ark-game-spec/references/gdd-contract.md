# gdd-pack 契約 v1

一款遊戲一包；所有檔案 UTF-8；路徑相對 `gdd.yaml`。任何欄位新增先改本文再改 lint。

## gdd.yaml

```yaml
contract: "1"
slug: kaiji-golden-hoyeah         # kebab-case，唯一
title / short_title / subtitle
domain: slot-game                 # ark-game-domains pack id
status: draft | review | published
distribution: internal            # 固定；lint 擋其他值
assets: {root: assets, symbols: symbols, screens: illustrations, reference: spec-reference-images}   # root 相對 gdd.yaml
#   三夾名省略時：預設英文定版名（gdd_common.ASSET_DIRS）；只有舊中文夾（圖騰/全示意圖/規格書競品圖）時自動相容並警告 GDD-ASSET-LEGACY
#   golden case 直接指樣板：root: ../../data/references/kaiji-gdd-sample（依 pack 實際位置調整相對層數）
spec: [{k, v, short?, short_k?, kv?: false}]   # short 有值 → 進首頁 spec 列（標籤用 short_k 或 k）；kv:false → 不進「遊戲規格」kv 表
spec_note / symbols_note / map_note / info_note / i18n_note   # 各段 note（symbols_note 允許 <code>）
symbols_internal_notes: [..]      # 只進 HTML 註解
symbol_groups: [{id, title, note?}]            # 圖騰牆分組，順序即頁面順序
odds_order: [M1, M2, …]           # INFO 頁賠率表順序（code）
features: [{id, title, rules?, screens_title?, screens_note?}]   # 一玩法一章；win = 階段性面板；common = 共用素材（只有 todo 卡）
i18n_columns: [{id, label}]       # 必與 i18n.csv 表頭一致
lint: {missing_symbol_file: warn}   # 選用：符號 file 為 null 時降 warn（from_spec 草稿用）
extract: {…}                         # 選用：gdd_extract / gdd_from_spec 寫入的來源資訊（xlsx sha、run_id、claims 對應、skipped）
open_questions: [{q, key, section}]  # 選用：from_spec 帶入的 spec UNKNOWN，進 todo.md
build: {output: 素材總覽.html, style?: <style.yaml>, lang_policy?: 文字說明}
```

## rules/*.md 錨點

`<!-- spec:<section_id> <spec sha16> -->` 或 `<!-- xlsx:<sheet> -->`：標示該段落逐條繼承自哪個來源；mini-markdown 原樣輸出到 HTML，不顯示。

## symbols.yaml

```yaml
contract: "1"
symbols:
  - code: M1                # 顯示代號；role=symbol 者唯一
    group: normal           # ∈ gdd.symbol_groups.id
    sym_id: 11 | null       # Symbol_ID 分頁；role=symbol 者唯一
    name: 星星
    file: Kaiji_MG_Symbol001.png   # assets.symbols 內實際檔（工程命名）
    soft: true              # false → 顯示「無（表演示意）」
    art_name: シンボル_星.png       # 美術原檔名（資訊用）
    updated: true|false     # 較新版標記
    role: symbol | performance     # performance = 表演示意，不進命名字典、可與 symbol 同 code
    ref: 皇帝牌             # 規格書參考描述
    ref_files: [M1_原.png, M1_參考.png]   # assets.reference 內的檔；只當參考，不得放進 file
    odds: [250, 60, 20]     # 5/4/3 連線；normal 組必填；恰 3 個整數
    scene: 主遊戲
    color: red|blue|green|purple  # 名稱前色點（對到 style token --<color>）
    flag: 表演示意          # 顯示為 guess tag；lint warn
    desc: …
```

## screens.yaml

```yaml
contract: "1"
screens:
  - feature: main           # ∈ gdd.features.id
    step: "1"               # 流程序號（字串；共用素材用 "—"）
    title: 主遊戲待機畫面
    file: 示意圖2.png | null # assets.screens 內的檔；null = 待補
    from: 流程分鏡 B4        # file 為 null 時必填
    lang: 英文 | 日文 | 繁中 | 只有日文
    issue: 面板顏色待修正    # 待美術修正；lint warn，進 todo
    desc: …
```

## rules/<feature>.md（mini-markdown 子集）

`### 標題`、`- 清單`（`**粗體**`、`` `code` ``）、`| 表格 |`（第二列為分隔列，欄數必須一致）、`> note`、一般段落。不支援巢狀、圖片、連結。

## info.yaml

```yaml
contract: "1"
langs: [{id: tw, label: 繁中}, {id: en, label: English}, {id: jp, label: 日本語}]
default_lang: tw
placeholders: {SC藍圖: SC藍, 金幣圖: Coin, …}   # {佔位符} → symbols.code（role=symbol）
blocks:
  - {t: h, en: ODDS TABLE, tw: 賠率表, jp: 配当表, widget: odds_grid}   # widget 在標題後插賠率牆
  - {t: p, id: info-17, en: …, tw: …, jp: …}                          # id 供 slots 錨定
slots:
  - {after: info-17, items: [{label: 免費遊戲圖（3×5）, file: xxx.png}, {label: 待補圖, file: null}]}
```
`t`：h 大標 / s 小標 / p 段落。缺語系時 fallback 到 en。

## i18n.csv

表頭 = `gdd.i18n_columns[].id`；每列欄數一致；空字串顯示為 —。佔位符允許圖騰型（在 placeholders）與數字型（`{25}`、`{000,000,000}`）。

## HTML 戳記

`<!-- gdd-src: gdd.yaml:<sha16> symbols.yaml:<sha16> screens.yaml:<sha16> info.yaml:<sha16> i18n.csv:<sha16> rules/<f>.md:<sha16> … -->`
`gdd_build --check`：任一不符 → STALE（exit 3）。無時間戳，同 pack 重編 bit-identical。

## lint 規則

見 SKILL.md「lint 規則」表；error 阻擋 build，warn 全部進 `todo.md`。

## 交付夾（gdd_export，2.1）

企劃樣板的交付形態是「一個 HTML + 三個圖夾」放同一層（`data/references/kaiji-gdd-sample` 定版）。`gdd_export.py`（或 `gdd_run --export`、`gs_run --stage gdd --export`）把 pack 編成同結構：

```text
<out>/                               預設 <pack>/export/
├── <short_title>_素材總覽.html       檔名可用 gdd.yaml.build.bundle_html 覆寫；<title> = "{short_title} 素材總覽"
├── symbols/                          symbols.yaml 的 file
├── illustrations/                    screens.yaml 的 file ＋ info.yaml slots 的 file
└── spec-reference-images/            symbols.yaml 的 ref_files
```

| 規則 | 內容 |
|---|---|
| 夾名 | 一律英文三夾，與來源 pack 用中文或英文無關；三夾即使空也建立 |
| 複製範圍 | 預設只帶「HTML 有引用」的圖；`--all-assets` 連同來源三夾未引用的圖一起帶（重現原樣板夾）|
| 連結 | HTML 內 img / href 與燈箱 gallery 的 src 一律是 `symbols/…`、`illustrations/…`、`spec-reference-images/…` 相對路徑（不含 `assets/` 或 assets.root）|
| 守門 | 任一連結在交付夾找不到，或指向三夾以外 → exit 3（GATE_BLOCKED）；來源缺圖列在 manifest |
| 交付夾內容 | 只有 HTML 與三夾，不放 yaml / json；核對清單寫回 pack 的 `export-manifest.json`（copied / counts / missing_sources / broken_links / extra_top_level / source_stamp / legacy_source_dirs）|
| 戳記 | HTML 仍帶 `gdd-src` 戳記（來源 pack 各檔 sha），可追溯是哪一版 pack 產的 |

KAIJI golden case 比對（2026-10-07）：交付夾 symbols 25 / illustrations 31 / spec-reference-images 40，全部 ⊆ 樣板夾；樣板夾多 5 張示意圖（樣板 HTML 本身也未引用）；`--all-assets` 時三夾與樣板逐檔一致。
