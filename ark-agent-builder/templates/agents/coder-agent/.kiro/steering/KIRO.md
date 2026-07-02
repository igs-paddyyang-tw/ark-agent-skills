---
inclusion: always
---
# 💻 Coder Agent 行為規範

## 一、核心規則
1. PEP 8 + 型別標註：所有 Python 函式必須有完整 type hints
2. Async 優先：IO 操作一律使用 async/await
3. 日誌規範：使用 `structlog`，含 request_id 和 context
4. 錯誤處理：外部呼叫必須 try/except + 適當的回退策略
5. 文件完整：每個模組必須有 docstring，公開 API 必須有使用範例

## 二、禁止事項
1. 禁止使用 `print()` 替代正式日誌
2. 禁止提交含 TODO/FIXME 的程式碼到主分支
3. 禁止忽略 lint 警告（修復或標注抑制理由）
