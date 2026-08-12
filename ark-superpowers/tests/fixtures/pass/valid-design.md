---
title: "通知系統設計文件"
type: design
status: proposed
language: zh-TW
author: "paddyyang"
created: 2026-08-12
updated: 2026-08-12
related_spec: "docs/specs/notification-spec.md"
---

# 通知系統 — 設計文件

## 1. 概述（Overview）

本文件描述通知系統的技術設計方案，涵蓋架構決策與降級策略。

## 2. 背景（Context）

- 相關 Spec：`docs/specs/notification-spec.md`
- 目前系統使用三套獨立通知管道

## 3. 架構決策（Architecture Decisions）

### 選項 A: Event-Driven（Kafka）

- 優點：高吞吐、解耦
- 缺點：營運複雜度高
- 預估成本：$200/mo

### 選項 B: Queue-Based（SQS）

- 優點：免維運、與 AWS 整合
- 缺點：Fan-out 需額外設計
- 預估成本：$50/mo

### 選項 C: Direct Push（WebSocket）

- 優點：低延遲、即時
- 缺點：連線管理複雜
- 預估成本：$100/mo

**決策**：選擇方案 B（SQS），因成本最低且免維運。

## 4. 系統架構（System Architecture）

### 4.1 高層架構圖

```text
[API Gateway] → [Notification Service] → [SQS] → [Workers]
                                                      ↓
                                              [Push/Email/In-app]
```

## 5. 故障隔離與降級策略（Failure Isolation）

| 故障場景 | 影響範圍 | 降級行為 | 恢復方式 |
|----------|----------|----------|----------|
| SQS 斷線 | 即時推播暫停 | 寫入 DLQ 待重送 | 自動重試 |
| Worker crash | 部分管道中斷 | 其他管道照常 | Auto-scaling |

## 6. 安全性考量（Security）

- 所有 API 需 JWT 認證
- 通知內容加密儲存

## 7. 可觀測性（Observability）

- Metrics：推播延遲 P99、失敗率
- Logging：結構化 JSON log
- Alerting：失敗率 > 5% 觸發 PagerDuty
