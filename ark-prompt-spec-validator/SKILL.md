---
name: ark-prompt-spec-validator
description: |
  驗證 Markdown 提詞與 AI 內文（SKILL.md、agent system prompt、steering 文件、
  給 AI 看的 wiki/報告內文）是否符合 ark-agent-skills 規格，且能讓 Agent 正確對話運作。
  兩層守門：L1 prompt_lint.py（deterministic：frontmatter schema、placeholder 殘留、
  路徑斷鏈、指令矛盾、觸發詞衝突、注入/隱形字元）→ L2 prompt_eval.py
  （行為 eval：情境輸入 → 預期行為斷言，N 次取通過率），合併產出 Prompt Drift Report。
  使用此 skill 當使用者提及「驗證提詞」「提詞 lint」「prompt drift」「md 符不符合規格」
  「SKILL.md 檢查」「steering 文件驗證」「AI 內文驗證」「提詞 eval」「這份提詞 agent 跑得動嗎」
  「提詞回歸測試」。不適用於：驗證 Python code 與 spec 一致性請用 ark-code-spec-validator；
  單一 skill 的建立與 description 優化請用 ark-skill-creator；整庫稽核請用 ark-skills-align。
metadata:
  author: paddyyang
  schema_version: 1
  category: process
  outputs:
    - { format: md, audience: both }
    - { format: data, audience: ai }
  render: none
  depends_on: [ark-md-report]
  status: active
  version: "1.0"
  updated: 2026-09-11
---

# ark-prompt-spec-validator

驗證「給 AI 讀的 Markdown」：規格對不對（L1，靜態）、放給 Agent 跑對不對（L2，行為）。
與 ark-code-spec-validator 是**同一份報告契約、兩個 validator**：那邊驗 code↔spec，這邊驗 prompt↔spec。

## 核心原則

1. **L1 是門，L2 是尺**：L1 有 P0 直接 `broken`，不跑 L2；L1 過了才用 L2 量「能不能正確運作」
2. **靜態能驗的不交給 LLM**：placeholder、路徑、矛盾、觸發詞衝突全在 L1 用腳本判，LLM 自評「看起來沒問題」不算通過
3. **L2 結果標信任層級**：純斷言（must_contain/regex/json）為 `deterministic`；用了 `judge` 的案例標 `llm-distilled`，報告分開統計
4. **報告可被下游吃**：產出符合 ark-md-report `review` 型 frontmatter，`report_lint.py` 必過，log line 走 CollectorRunner 契約

## 觸發條件

- 「驗證這份提詞」「這個 SKILL.md 符合規格嗎」「prompt lint」
- 「steering 文件檢查」「hoyeah 的 leader 提詞跑得對嗎」
- 「提詞 eval」「提詞回歸」「改了 system prompt 會不會壞」
- 「prompt drift report」

## 三種文件型別

| type | 對象 | L1 額外規則 | L2 典型案例 |
|------|------|------------|------------|
| `skill` | SKILL.md | name=目錄名、schema v1、觸發詞衝突矩陣 | 觸發/不觸發測試 |
| `prompt` | agent system prompt / steering / persona | 角色、邊界、輸出格式三章節必在 | 情境對話 → 行為斷言 |
| `content` | 給 AI 看的報告/wiki 內文 | chunk 自足禁詞、Finding ID 連續 | 通常不跑 L2（交 report_lint） |

不指定時腳本依路徑推斷（`SKILL.md` → skill；`steering/`、`prompts/`、`*.prompt.md` → prompt；其餘 → content）。

## 操作流程

### 1. L1 靜態 lint

```bash
python scripts/prompt_lint.py <path-or-dir> [--type skill|prompt|content] \
    [--repo <ark-agent-skills>]      # skill 型：跨庫觸發詞衝突比對
    [--config .ark-prompt-validator.yaml] [--json l1.json]
```

規則清單與嚴重度見 `references/lint-rules.md`（PL-xxx 穩定 ID）。
exit code：0 = 無 P0/P1；1 = 有 P1；2 = 有 P0。

### 2. L2 行為 eval（L1 無 P0 才跑）

先為目標提詞寫 `evals/<slug>.eval.yaml`（schema 見 `references/eval-schema.md`，範本在 `assets/evals.example.yaml`）。

```bash
python scripts/prompt_eval.py evals/<slug>.eval.yaml [--runs 3] [--json l2.json]
```

runner 兩種：`anthropic`（直接打 API，需 `ANTHROPIC_API_KEY`）或 `cmd`（把 system prompt 與輸入交給任意 CLI，例如 Kiro / claude-code，供 hoyeah 這類已部署 agent 用）。每案例跑 N 次，通過率 ≥ `threshold` 才算過。

### 3. 合併報告

```bash
python scripts/prompt_report.py --l1 l1.json [--l2 l2.json] \
    --subject <repo-relative-path> --out docs/reports/review/<date>-prompt-drift-<slug>.md
python <ark-md-report>/scripts/report_lint.py docs/reports/review/<date>-prompt-drift-<slug>.md
python <ark-md-report>/scripts/report_register.py docs/reports/review/<date>-prompt-drift-<slug>.md
```

## 評分（scoring_version 1）

| 維度 | 公式 | 權重 |
|------|------|------|
| L1 靜態 | 100 − P1×15 − P2×5 − P3×1（下限 0）；任一 P0 → 總分 0、verdict `broken` | 0.4 |
| L2 行為 | 通過案例 / 總案例 × 100（deterministic 與 llm-distilled 分開列，總分只計 deterministic） | 0.6 |

無 L2 時權重重分配（總分 = L1）。verdict：`sound` ≥90 / `needs-work` ≥70 / `broken` <70 或 P0。

## 回覆使用者格式

```
📝 Prompt Drift Report — {subject} — Score: {score}/100 · {verdict}

| 層 | 分數 | 備註 |
|----|------|------|
| {emoji} L1 靜態 | {n}/100 | P0:{n} P1:{n} P2:{n} |
| {emoji} L2 行為 | {n}/100 | {pass}/{total} deterministic · {j_pass}/{j_total} llm-distilled |

主要問題：
1. PL-xxx {現象 + 位置}
2. E-x {失敗案例 + 實際輸出片段}

💡 建議：{修復方向}
報告已落盤 {path}｜lint: PASS
```

## 邊界

- 不修改被驗證的提詞；只報告。修 description 交 ark-skill-creator，批次改庫交 ark-skills-align
- 不驗 code（FastAPI route / import / test）；那是 ark-code-spec-validator
- L2 `judge` 結果永遠不進總分，只作參考；要進總分請改寫成可斷言的 `expect`
- 沒有 evals yaml 時只出 L1 報告，並在 Actions 章節提議 3 個最該寫的 eval 案例
