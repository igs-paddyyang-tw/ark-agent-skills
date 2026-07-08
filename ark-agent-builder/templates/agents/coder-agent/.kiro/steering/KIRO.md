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



## 知識庫三層架構

查詢知識時，依以下優先順序搜尋：

1. **私有知識**：`knowledge/raw/` 和 `knowledge/wiki/`（你自己的記憶）
2. **共用知識**：`../../knowledge/shared/wiki/`（所有 Agent 共用的通用知識）
3. **專案知識**：`../../knowledge/{project}/wiki/`（特定專案知識）

> Agent 的 cwd 在 `agents/{name}-agent/`，全域知識庫在根目錄 `knowledge/`，
> 用 `../../knowledge/` 往上跳兩層存取。

寫入新記憶 → `knowledge/raw/`（私有）。
引用知識時，標註來源層級：`[私有]`、`[共用]`、`[專案名]`。
