---
author: paddyyang
name: ark-code-spec-validator
description: |
  驗證 code 與 spec/design 文件的一致性，產出 Drift Report。
  偵測 API 端點漂移、Schema 不符、依賴違規、測試覆蓋缺口。
  使用此 Skill 當使用者提及 drift、驗證、spec 一致性、API 比對、
  測試覆蓋檢查、依賴分析、code 與文件不同步、或要求產出驗證報告。
---

# ark-code-spec-validator

驗證原始碼與規格文件的一致性，產出 4 維度 Drift Report（0-100 評分）。

## 觸發條件

- 「驗證 spec」、「drift report」、「code 跟 spec 一致嗎」
- 「API 端點有漏嗎」、「哪些 API 沒文件」
- 「測試覆蓋率」、「哪些驗收條件沒測試」
- 「依賴分析」、「有沒有違規 import」
- 「跑一次 validator」、「產出驗證報告」

---

## 操作流程

### 快速驗證（API 端點 only）

```bash
py -m ark_team_agent.skills.code_spec_validator .
```

產出：`knowledge/team-agent/wiki/operations/drift-report.md`

### 完整驗證（4 維度 + 評分）

```bash
py -m ark_team_agent.skills.code_spec_validator --full .
```

產出同上，但包含 4 個維度的統一報告。

---

## 4 個驗證維度

| 維度 | 比對內容 | 評分邏輯 |
|------|---------|---------|
| **API 端點** | code 的 FastAPI route vs docs/ 中的 API 表格 | 100 - (drifts × 5) |
| **Schema** | Pydantic/dataclass model vs spec 定義 | 掃描 model 數量（v2 比對） |
| **依賴** | Python import graph vs design doc 規則 | 100 - (violations × 20) |
| **測試覆蓋** | spec 驗收條件 vs tests/ 中的 test 函式 | covered / total × 100 |

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

| 維度 | 分數 |
|------|------|
| {emoji} API 端點 | {n}/100 |
| {emoji} Schema | {n}/100 |
| {emoji} 依賴 | {n}/100 |
| {emoji} 測試覆蓋 | {n}/100 |

主要問題：
1. {最嚴重的 drift}
2. ...

💡 建議：{修復方向}
```

---

## 注意事項

- 報告每次執行會覆寫（不是 append）
- `log.md` 會追加一行驗證結果（append-only）
- 如果 score ≥ 90，簡短回報「✅ 無顯著 drift」即可
- 不要把整份報告貼到 reply — 只摘要重點
- 詳細報告引導使用者看 `knowledge/team-agent/wiki/operations/drift-report.md`

---

## 參考

- 詳細維度說明：`references/dimensions.md`
- Python module：`src/ark_team_agent/skills/code_spec_validator/`
- One Pager：`docs/one-pagers/ark-code-spec-validator.md`
