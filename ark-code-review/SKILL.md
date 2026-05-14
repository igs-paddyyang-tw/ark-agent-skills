---
name: ark-code-review
description: |
  產出程式碼審查 Skill，支援 Python/TypeScript 程式碼品質檢查、
  風格一致性驗證、安全性掃描、PR 審查報告產生。
  使用此 Skill 當使用者提及程式碼審查、code review、PR 審查、
  程式碼品質、lint、或任何需要檢查程式碼品質的場景。
---

# ark-code-review

產出 `src/skills/internal/code_review.py`，程式碼審查與品質檢查，可獨立運作。

## 觸發條件

- 「程式碼審查」、「code review」、「PR 審查」
- 「程式碼品質」、「lint」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `file_paths` | `list[str]` | ✅ | — | 要審查的檔案路徑 |
| `language` | `str` | ❌ | `"auto"` | 語言：`python` / `typescript` / `auto` |
| `rules` | `list[str]` | ❌ | `[]` | 自訂規則（如 `"no-print"`, `"type-hints"`) |
| `severity` | `str` | ❌ | `"all"` | 嚴重等級篩選：`error` / `warning` / `info` / `all` |

## 產出指引

### Skill 類別

```python
class CodeReviewSkill(BaseSkill):
    skill_id = "code_review"
    skill_type = SkillType.PYTHON
    description = "程式碼審查與品質檢查"
    version = "1.0.0"
    input_schema = CodeReviewParams
```

### 檢查項目

| 類別 | 檢查項目 |
|------|---------|
| 風格 | 命名慣例、縮排、行長度、import 排序 |
| 品質 | 未使用變數、重複程式碼、複雜度過高 |
| 安全 | 硬編碼密碼、SQL injection、eval 使用 |
| 型別 | 缺少型別提示、型別不一致 |
| 文件 | 缺少 docstring、過時的註解 |

### 輸出格式

```json
{
  "issues": [
    {
      "file": "src/main.py",
      "line": 42,
      "severity": "warning",
      "category": "security",
      "message": "硬編碼的 API Key",
      "suggestion": "使用環境變數 os.getenv('API_KEY')"
    }
  ],
  "summary": {
    "total": 5,
    "errors": 1,
    "warnings": 3,
    "info": 1
  },
  "score": 85
}
```

## 注意事項

- `language: auto` 根據副檔名自動偵測
- 安全性檢查包含常見的 OWASP Top 10 模式
- `score` 為 0-100 分，100 為完美
- 可搭配 `ark-chatbot-generator` 在 TG Bot 中觸發審查
