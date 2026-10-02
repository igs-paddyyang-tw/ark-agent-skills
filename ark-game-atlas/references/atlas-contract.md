# atlas 契約 v1（v1.1 增補見文末）

## atlas.yaml
```yaml
contract: "1"
genre: atlas
slug: dragon-fortune            # 唯一 id；kebab-case
title / subtitle / author / version(int) / status: draft|review|published / language: zh-Hant
distribution: internal          # 必為 internal（lint 擋）
game:
  domain, display_name, run_id, video_sha256, spec_source: game-spec.v1.md|game-spec.draft.md,
  spec_sha256, evidence_sha256, pack_version, pack_sha256, decisions, open_questions, claims
cover: {image: assets/figures/F001.jpg, accent: "#E0B95A"}
style: {name, theme: dark|light, tokens: {--bg: ..., --accent: ...}}   # ark-html-report token 契約變數
shelf: games/<domain>
tags: [...]                     # pack 受控詞彙（items kb_tags ∪ domain）
chapters: [{n, slug, title, type: preface|chapter, file, figures: [F001]}]
atlas_pack_snapshot_stale: false
created / updated
```

## 章節 Markdown
frontmatter：`chapter, slug, title, type, sections[](spec section id), figures[], tags[], sources[], trust: deterministic`

一般章五段（順序固定）：`## 一句話`（無數字）→ `## 畫面`（figure 或固定句）→ `## 規則`（`- **TAG** <spec bullet 原文>`；`### <spec section title>` 分組；state_machine 為 mermaid fence；表格原樣）→ `## 未知與決議`（UNKNOWN / PROPOSED bullet + `- **DECIDED** D007 \`key\` — 理由：…`）→ `## 相關機制`（FROM_KB bullet）。
序四段：`## 這是什麼遊戲` / `## 這本書怎麼讀` / `## 來源與版本` / `## 全書地圖`。

figure 語法：
```
![E012 · 00:01:23.750 · reel_stop](assets/figures/F004.jpg)
<!-- figure:F004 evidence:E012 -->
```

## figures.json
```json
{"contract":"1","run_id":"…","figures":[{"figure_id":"F004","type":"frame|strip|hero|state_frame","chapter":"reels",
 "evidence":["E012"],"t":[83.75],"ts":["00:01:23.750"],"labels":["reel_stop"],"src_frames_sha256":["…"],
 "file":"assets/figures/F004.jpg","caption":"E012 · 00:01:23.750 · reel_stop","w":1280,"h":720,"ops":{...},"sha256":"…","state":"reel_stop"}],
 "stats":{"count":9,"by_type":{...}}}
```

## pack atlas/（ark-game-domains）
- `outline.yaml` chapters[]：`id, title, type?, sections[], insert_after?, figure{type: hero|frame|strip|state_frames|none, prefer[], rule}`；`anchor: true` 為插入點
- `figures.yaml`：`hero.prefer[]`、`strips.<rule>{labels[]|around,before,after,max}`、`frame{max_width,quality,burn_caption}`、`strip{cell_width,arrow}`、`state_frames{thumb_width}`
- `style.yaml`：`name, theme, tokens{}`

## HTML 戳記
每章 `<!-- content-src: NN-x.md sha256:<16> -->`；書層 `<!-- atlas-src: atlas.yaml sha256:… figures:<figures.json sha16> chapters:N built:… -->`。`atlas_build --check`：任一不符 → STALE（exit 3）。

## library/atlas/catalog.json
見 SKILL.md「圖書館契約」；`shelves` 受控，不在清單 → 登錄但 WARN。

---

## v1.1 增補：gdd-pack 入口（atlas_from_gdd）

`atlas.yaml` 差異：`contract: "1.1"`；`game.spec_source: gdd-pack`、`game.run_id: gdd:<pack-dir-name>`、`game.video_sha256: null`、
`game.spec_sha256` = sha256（依序 `name.encode() + file bytes`，順序：gdd.yaml, symbols.yaml, screens.yaml, info.yaml, i18n.csv, 再 `rules/*.md` 檔名排序；缺檔跳過）、
`game.evidence_sha256` = screens.yaml 的 sha；`game.open_questions` 來自 gdd.yaml；`tags: [<domain>, gdd]`；style 預設 planner-brown-gold（accent `#e9b949`）。

章節：`00-preface`（序四段）→ `01-at-a-glance`（spec kv 表）→ `02-symbols`（圖騰牆 symbol_table figure + 表，含 `code` 反引號）→ 每個 `gdd.yaml.features[]` 一章（slug = feature id，五段）→ `NN-evidence-index` → `NN-glossary`（符號命名 + 多國語系）。

規則段來源 `rules/<feature>.md`（mini-markdown）：`- ` 清單 → `- **SPEC** …`；`> ` 引言 → SPEC bullet；純文字段 → SPEC bullet（第一段無數字者兼作「一句話」候選）；`###` 與表格原樣；已帶 provenance 的 bullet 不重複前置。

provenance 新增 **SPEC**：來源是規格書 / 企劃樣板，不是影片觀察；lint `TAG_RE` 接受，色票與 OBSERVED 同級。

figures.json 新 type：
```json
{"figure_id":"F003","type":"asset|symbol_table|hero","chapter":"fg","evidence":[],"t":[],"ts":[],"labels":["2"],
 "source":{"kind":"screens|symbols","file":"fg_02_進場.png","sha256":"…","feature":"fg"},
 "src_frames_sha256":["…"],"file":"assets/figures/F003.jpg","caption":"進場 · fg_02_進場.png","w":1280,"h":720,
 "ops":{"max_width":1280,"burn_caption":true},"sha256":"…"}
```
`asset`：示意圖，等比縮至 1280w、左下燒 `<title> · <file>`；`symbol_table`：PIL 拼牆（180px 格、6 欄、格下 code + odds；無檔者「待美術」），`source.kind: symbols`、`source.file` 為組 id；`hero` = 主玩法（features[0]）第一張示意圖。每章最多 `--max-figs`（預設 6）張，其餘只進證據索引。

sources 佈局：`sources/gdd/{gdd.yaml,symbols.yaml,screens.yaml,info.yaml,i18n.csv,rules/*.md}`（0444）+ `names.json {names:[…]}`（圖騰 code、sym_id、feature id、slug）。

lint gdd 模式（`game.spec_source == gdd-pack`）：ATL-STALE 以上述 sha 規則重算；ATL-NUM 允許集 = 來源全文（含檔名）∪ open_questions ∪ 圖數；ATL-NAME 允許集 = names.json ∪ 來源反引號詞 ∪ 章節 slug；`asset` / `symbol_table` figure 必有 `source`；evidence id 集為空（E 編號不適用）。

路徑：書在 `data/atlas/<slug>/`，圖書館在 `data/library/atlas/`（v1.1 起 atlas_run 預設值）。
