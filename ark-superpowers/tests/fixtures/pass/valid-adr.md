---
title: "選擇 SQS 作為通知佇列"
type: adr
status: proposed
language: zh-TW
author: "paddyyang"
created: 2026-08-12
adr_number: "001"
related_spec: "docs/specs/notification-spec.md"
---

# ADR-001: 選擇 SQS 作為通知佇列

## 背景

通知系統需要一個可靠的訊息佇列來解耦 API 層與推播 Worker，
目前候選方案有 Kafka、SQS、RabbitMQ。

## 選項

### 選項 A: Kafka

- 優點：高吞吐、日誌持久
- 缺點：營運複雜、需 Zookeeper
- 預估成本：$200/mo

### 選項 B: SQS

- 優點：全託管、按量計費、與 Lambda 整合好
- 缺點：無序列保證（需 FIFO 版本）
- 預估成本：$50/mo

## 決策

選擇 **選項 B（SQS FIFO）**。

理由：
1. 免維運，團隊人力有限
2. 成本低 4 倍
3. 與現有 AWS 基礎設施無縫整合

## 後果

### 正面

- 降低營運負擔
- 成本可預測

### 負面

- 單一雲端鎖定
- FIFO 有 300 msg/s 限制

### 風險

- 流量超過 FIFO 限制時需改用 Standard + 冪等 Worker
