---
name: ark-code-spec-validator
description: |
  驗證 code 與 spec/design 文件的一致性，產出 Drift Report。
  偵測 API 端點漂移、Schema 不符、依賴違規、驗收條件覆蓋缺口。
  使用此 Skill 當使用者提及 drift、驗證、spec 一致性、API 比對、
  驗收條件覆蓋、依賴分析、code 與文件不同步、或要求產出驗證報告。
  注意：本 skill 驗證的是 AC（驗收條件）是否有對應測試，
  非 pytest --cov 的 line coverage。如需 line coverage 分析，請用 pytest --cov。
metadata:
  category: process
  outputs:
    - format: md
      audience: both
  author: paddyyang
---

# ark-code-spec-validator

驗證原始碼與規格文件的一致性，產出 4 維度 Drift Report（0-100 評分）。

> **⚠️ 非 line coverage**：本 Skill 驗證的是 AC（驗收條件）是否有對應測試，非 `pytest --cov` 的 line coverage。如需 line coverage 分析，請用 `pytest --cov`。

## 觸發條件

- 「驗證 spec」、「drift report」、「code 跟 spec 一致嗎」
- 「API 端點有漏嗎」、「哪些 API 沒文件」
- 「驗收條件覆蓋」、「哪些 AC 沒測試」、「AC 覆蓋率」
- 「依賴分析」、「有沒有違規 import」
- 「跑一次 validator」、「產出驗證報告」

---

## 操作流程

### 快速驗證（API 端點 only）

```bash
python -m ark_team_agent.code_spec_validator .
```

產出：`knowledge/team-agent/wiki/operations/drift-report.md`

### 完整驗證（4 維度 + 評分）

```bash
python -m ark_team_agent.code_spec_validator --full .
```

產出同上，但包含 4 個維度的統一報告。

---

## 4 個驗證維度

| 維度 | 比對內容 | 評分邏輯 |
|------|---------|---------|
| **API 端點** | code 的 FastAPI route vs docs/ 中的 API 表格 | (1 - weighted_drift_ratio) × 100 |
| **Schema** ⚠️ | Pydantic/dataclass model vs spec 定義 | 掃描 model 數量（v2 比對）**〔不計分〕** |
| **依賴** | Python import graph vs design doc 規則 | 100 - (violations × 20)；無規則 → N/A |
| **測試覆蓋** | spec 驗收條件 vs tests/ 中的 test 函式 | covered / total × 100（AC-ID 優先） |

> ⚠️ **Schema 維度為 Informational Only**（v2 前不計入總分）。總分僅由 API 端點、依賴、測試覆蓋三維度加權計算。

---

## 解讀報告

執行後讀取 `knowledge/team-agent/wiki/operations/drift-report.md`，向使用者回報：

1. **總分**（0-100）+ emoji（✅ ≥90 / ⚠️ ≥70 / ❌ <70）
2. **各維度分數**
3. **最嚴重的 drift**（前 3 個）
4. **建議修復方向**：
   - API drift → 更新 docs/ 的 API 表格，或補實作
   - 依賴違規 → 重構 import 或更新 design doc
   - 測試缺口 → 補寫對應 test

---

## 輸出格式

回覆使用者時用以下格式：

```
📊 Spec Drift Report — Score: {score}/100

| 維度 | 分數 | 備註 |
|------|------|------|
| {emoji} API 端點 | {n}/100 | ×0.5 |
| ℹ️ Schema | {n} models | Informational（不計分） |
| {emoji} 依賴 | {n}/100 | ×0.2 |
| {emoji} 測試覆蓋 | {n}/100 | ×0.3 |

主要問題：
1. {最嚴重的 drift}
2. ...

💡 建議：{修復方向}
```

> **依賴維度 N/A 標示**：若 design doc 未定義依賴規則，報告中依賴行改為：
> `| ➖ 依賴 | N/A | 未定義依賴規則，不計入總分 |`
> 此時總分只由 API + 測試覆蓋計算（權重重分配）。

---

## 配置檔（.ark-validator.yaml）

在專案根目錄放置 `.ark-validator.yaml` 可自訂忽略清單，排除不需要驗證的項目：

```yaml
ignore:
  endpoints: ["GET /health", "GET /metrics"]   # 不計入 API 端點驗證
  modules: ["tests/*", "scripts/*"]            # 不掃描這些路徑的 import
  dependencies: ["dev-only"]                   # 忽略特定依賴規則標籤
```

### 欄位說明

| 欄位 | 型別 | 說明 |
|------|------|------|
| `ignore.endpoints` | `list[str]` | 格式 `METHOD /path`，完全匹配。被忽略的端點不算 drift 也不計入 total_endpoints |
| `ignore.modules` | `list[str]` | glob 模式，匹配的檔案不參與依賴分析 |
| `ignore.dependencies` | `list[str]` | 標籤名稱，design doc 中標記此標籤的規則被跳過 |

### 行為

- 若檔案不存在 → 全部掃描（預設行為，無忽略）
- 若檔案格式錯誤 → 報錯並 fallback 到全部掃描
- ignore 的項目在報告中以 `⏭️ ignored` 標示（可稽核，不是靜默消失）

---

## drift-report.md 格式

每次產出的 drift report 必須包含以下 frontmatter：

```yaml
---
date: YYYY-MM-DD
drift_score: 85
git_sha: abc1234
scoring_version: 2
api_score: 80
dep_score: N/A
test_score: 90
primary_direction: extra_in_code
---
```

