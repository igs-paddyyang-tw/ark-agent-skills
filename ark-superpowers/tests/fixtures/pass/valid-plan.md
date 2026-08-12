---
title: "通知系統執行計畫"
type: plan
status: draft
language: zh-TW
author: "paddyyang"
created: 2026-08-12
updated: 2026-08-12
related_design: "docs/designs/notification-design.md"
---

# 通知系統 — 執行計畫

## 1. 摘要

在 4 週內交付統一通知系統 MVP，涵蓋 Push/Email/In-app 三管道。

## 2. 里程碑（Milestones）

### Phase 1: 基礎架構（Week 1-2）

| # | 任務 | 角色 | 產出檔案 | 估時 | AC-ID | AC |
|---|------|------|----------|------|-------|-----|
| 1.1 | 建立 SQS FIFO Queue | coder | `infra/sqs.tf` | 2h | AC-001 | Queue 建立且可收發訊息 |
| 1.2 | Notification Service API | coder | `src/notification/api.py` | 4h | AC-002 | POST /notify 回 202 |
| 1.3 | Worker 框架 | ai-dev | `src/notification/worker.py` | 3h | AC-003 | Worker 可消費 SQS 訊息 |

**Phase 1 交付物**：
- [ ] SQS FIFO Queue 上線
- [ ] API 端點可用

### Phase 2: 管道整合（Week 3-4）

| # | 任務 | 角色 | 產出檔案 | 估時 | AC-ID | AC |
|---|------|------|----------|------|-------|-----|
| 2.1 | Email adapter | coder | `src/notification/adapters/email.py` | 2h | AC-004 | 寄送成功率 > 99% |
| 2.2 | Push adapter | coder | `src/notification/adapters/push.py` | 3h | AC-005 | FCM 推播 < 5s |
| 2.3 | 整合測試 [← 1.3] | qa | `tests/integration/test_notify.py` | 2h | AC-006 | 三管道全通過 |

**Phase 2 交付物**：
- [ ] 三管道全通
- [ ] 整合測試綠燈

## 3. 風險管理（Risk Management）

| 風險 | 機率 | 影響 | 緩解策略 | 觸發條件 |
|------|------|------|----------|----------|
| SQS FIFO 限流 | M | H | 監控 + 分 shard | msg/s > 250 |
| FCM 憑證過期 | L | H | 自動輪換 | 推播失敗率 > 10% |

## 4. 驗證標準（Verification Criteria）

| 類別 | 指標 | 目標 | 驗證方式 |
|------|------|------|----------|
| 單元測試 | 覆蓋率 | > 80% | pytest --cov |
| 整合測試 | 端到端 | 全通過 | CI pipeline |
| 效能 | 推播 P99 | < 5s | 壓測 |

## 5. 回滾計畫（Rollback Plan）

| 觸發條件 | 回滾步驟 | 預估時間 | 負責人 |
|----------|----------|----------|--------|
| 推播失敗率 > 20% | 切回舊管道 | 5 min | on-call |
