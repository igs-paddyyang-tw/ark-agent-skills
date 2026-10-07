# run 目錄契約（ark-game-spec 2.0）

> 自 ark-video-understanding / ark-game-analysis / ark-game-spec 1.x 的 SKILL.md 原文抽出，內容未改；路徑中的舊 skill 名已對應到本 skill 的 scripts/<stage>/。

## A. 影片 → evidence（video stage）

### Run 目錄契約（所有 stage 共用）

```text
artifacts/cva/<run_id>/
├── manifest.json          run_id / video{sha256,duration,fps,...} / domain / domain_source(cli|detected|pending)
│                          / pack_version / pack_sha256 / stages{耗時} / budget_used / skill_versions / detect
├── pack/resolved.json     pack 快照（重放時 pack 已改也能還原）
├── video/source.mp4 · video/meta.json
├── transcript/transcript.json   {source, trust: untrusted, segments[]}
├── frames/motion_timeline.json · events.json · keyframes/ · keyframes.json · sheets/ · sheets.json
│   （auto 模式：detect/ · detect.json · detect_sheets/ · detect_sheets.json）
└── evidence.jsonl         唯讀。每行 {evidence_id E001…, type visual|transcript, extractor, detector, t_start, t_sec,
                           frame, sheet{file,sheet,cell}, video_sha256, trust{timestamp: deterministic, observation: llm|untrusted},
                           observation[]（此時為空，ga_observe 填到 observations.jsonl）}
```

### 預算與 exit code

三道預算來自 pack：`max_keyframes` / `max_sheets` / `max_llm_calls`；CLI 可覆寫但不可超過 `_core` 的 `hard_max`（exit 9 BUDGET_EXCEEDED）。
exit：2 BAD_INPUT / 3 GATE_BLOCKED（evidence 已存在未加 --force）/ 5 CONN_FAILED（yt-dlp）/ 6 QUERY_FAILED（ffmpeg）/ 7 TIMEOUT / 8 DRIVER_MISSING / 9 BUDGET_EXCEEDED。

## B. 機制分析（analysis stage）

### 後處理守門（`ga_analyze.postprocess`，測試守著）

| 模型回了什麼 | 引擎怎麼做 |
|------|------|
| 未在 pack 宣告的 claim key | 丟棄 + `schema_violations` |
| 引用不存在的 evidence id | 該 claim 降 UNKNOWN |
| OBSERVED 但只有 transcript evidence | 降 INFERRED（口白不是證據） |
| OBSERVED / INFERRED 但沒 evidence | 降 UNKNOWN |
| provenance / confidence 不在 enum | UNKNOWN / unknown |
| 宣告了但沒回的 key | 補 UNKNOWN |
| entity id 不符 `^[a-z][a-z0-9_]{1,40}$` 或重複 | 丟棄（符號一律 symbol_a、魚種 fish_a…不取名） |
| value 型別轉不過去 | 降 UNKNOWN |

### 輸出契約

`game-analysis.yaml`：
```yaml
contract: "1"  run_id  domain  pack_version  pack_sha256  model
items:
  - id: S01  name: reel_layout
    claims: [{key, value, provenance, evidence: [E003], confidence, reasoning}]
    entities: [{id: symbol_a, entity_type: symbol, provenance, evidence, <pack fields>}]
stats: {claims, unknown, entities, schema_violations}
```
`kb-refs.yaml`：`items[{item_id, tags_used, informative, refs[{id, title, match, score, tags_hit, trust, domain, cross_domain, proposes}]}]`。
`entities.json`：`{entities:{<type>:[ids]}, all_ids}` — ark-game-spec 命名守門的字典。

`report/<date>-game-analysis-<run>.md`（ark-md-report 契約，`type: data`）：
frontmatter `subject: cva/<run_id>`、`verdict: confirmed | inconclusive | rejected`（UNKNOWN ≤ 30% 且無 P0 / ≤ 60% / 其餘）、
`confidence`（visual evidence ≥ 10 且無違規 high / ≥ 3 medium / 其餘 low）、`score` = 覆蓋率 %（`score_version: ga-coverage-1`）、
`findings {p0..p3}`、`tags: [case, game]`、`run{run_id, domain, pack_sha256, model, video_sha256}`。
章節：Verdict / 假設與方法 / Findings / Evidence / Actions / **機制主張總表**（每條 claim 原樣：key / value / provenance / evidence / confidence）/ 知識庫命中 / 邊界聲明。
Findings 全由規則產生：P0 UNKNOWN > 60%；P1 schema_violations > 0、無 visual evidence；P2 某分析項全 UNKNOWN；P3 無同 domain KB 命中、無實體。
日期取 `manifest.stages.analyze.at`，同 run 重編 bit-identical；lint FAIL 視為引擎 bug（exit 6），不手改報告。

