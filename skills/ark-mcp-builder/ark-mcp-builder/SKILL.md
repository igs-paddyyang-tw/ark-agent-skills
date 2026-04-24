---
name: ark-mcp-builder
description: |
  建立高品質 MCP（Model Context Protocol）Server 的指南，
  讓 LLM 能透過設計良好的 Tools 與外部服務互動。
  使用此 Skill 當需要建立 MCP Server 整合外部 API 或服務，
  無論是 Python（FastMCP）或 Node/TypeScript（MCP SDK）。
---

# MCP Server 開發指南

## 概述

建立 MCP（Model Context Protocol）Server，讓 LLM 能透過設計良好的 Tools 與外部服務互動。
MCP Server 的品質取決於它能多好地幫助 LLM 完成真實世界的任務。

---

## 高層工作流程

### 階段 1：深度研究與規劃

#### 1.1 理解現代 MCP 設計

- **API 覆蓋 vs 工作流 Tools**：平衡全面的 API 端點覆蓋與專用工作流 Tools。不確定時優先選擇全面的 API 覆蓋。
- **Tool 命名與可發現性**：清晰、描述性的名稱。使用一致的前綴（如 `github_create_issue`）和動作導向命名。
- **Context 管理**：設計回傳聚焦、相關資料的 Tools。支援篩選/分頁。
- **可操作的錯誤訊息**：錯誤訊息應引導 agent 找到解決方案。

#### 1.2 研究 MCP 協議文件

從 sitemap 開始：`https://modelcontextprotocol.io/sitemap.xml`
用 `.md` 後綴取得 Markdown 格式頁面。

#### 1.3 研究框架文件

**建議技術棧**：
- **語言**：TypeScript（推薦）或 Python
- **傳輸**：遠端用 Streamable HTTP，本地用 stdio

**框架文件**：
- TypeScript SDK：`https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/main/README.md`
- Python SDK：`https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md`

#### 1.4 規劃實作

- 檢視服務的 API 文件，識別關鍵端點、認證需求、資料模型
- 列出要實作的端點，從最常用的操作開始

### 階段 2：實作

#### 2.1 建立專案結構

依語言選擇對應指南設定專案。

#### 2.2 實作核心基礎設施

建立共用工具：
- API Client（含認證）
- 錯誤處理輔助函式
- 回應格式化（JSON/Markdown）
- 分頁支援

#### 2.3 實作 Tools

每個 Tool 需要：

- **輸入 Schema**：使用 Zod（TypeScript）或 Pydantic（Python），含約束與清晰描述
- **輸出 Schema**：盡可能定義 `outputSchema` 提供結構化資料
- **Tool 描述**：功能摘要、參數描述、回傳型別
- **實作**：async/await I/O、可操作的錯誤訊息、支援分頁
- **標註**：`readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint`

### 階段 3：審查與測試

- 無重複程式碼（DRY 原則）
- 一致的錯誤處理
- 完整的型別覆蓋
- 清晰的 Tool 描述

**TypeScript**：`npm run build` 驗證編譯 → MCP Inspector 測試
**Python**：`python -m py_compile` 驗證語法 → MCP Inspector 測試

### 階段 4：建立評估

實作完成後，建立全面的評估測試 MCP Server 的有效性。

#### 評估要求

建立 10 個評估問題，每個問題必須：
- **獨立**：不依賴其他問題
- **唯讀**：僅需非破壞性操作
- **複雜**：需要多次 Tool 呼叫與深度探索
- **真實**：基於真實使用案例
- **可驗證**：單一、明確的答案
- **穩定**：答案不會隨時間改變

#### 輸出格式

```xml
<evaluation>
  <qa_pair>
    <question>問題描述</question>
    <answer>答案</answer>
  </qa_pair>
</evaluation>
```

## 注意事項

- TypeScript 為推薦語言（SDK 支援度高、靜態型別、良好的 linting）
- 遠端 Server 使用 Streamable HTTP（無狀態 JSON，易於擴展）
- 本地 Server 使用 stdio
- Tool 命名使用一致前綴 + 動作導向
- 錯誤訊息必須可操作，引導 agent 找到解決方案
