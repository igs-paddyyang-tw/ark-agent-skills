---
name: ark-game-gdd
description: |
  遊戲企劃文件（GDD）的兩段式工具：**從構想產文件** + **從資料層產素材總覽**。
  ① 創作模式（from-concept，純提詞）：只有一句話概念/需求時，產結構化 GDD —— 完整 10 章（概述/核心玩法/
  系統機制/關卡內容/敘事世界觀/美術/音效/技術/商業模式/開發計畫）或精簡 One Pager；先做概念萃取
  （Understanding Lock）鎖定類型/平台/受眾/USP 再展開，依 genre 側重；數值一律標「建議值待測試」。
  ② 編譯模式（gdd-pack → HTML）：把正式規格資料層 gdd-pack（gdd.yaml / symbols.yaml / screens.yaml /
  rules/*.md / info.yaml / i18n.csv + 三資產夾「圖騰 / 全示意圖 / 規格書競品圖」）deterministic 編成企劃已習慣的
  十段式單檔 HTML（遊戲規格 → 圖騰牆 → 一玩法一章「規則 + 表 + 畫面流程」→ 階段性面板 → 共用素材待補 → 名稱對照表 →
  INFO 頁三語 → 多國語系；lightbox、搜尋、點檔名複製），並吐出給美術的 todo.md（缺示意圖 / 待修 / 檔名衛生）。
  gdd_lint 守門：圖檔必存在、參考圖不得當定案、odds 恰 5/4/3 三值、待補必附來源、佔位符必可解析、無注入；
  不呼叫 LLM、同 pack 重編 bit-identical、HTML 尾端戳記可驗 STALE。
  使用此 skill 當使用者或 agent 提及：遊戲企劃、遊戲設計文件、GDD、game design document、遊戲規格書、遊戲提案、
  遊戲概念文件、寫遊戲企劃、設計遊戲、One Pager、素材總覽、企劃規格書網頁、gdd-pack、正式遊戲規格書 HTML、
  圖騰對照表、軟體命名對接、示意圖待補清單、INFO 頁文案、多國語系表、把規格書做成企劃看的版本、規格書樣板。
  不適用於：工程規格書與 ADR（→ ark-superpowers，本 skill 出的是遊戲企劃不是技術規格）、
  影片競品分析與 atlas 圖鑑（→ ark-game-analysis / ark-game-atlas）、規格主張與決議（→ ark-game-spec / ark-grill-me）、
  機率規格與快測（→ prob-architect / quicktest-runner）、xlsx 規格書抽取（本版尚未提供，見「邊界」）。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "1.2.0"
  updated: 2026-10-01
  outputs:
    - { format: data, audience: ai }
    - { format: html, audience: human }
    - { format: md, audience: both }
  render: html
  depends_on: [ark-game-spec, ark-game-analysis, ark-video-understanding]
---

# ark-game-gdd — 遊戲企劃文件：從構想產文件 ＋ 從資料層產素材總覽

本 skill 覆蓋 GDD 的兩段：**創作**（只有構想 → 結構化 GDD 文件）與**編譯**（正式 gdd-pack → 企劃 HTML 素材總覽）。

一句話：**企劃看的正式規格書是資料層的一個 view**。資料層（gdd-pack）給 AI 與工程對接，HTML 給企劃/美術翻；
同一份資料日後也餵 ark-game-atlas（圖書館版）。本 skill 管兩件事：GDD 文件的創作，與 gdd-pack 的契約、守門與渲染。

## 模式一：創作（from-concept）— 只有構想，還沒有 gdd-pack

> 純提詞模式（無腳本）：從一句話概念/需求/參考遊戲，產出結構化 GDD 文件。
> 用於「連 pack 都還沒有」的最前期；產出的文件可作為日後建 gdd-pack 的依據。

**步驟 1 概念萃取（Understanding Lock）**：先從輸入提取/推導核心要素，確認後才展開（避免產空泛 GDD）——
遊戲名稱（暫定）、類型 Genre 與子類型、目標平台、目標受眾、核心賣點 USP、一句話概念 Elevator Pitch。
輸入過於模糊（如「幫我設計一個遊戲」）時引導補類型與核心玩法，不直接產空殼。

**步驟 2 章節展開**（展開前讀 `references/concept-gdd-template.md` 取章節模板、`references/genre-guides.md` 查該類型側重）：
- **full（完整 GDD，預設）** 10 章：概述 / 核心玩法 / 系統機制 / 關卡與內容 / 敘事與世界觀 / 美術 / 音效 / 技術規格 / 營運與商業模式 / 開發計畫
- **onepager（精簡）** 7 區塊：快速提案 / 早期構想用

**步驟 3 數值填充**：系統機制給具體數值範例（屬性表/道具表/經濟產出率用表格），**全標「建議值，需經實際測試調整」**；
博弈類額外給 RTP / 賠率表 / 中獎機率。

**步驟 4 產出**：Markdown，`docs/<遊戲名稱>-gdd.md`（full）或 `-onepager.md`；文末標產出戳記 + 「數值平衡需經實測調整」。

產出要求：`##` 章節、表格優先、每章有實質內容不空殼、繁中（術語保留英文如 Core Loop / RTP / DPS）。
創作模式的詳細章節模板見 `references/concept-gdd-template.md`，範例見 `references/concept-example/`。

## 模式二：編譯（gdd-pack → 素材總覽 HTML）


## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `pyyaml`、`jinja2` | 全部 | exit 8 |
| 三個資產夾（`assets.root` 下的 圖騰 / 全示意圖 / 規格書競品圖） | lint / build | exit 3（GDD-YAML） |
| ark-game-spec 的 `game-spec.v1.md` | 選配，`gdd_from_spec`（下一版） | 目前以手寫 yaml 為入口 |

## 資產地圖

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/gdd_extract.py` | **規格書 xlsx → gdd-pack 草稿**：分頁分類器 → `extract-map.yaml`（可手改）→ 抽 spec / odds / 圖騰 / 玩法 md / 介面圖 / INFO / 多國 + 內嵌圖進 assets/ → `extract-report.md` | 有規格書 xlsx 時的入口 |
| `scripts/gdd_from_spec.py` | **A 段 run → gdd-pack 草稿**：spec 章節逐條繼承進 rules/*.md（`<!-- spec:<section> sha16 -->` 錨點）、claims 換算 spec kv、entities → 無圖符號骨架、keyframes → 示意圖、UNKNOWN → todo 待決問題 | 影片分析完、想給企劃看規格草稿時 |
| `scripts/gdd_run.py` | **一鍵**：lint → build（lint 有 error 不產 HTML） | 預設入口 |
| `scripts/gdd_lint.py` | 守門 8 組規則 → `lint-report.json`；error exit 3，warn 進 todo | 改任何 yaml/md 後必跑 |
| `scripts/gdd_build.py` | → `素材總覽.html`（linked 模式，圖以相對路徑指向資產夾）+ `todo.md`；`--check` 驗戳記 | — |
| `scripts/gdd_common.py` | 契約常數、pack 載入、mini-markdown（rules 用） | 不直接執行 |
| `assets/template.html.j2` | 十段版面 + lightbox + 搜尋（從企劃樣板抽出，資料全換成變數） | 改版面時 |
| `assets/default-style.yaml` | 風格 token（企劃樣板暗棕金；換檔即換膚，不改元件 CSS） | 換風格時 |
| `references/concept-gdd-template.md` | **模式一**：完整 GDD 10 章節模板 + One Pager 模板 | 創作模式步驟 2 展開章節前 |
| `references/genre-guides.md` | **模式一**：遊戲類型的章節側重指南 | 創作模式步驟 2 確認類型後 |
| `references/concept-example/` | **模式一**：GDD 創作範例（zombie-fishing-machine） | 想看創作模式產出長相時 |
| `references/gdd-contract.md` | gdd-pack 六個檔的欄位契約 + lint 規則 | 建新 pack、改 lint 時 |
| `references/template-anatomy.md` | 企劃樣板（gdd-sample）拆解：8 個 JS 資料結構怎麼對到契約、刻意改掉的地方 | 想知道「為什麼長這樣」時 |
| `scripts/tests/test_gdd.py` | lint 規則（含真實瑕疵）、deterministic、STALE、佔位符/slot、注入 | 改腳本後 |

## 決策樹

```
要產遊戲企劃文件（GDD）
├─ 只有構想/一句話概念，連 gdd-pack 都還沒有 → 模式一（from-concept，純提詞）
│     ├─ 先做概念萃取 Understanding Lock（類型/平台/受眾/USP/Pitch），模糊就引導補
│     ├─ full（10 章，預設）或 onepager（7 區塊）；讀 concept-gdd-template.md + genre-guides.md
│     └─ 產 docs/<name>-gdd.md，數值全標「建議值待測試」
要做一款遊戲的素材總覽（已有規格資料）→ 模式二（編譯）
├─ 有規格書 xlsx → python scripts/gdd_extract.py --xlsx <規格書> --out data/gdd/<slug>
│     ├─ 先看 extract-report.md：分頁對錯改 extract-map.yaml 的 role / feature_id 重跑
│     ├─ lint 紅通常只剩兩種：圖騰缺圖（file: null）、INFO 佔位符猜不到 code → 人補，這就是「人審一眼」
│     └─ 非公版（一玩法一頁、規則靠 ❖ 條列）也吃得下，但並排儲存格會變成雜表格，rules/*.md 需人順一次
├─ 沒有 xlsx、有企劃手工 HTML → 複製 data/gdd/kaiji-golden-hoyeah/ 當骨架，改 gdd.yaml 的 assets.root 指到資產夾
│     ├─ 圖騰：一筆一個，file = 圖騰夾內工程命名檔；美術原檔名放 art_name；參考圖只放 ref_files
│     ├─ 畫面：feature × step 排序；沒圖就 file: null + from（分鏡/需求表編號）
│     ├─ 規則：rules/<feature>.md（### 標題、- 清單、| 表格 |、> note）
│     └─ INFO：blocks 三語 + placeholders（{佔位符} → 圖騰 code）+ slots（顯式 block id 錨點）
├─ 有 pack → python scripts/gdd_run.py --pack data/gdd/<slug>
│     ├─ lint FAIL → 讀 lint-report.json；修資料或資產，不繞 lint
│     └─ PASS → 素材總覽.html + todo.md（warn 全在這裡：待補、待修、檔名衛生、INFO 插圖）
├─ 企劃改了 yaml 沒重編 → gdd_build --check 回 STALE；重跑 gdd_run
├─ 要換配色 → 複製 assets/default-style.yaml 改 token，--style 指過去
└─ 要進圖書館做跨遊戲比較 → 下一版 atlas --from gdd（見邊界）
```

## gdd-pack 目錄

```text
data/gdd/<slug>/
├── gdd.yaml          機種資訊、spec 列、資產夾、symbol_groups、features（一玩法一章）、odds_order、各段 note、build
├── symbols.yaml      圖騰：code / group / sym_id / name / file / soft / art_name / updated / role / ref / ref_files / odds / scene / color / flag / desc
├── screens.yaml      畫面：feature / step / title / file|null / from / lang / issue / desc
├── rules/<f>.md      規則列 + 表格（mini-markdown）
├── info.yaml         langs / default_lang / placeholders / blocks[t,id,widget,<lang>…] / slots[after,items]
├── i18n.csv          多國語系（欄位 = gdd.i18n_columns）
├── lint-report.json  gdd_lint 產物
├── todo.md           gdd_build 產物：給美術的待補 / 待修 / 檔名衛生
└── 素材總覽.html      gdd_build 產物（build.output 可改名），勿手改
```

資產夾不在 pack 內、不複製：`assets.root` 可指到企劃現成的資料夾（golden case 指 `../../gdd-sample`，即 data/gdd-sample）。

## lint 規則（都是 deterministic）

| 規則 | error | warn |
|------|-------|------|
| GDD-YAML | 契約欄位、資產夾存在、feature/group id 唯一、distribution=internal | — |
| GDD-SYM | file 存在、group 合法、role=symbol 的 code 與 sym_id 唯一、odds 若有必為 3 整數、ref_files 存在、參考圖不當定案 | flag 標記、normal 組缺 odds |
| GDD-SCR | feature 合法、file 存在或 null+from | 待修 issue、雙副檔名 `.png.png`、泛用檔名 Snipaste_/圖層 |
| GDD-INFO | t 合法、block id 唯一、{佔位符} 皆定義且對到 role=symbol、slot 錨點存在、slot 圖存在 | slot 圖待補 |
| GDD-I18N | 表頭與 i18n_columns 一致、每列欄數一致 | 非圖騰非數字型佔位符 |
| GDD-RULES | rules 檔存在、表格欄數一致 | — |
| GDD-INJECT | script / iframe / 事件屬性 / 隱形字元 | — |

## 邊界

- **xlsx 抽取是草稿不是定稿**：91 本規格書的分頁名只有 INFO / 多國穩定，其餘各寫各的，所以分類靠同義詞 + 內容特徵，貼不上就 unknown；公版 Odds Table 與研七「M1..Mn + 程式代號」水平版型都認得，其他版型的賠率需人補；賠率為 server 值（紅字 {N}）時 odds 留空、頁面顯示 —。
- **資產配對不自動**：美術原檔名 → 圖騰代號由人（或 LLM 產草稿後人審）寫進 symbols.yaml；本 skill 只驗不猜。
- **不 inline 圖**：示意圖動輒數十 MB，一律 linked；要單檔可寄的版本走 atlas。
- **競品參考圖只准內部**：distribution 鎖 internal，頁尾標示；lint 擋參考圖進 final。
- **from_spec 是草稿不是規格**：rules 只搬 spec 的 provenance bullet（含 UNKNOWN / PROPOSED），不補字、不改寫；spec kv 只換算有 claim 的欄位（盤面 / 對獎 / Free / Feature / JP / 機種名 / 版型），其餘留給企劃；符號不取名（沿用 symbol_a）。
- **與 atlas 的分工**：本 skill 產企劃/美術/工程對接的工作文件；atlas 產主管翻、圖書館比較的參考書。同資料層、兩個 view；atlas `--from gdd` 與 `SPEC` provenance 為下一版。
