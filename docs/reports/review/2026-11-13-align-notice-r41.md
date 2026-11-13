---
title: "Alignment Notice — skill 破壞性升版"
type: review
subject: "skills-2026.11-r41"
date: 2026-11-13
author: ark-skills-sync/notice_build.py
source_skill: ark-skills-sync
verdict: needs-work
confidence: high
tags: [alignment, breaking-change, skills-sync]
sources: ["check_consumers（消費端掃描）", "pre-push major 偵測"]
findings: {p0: 0, p1: 1, p2: 0, p3: 0}
recipients: ["fish-team-agent", "game-team-agent", "nana-bot", "ninja-bot", "slot-team-agent", "slotverse-team-agent", "wukong-bot"]
affected: ["fish-team-agent", "game-team-agent", "nana-bot", "ninja-bot", "slot-team-agent", "slotverse-team-agent", "wukong-bot"]
---

# Alignment Notice — skill 破壞性升版

## Verdict

列車 `skills-2026.11-r41` 含 **1** 個破壞性升版，影響 **7** 個消費端部署。消費端需依下方 Actions 執行 `skills_sync` 對齊——判定 **needs-work**（需行動，非資料損毀）。

## Findings

| ID | 嚴重度 | skill | 從 | 到 | 遷移指引 |
|----|--------|-------|-----|-----|----------|
| F-1 | P1 | ark-skills-align | 2.16.0 | 3.0.0 | 已 deprecated，見該 stub 的 SKILL.md |

## Evidence

- **E-1**（支持 F-1）：`check_consumers --name ark-skills-align` 掃出 7 個已部署複本仍為舊版；pre-push 偵測到 major 升版 2.16.0 → 3.0.0。

## Actions

| ID | 動作 | 對應 Finding | 負責 |
|----|------|--------------|------|
| A-1 | 在專案根 `skills_sync.py status`（ark-skills-sync；沒裝就用上游 clone 那支），看缺少／空殼／舊名／STALE／LOCAL | F-1 | 各消費端 manager／admin |
| A-2 | `skills_sync.py update --apply`（補裝接手者與空殼、對齊 STALE；LOCAL 先判斷）；舊名用 `--prune` 或 `remove`，並改掉 SOUL／矩陣裡的舊名 | F-1 | 各消費端 manager／admin |
| A-3 | 再跑 `status` 全 ✅（或只剩已知 LOCAL）＋反證；pathspec 提交進自己的 repo | F-1 | 各消費端 manager／admin |

## 邊界聲明

- 本通知僅宣告破壞性升版與影響面，**不代消費端執行 sync**（各 manager 自行決定時機）。
- `affected` 清單為 `check_consumers` 掃描當下的部署複本，實際狀態以各端 `skills_sync.py status` 為準。
- 消費端若已透過 `policy: sync` 於重啟時自動重建，可能已對齊，無需重複 apply。
