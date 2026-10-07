# Domain Pack 契約 v1（ark-game-spec 2.0 `domains/`）

> 自 ark-game-domains 1.0.0 SKILL.md 原文抽出；pack 檔案與 lint 規則未改，只是搬到 ark-game-spec/domains/，腳本在 scripts/pack/。

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
