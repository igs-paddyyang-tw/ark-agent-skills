---
title: "自動化部署系統"
type: one-pager
status: draft
language: zh-TW
created: 2026-08-12
upgraded_to: null
---

# 自動化部署系統 — One Pager

## 問題與目標

目前部署靠手動 SSH 執行腳本，每次耗時 30 分鐘且容易出錯。
目標是建立一鍵部署管線，將部署時間縮短到 5 分鐘以內。

## 方案

使用 GitHub Actions + Docker + ArgoCD 建立 GitOps 管線。

| 方案 | 優點 | 缺點 |
|------|------|------|
| A: Jenkins | 成熟生態 | 維運負擔重 |
| B: GitHub Actions + ArgoCD | 免維運、GitOps | 學習曲線 |

**決策**：選擇方案 B，因為團隊已用 GitHub，且 ArgoCD 可實現聲明式部署。

## 執行計畫

| 階段 | 內容 | 交付物 |
|------|------|--------|
| Phase 1 | CI Pipeline 建立 | .github/workflows/*.yaml |
| Phase 2 | Docker 化所有服務 | Dockerfile × 3 |
| Phase 3 | ArgoCD 上線 | k8s manifests + ArgoCD app |

## 風險與驗收

**風險**：
- ArgoCD 學習曲線 → 緩解：安排 1 週學習 sprint

**驗收條件**：
- [ ] push to main 後 5 分鐘內自動部署完成
- [ ] 回滾 < 2 分鐘
