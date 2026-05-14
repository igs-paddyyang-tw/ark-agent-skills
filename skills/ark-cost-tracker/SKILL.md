---
name: ark-cost-tracker
description: |
  產出 API 呼叫成本追蹤 Skill，記錄 LLM API 的 token 使用量和費用。
  支援 Gemini、Ollama 等多個 LLM 後端的成本計算。
  使用此 Skill 當使用者提及成本追蹤、API 費用、token 使用量、
  cost tracking、或任何需要監控 LLM 呼叫成本的場景。
---

# ark-cost-tracker

產出 `src/skills/internal/cost_tracker.py`，追蹤 LLM API 呼叫成本，可獨立運作。

## 觸發條件

- 「成本追蹤」、「API 費用」、「token 使用量」
- 「cost tracking」、「LLM 成本」

## 產出檔案

- `src/skills/internal/cost_tracker.py`
- `data/costs/` — 成本記錄目錄

## 產出指引

### Skill 類別

```python
class CostTrackerInput(SkillParam):
    """Cost Tracker 輸入參數。"""
    action: str = Field(default="log", description="操作：log（記錄）/ report（報告）")
    model: str = Field(default="", description="LLM 模型名稱")
    input_tokens: int = Field(default=0, description="輸入 Token 數")
    output_tokens: int = Field(default=0, description="輸出 Token 數")

class CostTrackerSkill(BaseSkill):
    skill_id = "cost_tracker"
    skill_type = SkillType.PYTHON
    description = "LLM 成本追蹤：Token 用量 + 費用統計"
    input_schema = CostTrackerInput
```

### 功能

| action | 功能 |
|--------|------|
| `log` | 記錄一次 API 呼叫（model + tokens） |
| `summary` | 查詢指定期間的成本摘要 |
| `reset` | 重置成本記錄 |

### 費率表

```python
COST_PER_1K_TOKENS = {
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
    "qwen3:4b": {"input": 0.0, "output": 0.0},  # 本地免費
    "qwen3:8b": {"input": 0.0, "output": 0.0},
}
```

### 輸出格式

```json
{
  "period": "today",
  "total_calls": 42,
  "total_tokens": 125000,
  "total_cost_usd": 0.075,
  "by_model": {
    "gemini-2.5-flash": {"calls": 40, "tokens": 120000, "cost": 0.072},
    "gemini-2.5-pro": {"calls": 2, "tokens": 5000, "cost": 0.003}
  }
}
```

## 整合方式

在 GeminiAdapter 的 `generate()` 和 `function_call()` 回傳後自動呼叫 `cost_tracker.log()`。

## 注意事項

- 成本記錄存在 `data/costs/{date}.json`
- 本地 Ollama 模型費用為 0
- 費率表需手動更新（API 定價可能變動）
