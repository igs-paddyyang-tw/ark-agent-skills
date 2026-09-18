---
name: ark-game-atlas
description: |
  圖文遊戲規格書（atlas）編譯器：把「競品影片 → 遊戲規格」鏈的一個 run 編成一本可翻閱的書——
  文字逐條來自 `game-spec.v1.md` 帶 provenance 的主張（OBSERVED / INFERRED / DECIDED / UNKNOWN 彩色標記），
  圖逐張來自 `evidence.jsonl` 指向的關鍵幀（單幀、時序條 strip、狀態機各 state 縮圖，燒時間碼與 evidence 編號），
  章節骨架與風格 token 由 ark-game-domains pack 的 `atlas/` 決定（slot 暗金 / fish 深海 / fast 霓虹）。
  deterministic：不呼叫 LLM、同 run 重編 bit-identical；atlas_lint 守「書裡沒有 spec 沒有的數字、沒有 evidence 沒有的圖」；
  單檔 HTML（圖可 inline）、雙軌戳記、登錄 library/atlas/catalog.json 供圖書館上架；distribution 一律 internal。
  使用此 skill 當使用者或 agent 提及：遊戲說明書、圖文規格書、競品規格書、把 spec 做成書 / 網頁書、
  遊戲 atlas、看得懂的競品分析、給主管翻的版本、把關鍵幀和規格放在一起、competitor atlas、遊戲圖鑑。
  不適用於：教學用電子書 / 新人手冊 / onboarding 教材（→ ark-book，不同文體）、產規格本身（→ ark-game-spec）、
  影片抽幀（→ ark-video-understanding）、單頁分析報告（→ ark-html-report）、章節骨架與風格的定義（→ ark-game-domains atlas/）。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "1.0.0"
  updated: 2026-09-18
  outputs:
    - { format: md, audience: ai }
    - { format: html, audience: human }
    - { format: data, audience: ai }
  render: html
  depends_on: [ark-game-domains, ark-game-spec, ark-video-understanding]
---

# ark-game-atlas — 一個 run，一本圖文規格書

與 ark-book 的分工：ark-book 教人「怎麼做」（教學文體，七段、有誤解有動手做）；**atlas 告訴人「這款遊戲是什麼」**（參考文體，五段、每個數字可回溯、每張圖是證據）。兩者共用圖書館的 token 契約，各自一個 catalog。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `pyyaml`、`Pillow` | 全部 / figures | exit 8 |
| ark-game-domains | 章節骨架 `atlas/`、風格、figure 規則 | exit 8；run 的 pack 快照沒有 `atlas` 區塊時自動以現行 pack 補（`atlas_pack_snapshot_stale: true`） |
| 已完成 decide 的 run | `game-spec.v1.md` | `--from draft` 可編草稿版（水印、status 鎖 draft） |
| `wkhtmltoimage` / 瀏覧器 | 選配，預覽 | 不影響產出 |

