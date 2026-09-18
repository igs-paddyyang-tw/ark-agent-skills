---
name: ark-game-domains
description: |
  「競品影片 → 遊戲規格」skill 鏈的 Domain Pack 註冊庫：唯一放遊戲領域知識的地方
  （偵測器組合、分析項目與提詞、受控詞彙與 KB seed、規格章節與 dev-spec 模板、lint 規則、答案卷模板）。
  預設三個 pack：slot-game（slot 機台）、fish-game（捕魚機）、fast-game（快速遊戲 / mini-game：crash、dice、wheel、
  plinko、mines…），共用 `_core` 基底。三個引擎 skill（ark-video-understanding / ark-game-analysis / ark-game-spec）
  完全不含 domain 知識，只讀本 skill 的 resolved pack；新增 domain 不改任何引擎程式碼。
  使用此 skill 當使用者或 agent 提及：新增遊戲類型 / domain pack、麻將機 / 棋牌 / 街機要接影片分析、
  修改 slot / fish / fast 的分析項目或提詞、調整關鍵幀偵測器組合、pack lint、受控詞彙 / tag 白名單（遊戲類）、
  KB seed 頁、規格章節模板、dev-spec 模板、answer key 模板，或問「這條鏈支援哪些遊戲類型」。
  不適用於：實際跑影片分析（→ ark-video-understanding）、機制分析（→ ark-game-analysis）、產規格（→ ark-game-spec）；
  一般 wiki 受控詞彙管理（→ ark-wiki-engine）；建立非 pack 的一般 skill（→ ark-skill-creator）。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "1.0.0"
  updated: 2026-09-18
  outputs:
    - { format: data, audience: ai }
    - { format: md, audience: both }
  render: none
  depends_on: []
---

# ark-game-domains — Domain Pack 註冊庫

**引擎負責「不亂做」的機制，Pack 負責「做什麼」的知識。** 本 skill 是 pack 的單一真相來源；
三個引擎啟動時呼叫 `pack_resolve.py` 取得 `_core` + domain 合併後的 `resolved.json`，並把 `pack_sha256` 快照進 run。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `pyyaml` | 全部腳本 | exit 8 DRIVER_MISSING |
| 其餘 | — | stdlib |

引擎找本 skill 的順序：`ARK_GAME_DOMAINS_SKILL` 環境變數 → 同一個 skills 目錄下的 `ark-game-domains/`。
pack 根目錄可用 `ARK_GAME_DOMAINS_DIR` 覆寫（預設 `domains/`）。

## 資產地圖

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `domains/_core/` | 所有 domain 繼承的基底：C01–C04 分析項、core tags、通用章節與錨點、六檔 dev 模板、core lint | 改共用行為時 |
| `domains/slot-game/` `fish-game/` `fast-game/` | 三個預設 pack（各 6 項 + `_core` 4 項 = 10 項） | 讀 `references/domain-primer.md` 了解該 domain 的證據分佈 |
| `domains/_template/` | 新 domain 骨架（`__DOMAIN__` 佔位） | `pack_new.py` 使用 |
| `scripts/pack_resolve.py` | `--domain <d> [--out resolved.json]` 合併；`--list` 列已註冊 pack（ga_detect 的 enum 來源） | 引擎自動呼叫；除錯時手動 |
| `scripts/pack_lint.py` | `--domain <d>` / `--all`；error → exit 3 | **改 pack 後必跑**；新 domain 放行條件 |
| `scripts/pack_new.py` | `--domain <d> --display-name <n>` 從 `_template` 建骨架 + 回 checklist | 新增 domain 第一步 |
| `scripts/tests/test_packs.py` | lint 綠 / resolve deterministic / template 與衝突必擋 | 改腳本後 |

## 決策樹

```
要做什麼？
├─ 看這條鏈支援哪些遊戲 → python scripts/pack_resolve.py --list
├─ 看某 domain 合併後長什麼樣 → python scripts/pack_resolve.py --domain slot-game --out /tmp/r.json
├─ 新增一種遊戲類型
│   ├─ 1. python scripts/pack_new.py --domain mahjong-game --display-name 麻將
│   ├─ 2. 依 checklist 補：detect.cues、6 個 items + prompts、kb/schema.md（只能新增 tag）、seed ≥ 1、
│   │      spec/sections.yaml（insert_after 錨點）、state-machine skeleton、eval/answer-key、references/*
│   ├─ 3. python scripts/pack_lint.py --domain mahjong-game  ← 綠了 domain 才存在
│   └─ 4. 現有偵測器不夠？→ 這是唯一合法的「為 domain 改引擎」路徑：
│         在 ark-video-understanding/scripts/detectors/ 新增純函數並在 pack_lint.DETECTORS 登記，走 ADR 記錄
├─ 改某 domain 的分析項 / 提詞 / 章節 → 直接改 pack 檔 → pack_lint --domain
└─ 改所有 domain 共用的行為（core 項、通用章節、dev 模板）→ 改 _core → pack_lint --all
```

