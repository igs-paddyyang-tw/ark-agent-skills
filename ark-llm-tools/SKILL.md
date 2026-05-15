---
author: paddyyang
name: ark-llm-tools
description: |
  產出 LLM 通用工具 Skills（summarize、analyze、qa、intent_parse），
  搭配 GeminiAdapter 或 LLMAdapter 進行文字摘要、資料分析、問答、意圖解析。
  使用此 Skill 當使用者提及 LLM 摘要、AI 分析、智能問答、意圖解析、
  或任何需要 LLM 文字處理能力的場景。
---

# ark-llm-tools

產出 4 個 LLM 通用工具 Skills，可獨立運作。

## 觸發條件

- 「LLM 摘要」、「AI 分析」、「智能問答」
- 「意圖解析」、「文字摘要」、「summarize」

## 產出檔案

```
src/skills/llm_skills/
├── __init__.py
├── llm_summarize.py    # 文字摘要
├── llm_analyze.py      # 資料分析（趨勢、異常、建議）
├── llm_qa.py           # 問答（搭配 context）
└── parse_intent.py     # 意圖解析（自然語言 → 結構化意圖）
```

## 產出指引

### llm_summarize

```python
class LLMSummarizeInput(SkillParam):
    """LLM Summarize 輸入參數。"""
    content: str = Field(description="要摘要的文本內容")
    max_length: int = Field(default=500, description="摘要最大字數")

class LLMSummarizeSkill(BaseSkill):
    skill_id = "llm_summarize"
    skill_type = SkillType.LLM
    description = "文本摘要：長文檔快速摘要"
    input_schema = LLMSummarizeInput
```

- 輸入長文 → 輸出指定長度的摘要
- 支援多語言（zh-TW / en / ja）

### llm_analyze

```python
class LLMAnalyzeInput(SkillParam):
    """LLM Analyze 輸入參數。"""
    data: str = Field(description="要分析的數據（文字或 JSON）")
    context: str = Field(default="", description="額外上下文")

class LLMAnalyzeSkill(BaseSkill):
    skill_id = "llm_analyze"
    skill_type = SkillType.LLM
    description = "AI 數據洞察：KPI 異常解讀 + 趨勢分析 + 行動建議"
    input_schema = LLMAnalyzeInput
```

- 輸入結構化資料 + 問題 → 輸出分析報告

### llm_qa

```python
class LLMQAInput(SkillParam):
    """LLM QA 輸入參數。"""
    question: str = Field(description="使用者問題")
    context: str = Field(default="", description="額外上下文")

class LLMQASkill(BaseSkill):
    skill_id = "llm_qa"
    skill_type = SkillType.LLM
    description = "知識問答：Wiki + RAG 增強的 Q&A"
    input_schema = LLMQAInput
```

- 搭配 `wiki_rag_bridge` 自動注入 Wiki context

### parse_intent

```python
class ParseIntentSkill(BaseSkill):
    skill_id = "llm_parse_intent"
    skill_type = SkillType.LLM
    description = "使用 LLM 進行 12 意圖分類 + 參數抽取"
```

- 輸入自然語言 → 輸出 `{"intent": "skill_call", "skill_id": "xxx", "params": {...}}`
- 內建 keyword fallback（LLM 不可用時自動降級）

## 注意事項

- 所有 LLM 呼叫透過 GeminiAdapter 或 LLMAdapter，不直接呼叫 API
- temperature 依用途調整：摘要 0.3、分析 0.5、問答 0.7
- 長文本分段處理，避免 token 上限
