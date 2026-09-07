---
inclusion: always
---
# Memory — 專案狀態

> 持久化上下文，避免每次重問。定期由使用者更新。

## 專案狀態（2026-07-15）

- 架構：TG Bot gateway + Gemini Chat + Agent CLI 派工
- 團隊：8 agents，派工由 Ark Agent 統一調度
- 開發模式：個人開發者，無正式 Sprint，按需求逐步迭代

## 技術決策

- 派工機制：dispatch_to_agent tool，由 Ark Agent ReAct Loop 決定
- Spec 格式：Markdown（背景/目標/驗收標準/技術約束）
- 驗收：功能驗證 + 邊界測試 + 文件完整度

## 踩坑紀錄

- 單一 Agent 不宜超過 3 個並行任務（context 會混亂）