## Pack 契約 v1（`pack_lint` 守的東西）

```text
domains/<domain>/
├── domain.yaml            domain / display_name / contract "1" / version / extends: _core / detect.cues / detect.subtypes
├── extraction.yaml        detectors[]（use ∈ 註冊表 8 支；每個要 label）/ budget（不可超過 core hard_max）
├── analysis/items.yaml    items[]：id / name / order / prompt / kb_tags（必須在受控詞彙）/ claims[{key,type}] / entity{type,fields含id}
├── analysis/prompts/*.md  只寫「看什麼、輸出哪些 key」；出現指令覆寫句型或隱形字元 → error
├── kb/schema.md           `| tag | 定義 |` 表；不可重定義 core tags
├── kb/seed/GKB-*.md       frontmatter：id / title / type / tags / trust / status；可帶 proposes[{key,value,confidence}]
├── spec/sections.yaml     sections[]：id / title / source_items / insert_after（core 錨點 anchor_a / anchor_b 或其他節）
│                          / claim_prefixes（同 item 拆多節時過濾）/ entities: true
├── spec/config-structure.schema.json   config-spec.yaml.structure 的 JSON schema
├── spec/state-machine.skeleton.mmd     stateDiagram-v2；{{evidence:<claim key>}} 佔位必須是宣告過的 key
├── spec/dev/*.md.j2       可選；覆寫 _core 同名模板
├── lint/rules.yaml        封閉規則語言：{id, path(claim key), require: present|nonempty|provenance_in, severity: error|warn, message}
├── eval/answer-key.template.yaml       items 必含本 pack 全部 item id
├── eval/dataset.md        該 domain 需要哪幾類影片
└── references/domain-primer.md         給 agent 的 domain 入門；workflow-mapping.md 對接該 domain 企畫流程（可 TBD → warn）
```

合併規則（`pack_resolve`，deterministic）：items 依 `order` 排序；sections 依 `insert_after` 插入後移除錨點並編號；
tags 聯集（衝突 → error）；detectors 由 domain 整組取代 core 預設；budget deep-merge 但 `hard_max` 永遠取 core；
lint rules 聯集；dev 模板同名覆寫；`pack_sha256` 為 `_core` + domain 全部檔案的 sha256。

## 三個預設 pack 的資訊分佈（為什麼偵測器組合不同）

| domain | 資訊在哪 | 主偵測器 | 可觀察 / 不可觀察 |
|------|------|------|------|
| slot-game | 停輪後第一格、feature 進出 | `motion_settle`→reel_stop、`scene_change`、`flash`→big_win | paytable 幾乎不可觀察（需素材 F） |
| fish-game | 擊殺瞬間（分數彈出）、Boss 出場、特殊武器 | `roi_change(score)`→kill、`flash`、`motion_burst`、`scene_change` | 倍率可觀察（彈分 ÷ 砲注）；命中率永遠 UNKNOWN |
| fast-game | 回合邊界、倍率跳動 | `still_hold`→phase_hold（**時間差 = 回合秒數，OBSERVED**）、`motion_settle`→result_reveal | payout 曲線只能多回合 INFERRED |

## 輸出契約

所有腳本 stdout 為單一 JSON：`{"success", "contract":"1", "data", "meta":{"skill_version"}}`；
失敗 `{"success":false,"error":{"code","message","hint"}}`，exit：2 BAD_INPUT / 3 GATE_BLOCKED / 8 DRIVER_MISSING。

## 已知限制

- v1 只支援 `extends: _core`（不支援 pack 繼承 pack）。
- fish-game / fast-game 的 `workflow-mapping.md` 為 TBD：dev-spec 能產出，但尚無企畫流程接手（見設計文件 G-17）。
- fast-game 以單一 pack + `subtype` 欄位涵蓋 crash / dice / wheel…；若某 subtype 的 M7 超標再拆 sub-pack。
