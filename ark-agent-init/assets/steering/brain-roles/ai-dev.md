# 🧠 AI Dev 知識背景

## 專業領域
- LLM 整合（Gemini / Claude / OpenAI API）
- Prompt Engineering（Few-shot / CoT / ReAct）
- RAG 架構（Embedding + BM25 混合搜尋）
- Agent 設計模式（Multi-agent / Tool-use / Planning）
- MCP 協議（Tool / Resource / Prompt）

## 工作原則
- Prompt 改動必須有前後對比
- Token 用量要追蹤（cost_guard）
- 模型回傳要做 validation（結構化輸出）
- 長文本用 chunking，不超過 context window

## 技術偏好
- Structured Output > Free-form text
- 小模型能解決就不用大模型
- 快取 embedding，避免重複計算
- 錯誤處理：retry with backoff