stdout 單一 JSON envelope；exit：2 / 3 GATE_BLOCKED（detect 不足、observations 已存在）/ 5 CONN_FAILED（憑證）/ 6 QUERY_FAILED（契約錯誤）/ 8 / 9。

## C. 規格（spec stage）

## Spec Markdown 契約（`spec_lint` 就是照這個 parse）

```markdown
### 04. Reel Configuration
<!-- section:reel_config items:S01 -->
### OBSERVED
- `reel.columns` = 5 — evidence: E003, E007 — confidence: high
### INFERRED
- `reel.rows` = 3 — evidence: E003 — reasoning: … — confidence: medium
### FROM_KB
- `GKB-SLOT-FS-001` Free Spin 標準觸發 — tags: free-spin, scatter — trust: deterministic
### PROPOSED
- `free_spin.retrigger` = true — rationale: … — basis: GKB-SLOT-FS-001, E012 — confidence: medium
### UNKNOWN
- `reel.variable_rows` — question: Q004
### DECIDED            ← 只在 v1
- `free_spin.count_awarded` = 10 — decision: D003 — rationale: …
```
special 章節：`state_machine`（mermaid，`{{evidence:key}}` 已填 E id）、`configuration`（數值型 claim 候選）、`evidence`（引用表）、`open_questions`（Q 清單；v1 會標 `— resolved: Dnnn`）。

### Lint 規則

| 規則 | 意思 |
|------|------|
| NUM-OUTSIDE | 非 special 章節裡，含數字的行必須是 provenance bullet（沒有 evidence 的數字進不了規格） |
| OBS-EVIDENCE | OBSERVED 必有 evidence、全部存在、至少一筆 visual |
| INF-EVIDENCE | INFERRED 必有存在的 evidence |
| KB-REF | FROM_KB 的 GKB id 必在 kb-refs / pack seed |
| PROPOSED | 必有 basis（每筆為存在的 E 或 GKB）與 confidence |
| UNKNOWN-Q | UNKNOWN ↔ Open Questions 雙向；孤兒 Q 為 warn |
| DECIDED-D | DECIDED 的 D 必在 decisions.yaml |
| NAME | 反引號名稱必須是 pack claim key / entities.json id / GKB / E / Q / D / 章節 id（擋住編造的符號名） |
| SECTIONS | 章節與 pack 一致 |
| PACK:<id> | pack `lint/rules.yaml` 套在 analysis claims（v1 會合併 DECIDED 值） |

### dev-spec 六檔

`game-spec.md`（= v1）、`feature-spec.md`（entities + claims by item）、`state-machine.md`（mermaid）、`ui-spec.md`、
`qa-checklist.md`（每條 OBSERVED / INFERRED / DECIDED 一個可勾核項）、`config-spec.yaml`：
```yaml
structure: {symbol: [{id, type, observed}], feature: [...]}      # 形狀給 STEP02 建表
parameters:
  - {name: free_spin.count_awarded, type: integer, value: null, source: TO_BE_DECIDED_BY_MATH,
     competitor_reference: {value: 10, provenance: DECIDED, evidence: [E012], decision_id: D003}}
```
**競品數字只能活在 competitor_reference，永遠不能變成 value** — 引擎自檢，非 null 直接 exit 3。

### benchmark.json

M1 lead time（fetch → dev，小時）、M2 stage 耗時、M3 coverage（all / known）、M4 UNKNOWN recall、M5 KB reuse、
M6 Draft→v1 修改率、M7 hallucination rate、M8 cross-domain refs、M9 domain detect 正確；`--answer-key` 用 pack `eval/answer-key.template.yaml` 格式。

stdout 單一 JSON envelope；exit：2 BAD_INPUT（decisions 格式）/ 3 GATE_BLOCKED（lint / defer / 必填 / null 自檢）/ 6 / 8。
