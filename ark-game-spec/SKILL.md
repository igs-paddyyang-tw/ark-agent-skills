---
name: ark-game-spec
description: |
  遊戲規格產出 executor（domain-agnostic）：`game-analysis.yaml` + `kb-refs.yaml` → 依 pack 章節 deterministic 渲染
  `game-spec.draft.md`（每條主張在 OBSERVED / INFERRED / FROM_KB / PROPOSED / UNKNOWN 區塊內）→ `spec_lint` 四分法守門
  （區塊外不得有數字、OBSERVED 必有 visual evidence、名稱必在字典、UNKNOWN ↔ Open Question）→ review-report →
  人員以 ark-grill-me 決議 `decisions.yaml` → `gs_decide` deterministic 套用成 `game-spec.v1.md`（PROPOSED→DECIDED）→
  `gs_dev` 產 dev-spec 六檔（config-spec.yaml 的 parameters.value **一律 null**）→ `benchmark.json`（M1–M9）。
  使用此 skill 當使用者或 agent 提及：競品規格草稿、機制規格書、Open Questions、規格 lint、provenance 四分法、
  Decision Record / decisions.yaml、dev-ready spec、feature spec / state machine / ui spec / qa checklist / config-spec、
  機率企畫 STEP01–04 的輸入、POC benchmark / M3 coverage / M7 hallucination。
  不適用於：影片抽幀（→ ark-video-understanding）、機制分析（→ ark-game-analysis）、章節模板與 lint 規則本身（→ ark-game-domains）、
  工程 Spec / Design / plan（→ ark-superpowers）、決議拷問流程本身（→ ark-grill-me）。
metadata:
  schema_version: "1.1"
  status: active
  author: paddyyang
  category: executor
  version: "1.0.0"
  updated: 2026-09-18
  outputs:
    - { format: md, audience: both }
    - { format: data, audience: ai }
  render: none
  depends_on: [ark-game-domains, ark-game-analysis, ark-grill-me]
---

# ark-game-spec — 分析 → Draft → 決議 → Dev-ready

三個階段、三個 gate，每個 gate 都是腳本而不是人的自律：
Draft 過 `spec_lint`（exit 3 不過）→ 決議格式過 `gs_decide` 驗證 → dev-spec 過 defer / 必填 / null 自檢。

## 前置需求

| 依賴 | 誰需要 | 缺了會怎樣 |
|------|--------|-----------|
| `pyyaml` | 全部 | exit 8 |
| `jinja2` | gs_dev（沙箱模板） | exit 8 |
| `jsonschema` | 選配，gs_dev 驗 config structure | 略過 schema 驗證 |
| ark-game-analysis 的 `llm_adapter` | 選配，`gs_review --llm` | 只出 deterministic 審查 |

## 資產地圖

| 路徑 | 用途 | 何時載入 |
|------|------|---------|
| `scripts/gs_run.py` | 分段一鍵：`--stage draft` / `decide` / `dev` | 預設入口 |
| `scripts/gs_draft.py` | deterministic 渲染 Draft 並自動 lint | — |
| `scripts/spec_lint.py` | 四分法守門；`--spec game-spec.v1.md` 也能驗 | **任何人手改 spec 後必跑** |
| `scripts/gs_review.py` | review-report.md：lint 摘要、Missing Information（附 KB 建議）、低信心、給 grill-me 的題目；`--llm` 加 advisory | Draft 後 |
| `scripts/gs_decide.py` | `--template` 產 decisions.template.yaml；套用 decisions.yaml → v1（重跑 bit-identical） | 人員決議後 |
| `scripts/gs_dev.py` | dev-spec 六檔；defer 阻斷；`config-spec.yaml` 自檢 value 全 null | v1 lint 綠後 |
| `scripts/gs_metrics.py` | benchmark.json；`--answer-key` 算 M4 / M7 / M9 | POC 評估 |
| `scripts/gs_common.py` | spec markdown 契約的 parser（`parse_spec` / `parse_bullet`） | 不直接執行 |
| `scripts/tests/test_spec_lint.py` | 每條 lint 規則一個反證 + decide determinism + config null | 改 lint 後 |

## 決策樹

```
拿到 game-analysis.yaml + kb-refs.yaml 的 run
├─ python scripts/gs_run.py --run <run> --stage draft
│     ├─ exit 3 → 讀 review-report.json 的 violations。原則：修 pack 或重跑 analyze，**不手改 spec 繞 lint**
│     └─ 綠 → 交 review-report.md + decisions.template.yaml 給企畫
├─ 人員決議（建議用 ark-grill-me 逐 Q 拷問）→ 填 decisions.yaml
│     decision ∈ accept（採 PROPOSED 值）| modify（給 value）| reject（保持 UNKNOWN）| defer（阻斷 dev）
├─ python scripts/gs_run.py --run <run> --stage decide  → game-spec.v1.md + v1 lint
├─ python scripts/gs_run.py --run <run> --stage dev [--answer-key k.yaml]
│     ├─ exit 3 defer 未解 → 回去決議（或 --allow-deferred，manifest 會標記 dev-spec 不完整）
│     ├─ exit 3 必填未決（pack lint 規則 severity=error & nonempty）→ 回去決議
│     └─ 綠 → dev-spec/ 六檔 + benchmark.json
└─ 想知道這條鏈到底省了多少 → benchmark.json 的 M1 lead time 對比人工基準（pack workflow-mapping）
```

## Spec Markdown 契約（`spec_lint` 就是照這個 parse）

```markdown
## 04. Reel Configuration
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

## Lint 規則

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

## dev-spec 六檔

`game-spec.md`（= v1）、`feature-spec.md`（entities + claims by item）、`state-machine.md`（mermaid）、`ui-spec.md`、
`qa-checklist.md`（每條 OBSERVED / INFERRED / DECIDED 一個可勾核項）、`config-spec.yaml`：
```yaml
structure: {symbol: [{id, type, observed}], feature: [...]}      # 形狀給 STEP02 建表
parameters:
  - {name: free_spin.count_awarded, type: integer, value: null, source: TO_BE_DECIDED_BY_MATH,
     competitor_reference: {value: 10, provenance: DECIDED, evidence: [E012], decision_id: D003}}
```
**競品數字只能活在 competitor_reference，永遠不能變成 value** — 引擎自檢，非 null 直接 exit 3。

## benchmark.json

M1 lead time（fetch → dev，小時）、M2 stage 耗時、M3 coverage（all / known）、M4 UNKNOWN recall、M5 KB reuse、
M6 Draft→v1 修改率、M7 hallucination rate、M8 cross-domain refs、M9 domain detect 正確；`--answer-key` 用 pack `eval/answer-key.template.yaml` 格式。

stdout 單一 JSON envelope；exit：2 BAD_INPUT（decisions 格式）/ 3 GATE_BLOCKED（lint / defer / 必填 / null 自檢）/ 6 / 8。
