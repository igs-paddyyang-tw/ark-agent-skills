---
name: ark-game-spec
description: |
  遊戲規格書 executor（2.0 合體版）：遊戲開發製程 A+B 段「從競品／構想到正式遊戲規格書」的唯一產出 skill，
  與 ark-game-prob（機率規格書）、ark-game-quicktest（Go 快測）三件套。一個入口 gs_run --stage 串八個 stage：
  video（影片 → 抽幀 → contact sheet → 唯讀 evidence）→ detect／analyze（多模態機制分析 → game-analysis.yaml + kb-refs + 報告）
  → draft／decide／dev（規格草稿 spec_lint → ark-grill-me 決議 → game-spec.v1 → dev-spec 六檔，config-spec value=null）
  → gdd（規格書 xlsx 或 spec run → gdd-pack → 素材總覽.html + todo.md）→ atlas（圖文規格書單檔 HTML 入圖書館）→ pack（domain pack lint）。
  另含純提詞「從構想產 GDD」創作模式。只有 analyze 與 gs_review --llm 呼叫 LLM，其餘 deterministic。
  使用此 skill 當提及：遊戲規格書、規格書、GDD、遊戲企劃、素材總覽、gdd-pack、圖騰對照表、競品影片分析、拆解競品機制、
  抽幀、contact sheet、evidence、機制規格草稿、Open Questions、decisions.yaml、dev-ready spec、config-spec、state machine、
  qa checklist、圖文規格書、遊戲 atlas、遊戲圖鑑、domain pack、新增遊戲類型、answer key、POC benchmark。
  不適用於：機率規格書／參數表／隱性規則（→ ark-game-prob）、Go 快測／RTP 模擬／odds.json（→ ark-game-quicktest）、
  決議拷問流程本身（→ ark-grill-me）、教學書（→ ark-book）、單頁報告（→ ark-html-report）、工程 Spec／ADR（→ ark-superpowers）。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "2.0.0"
  updated: 2026-10-07
  outputs:
    - { format: data, audience: ai }
    - { format: md, audience: both }
    - { format: html, audience: human }
  render: html
  depends_on: [ark-grill-me, ark-md-report, ark-wiki-engine, ark-llm-tools]
---

# ark-game-spec 2.0 — 從競品／構想到正式遊戲規格書，一個 skill、八個 stage

一句話：**原本的影片理解、機制分析、1.x 規格、企劃 GDD、圖文 atlas 五個 skill，加上 domain pack 註冊庫的資料，
合成一個以「交付物」命名的 skill**——企劃說「幫我出規格書」，agent 跑的是 `gs_run --stage …`，不需要知道底下是哪一支引擎。
2.0 是「搬家不改語意」：每支 stage 腳本與既有測試原封搬入、只改 import 與路徑；共用碼收進 `_lib/`；domain pack 收進 `domains/`。

> 製程位置（P-000）：**ark-game-spec（A 競品分析 + B 正式遊戲規格書）** → ark-game-prob（C1 機率規格書）⇄ ark-game-quicktest（C2 Go 快測）。
> 交接契約：`dev-spec/config-spec.yaml`（value 一律 null，P-002）、`decisions.yaml`、`dev-spec/state-machine.md`、`kb-refs.yaml`、gdd-pack 的 `symbols.yaml.odds`。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `pyyaml`、`jinja2`、`openpyxl`、`Pillow`（`requirements.txt`）| 全部 stage | exit 8 DRIVER_MISSING |
| `numpy`、`yt-dlp`、`faster-whisper`（選配，`requirements-video.txt`）+ 系統 `ffmpeg`/`ffprobe` | video stage | 只有影片入口不能用；gdd / atlas-from-gdd / spec（既有 run）照常 |
| LLM 憑證（`ARK_LLM_PROVIDER=anthropic\|gemini\|module\|fake`、`ARK_LLM_MODEL`）| analyze、detect、`gs_review --llm` | exit 5／8；測試用 `fake` |
| ark-md-report（同層）| analyze 的 ga_report（report_lint / report_pair / register）| 報告仍產出但未經 lint，envelope 標 unverified |
| ark-wiki-engine（同層，選配）| kb_match 的 wiki_query 第三順位 | 只用 pack seed 比對 |
| ark-grill-me | draft → decide 之間的人工決議 | 無法產 decisions.yaml → dev 不放行 |

