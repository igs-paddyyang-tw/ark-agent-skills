---
title: "跨 Agent 通訊模式"
type: concept
tags: [communication, collaboration, protocol, chain-of-command]
created: {{TODAY}}
updated: {{TODAY}}
status: mature
---

# 跨 Agent 通訊模式

## 指揮鏈

```
使用者 → admin（服務管理）
使用者 → leader（業務入口）→ worker（執行）→ leader（整合）→ 使用者
```

## 角色權限

| 角色 | 可發給 | 可用通訊工具 |
|------|--------|-------------|
| admin | 所有人 | send_to_instance / delegate_task / broadcast_all |
| leader | 所有人（除 admin） | send_to_instance / delegate_task / broadcast_all |
| worker | leader + 其他 worker | send_to_instance（無 delegate_task / broadcast_all） |

## 通訊模式

### 1. 派工模式（Leader → Worker）

```
delegate_task(instance="coder-agent", task="""
📋 任務：實作使用者 API
📄 規格：specs/user-api-spec.md（第 3 節）
🎯 你負責：REST API + DB schema
📁 範圍：src/api/users.py
⏰ 優先級：高
📎 依賴：無
✅ 驗收：pytest 通過 + API 可呼叫
📏 大小：M
""")
```

### 2. 回報模式（Worker → Leader）

```
send_to_instance(instance="pm-agent", msg="""
✅ 工作成果：使用者 API 已完成（5 個端點）
📚 學習結果：FastAPI 的 Depends 注入模式
⚠️ 阻礙：無
📋 下一步：等待 QA 驗證
""")
```

### 3. 求助模式（Worker → Worker）

```
send_to_instance(instance="ai-dev-agent", msg="""
需要你的幫助：Prompt 工程問題
我在實作 summarize 工具，但 Gemini 回覆太長。
能否幫我優化 system prompt？
相關檔案：src/tools/summarize.py
""")
```

### 4. 廣播模式（Admin/Leader → All）

```
broadcast_all(message="📢 系統維護通知：15 分鐘後重啟，請儲存進度。")
```

### 5. 私下回報（Worker → Leader，不給使用者看）

```
log_to_leader(text="⚠️ Gemini API 回傳 429 Too Many Requests，已自動重試 2 次。")
```

## 禁忌

| ❌ 禁止行為 | 正確做法 |
|-------------|---------|
| Worker 直接 reply 使用者 | 先 send 給 leader 整合 |
| 把 stack trace 丟給使用者 | log_to_leader 私下回報 |
| 跳級回報（worker → admin） | 走 worker → leader → admin |
| 廣播不相關訊息 | 只有重要公告才用 broadcast |
| 無格式派工 | 必須用標準派工格式 |

## 退回規則

- Worker 結果不合格 → Leader 退回並說明原因
- 退回單級不跳關
- 同一關失敗 3 次 → 升級上級處理

## 訊息長度限制

| 場景 | 限制 |
|------|------|
| reply（TG） | ≤ 4096 字元（建議 ≤ 150） |
| send_to_instance | 無硬限制（建議 ≤ 2000） |
| delegate_task | 無硬限制（建議含完整格式） |
| broadcast_all | ≤ 500 字（簡潔公告） |
