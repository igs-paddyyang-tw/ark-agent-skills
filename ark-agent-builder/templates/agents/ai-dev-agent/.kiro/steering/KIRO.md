---
inclusion: always
---
# 🧠 AI Dev Agent 行為規範

## 一、核心規則
1. Prompt 版本化：每個 Prompt 必須有版本號，修改時建立新版本而非覆蓋
2. 模型選擇：優先考慮成本效益比，記錄選型理由
3. 評估方法：新 Prompt 必須跑至少 5 個測試案例才算完成
4. Skill 結構：遵循 `name / description / parameters / execute` 四段式
5. 安全優先：所有 LLM 呼叫必須有 timeout 和 fallback 機制

## 二、禁止事項
1. 禁止未測試就交付 Prompt
2. 禁止在程式碼中明文存放模型 API 金鑰
3. 禁止跳過成本評估直接使用最貴模型


## 知識庫存取

查詢知識時，依以下優先順序搜尋：

1. **私有知識**：`knowledge/raw/` 和 `knowledge/wiki/`（你自己的記憶）
2. **共用知識**：`knowledge/shared/wiki/`（所有 Agent 共用的通用知識）
3. **專案知識**：`knowledge/{project}/wiki/`（特定專案知識）

寫入新記憶時，寫到 `knowledge/raw/`（私有）。
引用知識時，標註來源層級：`[私有]`、`[共用]`、`[專案名]`。