## 資產地圖（先讀這張表再動工）

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/gs_run.py` | **總編排（薄派發器）**：`--stage video\|detect\|analyze\|report\|draft\|decide\|dev\|gdd\|atlas\|pack\|all`，flag 透傳各 stage runner；`analyze` 自動補跑 ga_report（D-3）；`all` 跑到 draft 停（人工決議是刻意斷點），帶 `--decisions` 續到 atlas | 平常只用這支 |
| `scripts/video/` | `vu_run.py`（fetch → timeline → events → keyframes → sheets → transcript → evidence；`--domain auto` 只產 detect sheets）、各 `vu_*.py`、`detectors/`（8 個 deterministic 偵測器 REGISTRY）| 影片入口；調偵測器看 `references/video-calibration.md` |
| `scripts/analysis/` | `ga_detect.py`（LLM 判 domain）、`ga_run.py`（observe → analyze → validate → kb_match）、`ga_report.py`（md-report + html）、`wev_fetch.py`（網頁 evidence，type: web）| 機制分析；fake provider 跑測試 |
| `scripts/spec/` | `gs_run.py --stage draft\|decide\|dev`（舊 1.x 三段）、`gs_draft / gs_review / gs_decide / gs_dev / gs_metrics / spec_lint` | 規格草稿 → 決議 → dev-spec |
| `scripts/gdd/` | `gdd_extract.py`（規格書 xlsx → gdd-pack）、`gdd_from_spec.py`（spec run → gdd-pack）、`gdd_lint.py`、`gdd_build.py`（素材總覽.html + todo.md）、`gdd_run.py`（lint → build）、`gdd_common.py`（本 stage 自用 helper，2.1 併入 _lib）| 企劃規格書 |
| `scripts/atlas/` | `atlas_run.py`（`--run` 或 `--gdd`）、`atlas_compile / atlas_from_gdd / atlas_figures / atlas_lint / atlas_build / atlas_register` | 圖文書、圖書館上架 |
| `scripts/pack/` | `pack_resolve.py`（`--list` / `--domain`）、`pack_lint.py`（`--all`）、`pack_new.py` | 新增 / 修改 domain pack |
| `_lib/` | `run_common.py`（envelope / run / manifest / pack 載入 / evidence / spec parser / atlas / ffmpeg；四份舊 common 的超集）、`pack_common.py`、`llm_adapter.py`、`guard.py`（注入 regex 唯一一份）、`md_render.py`（content-src 戳記）| 所有 stage import |
| `domains/` | `_core` / `_template` / `slot-game` / `fish-game` / `fast-game`（原 domain pack 註冊庫原封搬入）；`ARK_GAME_DOMAINS_DIR` 可覆寫（舊 `ARK_GAME_DOMAINS_SKILL` 相容一版）| 契約見 `references/pack-contract.md` |
| `references/run-contract.md` | run 目錄、evidence、後處理守門、game-analysis / kb-refs / spec md / config-spec / benchmark 契約（自 1.x SKILL.md 原文抽出）| 改任何 stage 腳本前 |
| `references/pack-contract.md`、`gdd-contract.md`、`atlas-contract.md`、`gdd-template-anatomy.md`、`video-calibration.md` | 各 stage 契約與調參 | 對應 stage |
| `references/concept-gdd-template.md`、`genre-guides.md`、`concept-example/` | **創作模式**（純提詞）：只有一句話概念時產 10 章 GDD 或 One Pager | 沒有影片也沒有 xlsx 時 |
| `assets/` | `gdd-template.html.j2`、`gdd-default-style.yaml`（企劃暗棕金）、`atlas-default-style.yaml`（與 `domains/_core/atlas/style.yaml` 相同，2.1 刪）| gdd_build / atlas_build |
| `scripts/tests/` | 49 tests：detectors（召回 ≥ 90%、deterministic）、postprocess、report、spec_lint、gdd、atlas、atlas_gdd、packs、**gs_run_dispatch**（video → analyze → draft → decide → dev → atlas 全鏈）；需 ffmpeg 的自動 skip | 改腳本後 `python -m pytest -q scripts/tests` |

## 決策樹

```
手上有什麼？
├─ 競品影片（URL / mp4）
│   python scripts/gs_run.py --stage all --source <url|mp4> [--domain slot-game|fish-game|fast-game|auto]
│   ├─ auto → ga_detect 判 domain（≥ 0.7 才綁定）→ 續抽幀；判不出 → exit 3，手動 --domain
│   ├─ 停在 draft：看 <run>/review-report.md 的 Open Questions → ark-grill-me 決議 → <run>/decisions.yaml
│   ├─ python scripts/gs_run.py --stage decide --run <run> → --stage dev（config-spec value 一律 null；有 defer 不放行，--allow-deferred 例外）
│   └─ 要給人看：--stage atlas --run <run> --slug <slug>（圖文書）；要企劃樣板：--stage gdd --from spec --run <run> --out data/gdd/<slug>
├─ 企劃的規格書 xlsx（KAIJI 樣板）
│   python scripts/gs_run.py --stage gdd --from xlsx --xlsx <規格書.xlsx> --out data/gdd/<slug>  → 素材總覽.html + todo.md
│   └─ todo.md 給美術（缺示意圖 / 待修 / 檔名衛生）；--stage atlas --gdd data/gdd/<slug> 出圖文書
├─ 只有一句話概念 → 創作模式：讀 references/concept-gdd-template.md + genre-guides.md，Understanding Lock 後產 docs/<name>-gdd.md；數值一律「建議值待測試」
├─ 新遊戲類型（麻將 / 棋牌 / 街機）→ python scripts/pack/pack_new.py --domain <d> --display-name <名> → 填 pack → --stage pack --domain <d>
└─ 規格定案要進機率段 → 交接檔在 <run>/dev-spec/ 與 data/gdd/<slug>/：下一步 ark-game-quicktest qt_config、ark-game-prob ps_run --qt
```

## 目錄（run 為單位）

```text
artifacts/cva/<run_id>/
├── manifest.json · pack/resolved.json · video/ · transcript/ · frames/ · evidence.jsonl（唯讀）       video
├── observations.jsonl · game-analysis.yaml · entities.json · kb-refs.yaml · report/<date>-game-analysis-*.md   analysis
├── game-spec.draft.md · review-report.md/.json · decisions.template.yaml · decisions.yaml · game-spec.v1.md    spec
├── dev-spec/{game-spec, feature-spec, state-machine, ui-spec, qa-checklist}.md · config-spec.yaml · benchmark.json
data/gdd/<slug>/   gdd.yaml · symbols.yaml · screens.yaml · rules/*.md · info.yaml · i18n.csv · assets/ · 素材總覽.html · todo.md   gdd
data/atlas/<slug>/ atlas.yaml · NN-*.md · assets/figures/ · site/index.html · data/library/atlas/catalog.json                     atlas
```

## 守門

| stage | lint | 擋什麼 |
|---|---|---|
| video | 預算 hard_max（exit 9）、evidence 已存在未 --force（exit 3）| 抽幀失控、覆寫唯讀 evidence |
| analyze | `ga_analyze.postprocess`、`ga_validate`（exit 6）、`report_lint` | 未宣告 key、壞 evidence、口白撐 OBSERVED、UNKNOWN > 60% |
| spec | `spec_lint` 四分法（NUM-OUTSIDE / OBS-EVIDENCE / KB-REF / UNKNOWN-Q / DECIDED-D / NAME / SECTIONS / PACK:*）、gs_dev 三道（defer / 必填 / value≠null）| 區塊外數字、沒 evidence 的 OBSERVED、競品值偷渡成定案 |
| gdd | `gdd_lint` 7 組（YAML / SYM / SCR / INFO / I18N / RULES / INJECT）| 圖檔不存在、參考圖當定案、odds 不是 3 值、注入 |
| atlas | `atlas_lint` 10 組（含 ATL-NUM：書裡沒有 spec 沒有的數字、ATL-STALE）| 憑空數字、過期來源 |
| pack | `pack_lint` 20 餘組（PACK-ITEMS 恰 10 項、PACK-KB-TAGS 受控詞彙…）| pack 契約破壞 |

## 2.0 相對 1.x 的變更（給消費端）

| 舊 | 新 |
|---|---|
| `ark-video-understanding/scripts/vu_run.py` | `ark-game-spec/scripts/video/vu_run.py` 或 `gs_run.py --stage video` |
| `ark-game-analysis/scripts/ga_run.py`（不產 report）| `scripts/analysis/ga_run.py`；`gs_run.py --stage analyze` 會補跑 ga_report |
| `ark-game-spec/scripts/gs_run.py --stage draft` | `scripts/spec/gs_run.py --stage draft` 或 `gs_run.py --stage draft` |
| `ark-game-gdd/scripts/gdd_run.py --pack` | `scripts/gdd/gdd_run.py` 或 `gs_run.py --stage gdd --pack` |
| `ark-game-atlas/scripts/atlas_run.py` | `scripts/atlas/atlas_run.py` 或 `gs_run.py --stage atlas` |
| `ark-game-domains/domains/`、`ARK_GAME_DOMAINS_SKILL` | `ark-game-spec/domains/`、`ARK_GAME_DOMAINS_DIR`（舊 env 相容一版，印 DeprecationWarning）|
| `*_common.py` × 4 | `_lib/run_common.py`；`manifest.skill_versions` 改記 `ark-game-spec` + `stage:*` |
| gdd 舊 `assets/` 下的 `template.html.j2` / `default-style.yaml` | `assets/gdd-template.html.j2` / `gdd-default-style.yaml`；atlas 的在 `assets/atlas-default-style.yaml` |

## 邊界

- **domain 知識只在 `domains/`**：三個引擎 stage 不含 slot / fish / fast 任何硬編（已知例外：`gdd_from_spec` 的 slot section 對照，2.1 收斂 D-9 改讀 pack）。
- **只有 analyze 與 `gs_review --llm` 碰 LLM**；其餘 deterministic、同 run 重編 bit-identical。
- **數值不定案**：config-spec value 一律 null；數字由 ark-game-prob / ark-game-quicktest 段處理。
- **evidence 唯讀**：`wev_fetch` 追加 web evidence 是唯一例外，且只能撐 INFERRED。
- **2.0 不收斂重複實作**（兩套 spec parser、兩套 gdd-pack loader、三套 mini-markdown 渲染器）：留 2.1（D-9），本版先保證舊測試原封通過。
- 創作模式產出的 GDD 是企劃文件不是技術規格；工程 Spec / ADR 走 ark-superpowers。
