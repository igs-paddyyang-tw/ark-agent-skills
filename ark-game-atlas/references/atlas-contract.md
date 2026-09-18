# atlas 契約 v1

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