| 欄位 | 說明 |
|------|------|
| `date` | 報告產出日期 |
| `drift_score` | 總分（0-100） |
| `git_sha` | 當次驗證的 git commit（short sha，7 chars） |
| `scoring_version` | 評分公式版本（當前為 `2`） |
| `api_score` | API 端點維度分數 |
| `dep_score` | 依賴維度分數；無規則時填 `N/A` |
| `test_score` | 測試覆蓋維度分數 |
| `primary_direction` | 偏移主因：`extra_in_code` / `missing_in_code` / `mismatch` / `none` |

### 歸檔規則

- 報告路徑：`knowledge/team-agent/wiki/operations/drift-report.md`（最新一份）
- 產出新報告時，舊報告移動到 `drift-reports/{date}.md`（以舊報告的 `date` 命名）
- `drift-reports/` 目錄位於專案根目錄，僅保留歸檔用途
- 歸檔格式不變（含 frontmatter + 完整報告內容）

---

## log.md 格式

路徑：`knowledge/team-agent/wiki/operations/log.md`

每次驗證 append 一行，pipe-delimited，不含空格：

```
date|sha|score|api|dep|test|direction|scoring_version
```

範例：

```
2026-08-11|a1b2c3d|85|80|N/A|90|extra_in_code|2
2026-08-10|f4e5d6c|72|65|100|70|missing_in_code|2
```

### 解析範例（Python one-liner）

```python
fields = "date sha score api dep test direction scoring_version".split()
rows = [dict(zip(fields, line.split("|"))) for line in open("log.md").read().strip().splitlines()]
```

---

## 注意事項

- 報告每次執行會覆寫（不是 append），舊報告自動歸檔到 `drift-reports/`
- `log.md` 會追加一行驗證結果（append-only）
- 如果 score ≥ 90，簡短回報「✅ 無顯著 drift」即可
- 不要把整份報告貼到 reply — 只摘要重點
- 詳細報告引導使用者看 `knowledge/team-agent/wiki/operations/drift-report.md`

---

## Fallback 策略（模組不可用時）

當 `python -m ark_team_agent.code_spec_validator` 執行失敗時，**禁止 agentic 自由發揮**。嚴格遵循以下步驟：

### 錯誤診斷

```
ModuleNotFoundError: No module named 'ark_team_agent.code_spec_validator'
```

**原因**：套件未安裝或版本過舊（需 ark_team_agent ≥ 1.0.5）。

### 修復指引

```bash
# 確認版本
pip show ark-team-agent | grep Version

# 升級到最新
pip install --force-reinstall https://github.com/igs-paddyyang-tw/ark_team_agent/releases/latest/download/ark_team_agent-*.whl
```

### 降級模式（模組確實不可用）

如果確認環境無法安裝套件，改用 `scripts/run_validator.py`：

```bash
python .kiro/skills/ark-code-spec-validator/scripts/run_validator.py --target .
```

### 禁止行為

- 🚫 禁止自行實作 validator 邏輯
- 🚫 禁止跳過驗證步驟直接回報「通過」
- 🚫 禁止用 grep/find 模擬 drift 分析

---

## 參考

- 詳細維度說明：`references/dimensions.md`
- 迴圈規則與閾值：`references/loop-rules.md`
- Pipeline 狀態 Schema：`references/pipeline-state-schema.md`
- Python module：`src/ark_team_agent/code_spec_validator/`
- One Pager：`docs/one-pagers/ark-code-spec-validator.md`

---

## 🔄 工作流鏈串接（Loop Engineering）

此 Skill 是四段鏈的最終驗證：

```
ark-grill-me → ark-superpowers → ark-spec-executor → 【ark-code-spec-validator】
                                                              │
                                       score ≥ 90 → ✅ Ship   │
                                       score < 90 → ⚠️ 方向分流（見 loop-rules.md）
```

### 迴圈規則

> 閾值與方向分流邏輯詳見 `references/loop-rules.md`（唯一來源）。

**摘要**：≥ 90 Ship / 70-89 方向分流 / < 70 方向分流（保險絲：loop ≥ 3 人工介入）

| Drift Score | 動作 |
|-------------|------|
| ≥ 90 | ✅ 標記 milestone 完成 |
| < 90 | ⚠️ 依偏移主因分流（見下） |

**方向分流**（score < 90 時）：

| 偏移主因 | 動作 |
|----------|------|
| `extra_in_code` 為主 | 觸發 `ark-superpowers` 補文件 |
| `missing_in_code` 為主 | 觸發 `ark-spec-executor` 補實作 |
| `mismatch` / 依賴違規為主 | 觸發 `ark-grill-me` 重新釐清需求 |

### Pipeline 狀態

- **開頭**：讀取 `docs/pipeline/{feature}.yaml`，取得 `loop_count` + `drift_scores` 歷史
- **結尾**：更新 `phase: validate`（或 `shipped`），append `drift_scores`，`loop_count += 1`，寫入 `last_direction` + `drift_report_path`
- Schema 詳見 `references/pipeline-state-schema.md`

### 銜接提示

- drift check 完成後，依方向分流主動建議下一步 Skill
- 修復完後再跑一次 validator，直到 score ≥ 90
- loop_count ≥ 3 時觸發保險絲，停止自動迴圈並回報使用者