## 資產地圖

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/atlas_run.py` | **一鍵**：compile → lint → build → register | 預設入口 |
| `scripts/atlas_compile.py` | run → `atlas/<slug>/`（atlas.yaml、00-preface、NN-章節、sources/ 唯讀複本、呼叫 figures） | — |
| `scripts/atlas_figures.py` | keyframes → `assets/figures/Fnnn.jpg` + `figures.json`（hero / frame / strip / state_frame） | 由 compile 呼叫；單獨重產圖 |
| `scripts/atlas_lint.py` | 10 條規則，error → exit 3；輸出 `lint-report.json` | **任何人手改章節後必跑** |
| `scripts/atlas_build.py` | → `site/index.html`；`--assets auto\|inline\|linked`；`--check` 驗雙軌戳記 | — |
| `scripts/atlas_register.py` | → `library/atlas/{catalog.json,catalog.md,log.md}`；published 需 lint PASS + pair OK | — |
| `references/atlas-contract.md` | atlas.yaml / 章節 / figures.json / catalog 契約 | 改 compile 或接圖書館時 |
| `assets/default-style.yaml` | pack 無 style 時的預設 token | — |
| `scripts/tests/test_atlas.py` | deterministic、lint 反證、STALE、register gate | 改腳本後 |

## 決策樹

```
有一個 run
├─ 已 decide（有 game-spec.v1.md）→ python scripts/atlas_run.py --run <run> --slug <game> --out atlas --library library/atlas
├─ 只到 draft → 同上加 --from draft（書鎖 draft、封面水印；給企畫看「還缺什麼」用）
├─ 想換版面風格 → 改 pack 的 atlas/style.yaml（token），不改引擎；圖書館統一主題改外層 :root
├─ 圖挑得不對（strip 缺段、封面選錯）→ 改 pack 的 atlas/figures.yaml（label 序列 / prefer），重跑 compile
├─ 章節想拆併 → 改 pack 的 atlas/outline.yaml（sections 映射、insert_after），pack_lint 綠後重跑
├─ lint 紅 → 讀 lint-report.json；原則：修 compile / pack / 上游 spec，不手改章節繞 lint
├─ run 有新決議或新影片 → 重跑 atlas_run（同 slug = 更新；atlas.yaml.version 手動 +1）
└─ 書要給人 → site/index.html（inline 模式單檔可寄）；linked 模式需連同 site/assets/
```

## atlas 目錄

```text
atlas/<slug>/
├── atlas.yaml               genre: atlas · game{domain, run_id, video_sha256, spec_sha256, evidence_sha256, decisions, open_questions}
│                            · distribution: internal · cover.image · style · shelf: games/<domain> · tags · chapters[]
├── 00-preface.md            這是什麼遊戲（hero 圖）/ 這本書怎麼讀（provenance 圖例）/ 來源與版本 / 全書地圖
├── 01-at-a-glance.md …      五段：一句話 / 畫面 / 規則 / 未知與決議 / 相關機制
├── NN-evidence-index.md     全部 figure 縮圖牆 + 對照表
├── NN-glossary.md           claim key 中文對照、實體清單、KB 命中頁
├── assets/figures/Fnnn.jpg  燒 `E012 · 00:01:23.750 · reel_stop`
├── figures.json             每圖 evidence / 時間碼 / 來源幀 sha / ops / sha256
├── sources/                 唯讀：spec、evidence.jsonl、game-analysis、kb-refs、decisions、entities、run-manifest
├── lint-report.json
└── site/index.html          build 產物，不手改（inline 模式含全部圖）
```

## lint 規則（都是 deterministic）

| 規則 | 意思 |
|------|------|
| ATL-SECTIONS | 一般章五段齊全順序正確；序四段 |
| ATL-ONELINE | 「一句話」不得含數字 |
| ATL-FIGURE | 「畫面」段 ≥1 figure 或固定句「影片未拍到本章對應畫面。」；figure 在 figures.json、檔案存在、evidence 存在 |
| ATL-NUM | **全書每個數字必須能在 sources 的 spec bullet 找到**（E/Q/D/F/GKB id、時間碼、run_id、版本號例外） |
| ATL-NAME | 反引號名稱 ⊆ spec claim key / entity id / GKB / E / Q / D / F / 章節 id |
| ATL-PROV | 「規則」段每條 bullet 以 provenance 標記開頭 |
| ATL-STALE | atlas.yaml 記的 spec / evidence sha 與 sources 現況一致 |
| ATL-CHAPTERS / ATL-YAML / ATL-INJECT | 目錄一致、契約欄位、無指令覆寫句型與隱形字元 |

## 圖書館契約

`library/atlas/catalog.json`：`{catalog_version, kind: atlas, shelves[], books[{kind, slug, title, status, distribution, shelf, tags, game{domain, run_id, …}, cover, style, chapters[], figures, paths{site, sources, figures_json}, lint, pair}]}`。
與 ark-book 的 `library/catalog.json` 平行；圖書館網站讀兩份、以 `kind` 分區。同 domain 的書章節骨架相同（來自 pack），網站可用多本書的 `sources/game-analysis.yaml` 直接拉「機制 × 遊戲」比較矩陣，不需解析章節。

## 邊界

- 不畫框、不標物件：observations 沒有座標；要框選需先在 ark-game-analysis 的 observe 契約加 bbox。
- 不潤稿：文字逐條繼承 spec；若未來加 LLM 潤稿，守門要跟 ATL-NUM 同一判準（潤稿後數字集合 ⊆ 來源）。
- 競品畫面只准內部：`distribution: internal` 貫穿 atlas.yaml → catalog → 頁尾水印；不做分享功能。
- 一本書目前綁一個 run；同款遊戲多支影片的合併（`game.runs[]`）為下一版。
