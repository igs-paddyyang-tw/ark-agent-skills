# ark-agent-skills Changelog

> 各專案同步 skills 時參考此檔案。格式：日期 + 動作 + 影響範圍。

---

## 2026-08-12

### 新增
- `ark-md-report` — Content 軌報告引擎（5 類型 × frontmatter 契約 × AI 寫作規則）
  - `scripts/report_lint.py` — 契約守門驗證（275 行）
  - `scripts/report_pair.py` — MD↔HTML 漂移檢查（119 行）
  - `scripts/report_register.py` — 索引 + 日報 log（112 行）
  - `references/agent-operating-guide.md` — 三件套運作契約
- `ark-html-report` — View 軌呈現引擎（5 風格 token × 17 元件 × Chart.js）
- `ark-api-doc-sync` — FastAPI route → docs API 表格自動同步
- `ark-eval-runner` — LLM 輸出回歸評測
- `ark-ingest-guard` — 知識入庫 prompt injection 消毒
- `ark-data-contract` — 管線元件間 schema 契約驗證
- `ark-release-notes` — git log → 結構化 changelog

### 移除（deprecated stub 保留 6 個月）
- `ark-report-template` → 被 `ark-md-report` + `ark-html-report` 取代
- `ark-postmortem` → 併入 `ark-md-report` type: incident
- `ark-ai-bot-builder` → 與 `ark-agent-builder` 完全重複
- `ark-daily-decision-digest` → 廢棄
- `ark-policy-translate` → 廢棄

### 修正
- `ark-code-spec-validator` — 四段工作流鏈優化（17 任務）
  - 評分公式定義 + 比例制 + drift 加權
  - AC-ID 約定 + loop-rules.md + 方向分流
  - pipeline 狀態檔 schema
  - evals.json
- `ark-superpowers` — 15 任務優化
  - plan 模板改 executor 相容 7 欄格式
  - checker one-pager 支援 + 空白章節攔截
  - build_docs.py --slug + upgrade 指令
  - ADR 單一來源 + hooks + parity check + evals
- `ark-html-dashboard` — theme: auto/dark/light
- `ark-data-dashboard` — theme: auto + depends_on html-dashboard
- `ark-webapp-generator` — theme: auto

### 治理
- 全庫 57 個 SKILL.md 回填 `category` / `outputs` frontmatter
- 5 組觸發詞衝突加 negative trigger 聲明
- `docs/skill-metadata-schema.md` — frontmatter 擴充規格
- `docs/report-frontmatter-standard.md` — 報告類 MD 標準
- `docs/trigger-matrix.md` — 衝突解法對照表

---

## 2026-08-05~07

### 新增
- `ark-grill-me` — 實作前拷問設計（加入預設 skills）
- `ark-spec-executor` — 執行 plan.md 任務清單（加入預設 skills）

### 修正
- `ark-wiki-engine` — 本地化 7 scripts（ingest/query/lint/graph/index/build/validate）

---

## 同步指南

```bash
# 從 kiro-cli 根目錄同步到子專案
cp -r ~/kiro-cli/.kiro/skills/ark-{skill-name} your-project/.kiro/skills/

# 批量同步核心 6 skills 到所有 agent
for agent in agents/*/; do
  for skill in ark-grill-me ark-superpowers ark-spec-executor ark-code-spec-validator ark-skill-creator ark-wiki-engine; do
    rm -rf "$agent/.kiro/skills/$skill"
    cp -r ~/kiro-cli/.kiro/skills/$skill "$agent/.kiro/skills/"
  done
done

# 同步報告雙軌
cp -r ~/kiro-cli/.kiro/skills/ark-md-report your-project/.kiro/skills/
cp -r ~/kiro-cli/.kiro/skills/ark-html-report your-project/.kiro/skills/
```

### 移除已廢棄 skills

```bash
rm -rf agents/*/.kiro/skills/ark-daily-decision-digest
rm -rf agents/*/.kiro/skills/ark-policy-translate
```
