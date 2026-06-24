---
title: "系統升級路徑"
type: concept
tags: [upgrade, migration, roadmap, evolution]
created: {{TODAY}}
updated: {{TODAY}}
status: developing
---

# 系統升級路徑

## 當前階段

本專案由 `ark-agent-team-builder` Skill 產出，為 **Stage 0（精簡版）**。

## 升級路徑總覽

| Stage | 名稱 | 新增能力 | 觸發條件 |
|-------|------|---------|---------|
| 0 | 精簡版（當前） | 7 模組 + 10 MCP tools | — |
| 1 | Telegram 深度整合 | session + router + planner | 互動需求增加 |
| 2 | 監控與風控 | cost_guard + failure_memory | 成本或穩定性問題 |
| 3 | 知識演化 | wiki_query + skill_growth | 知識需累積重用 |
| 4 | pip 套件化 | CLI 入口 + semver | 需多環境部署 |
| 5 | Web 觀測面板 | WebSocket + Dashboard | 需視覺化監控 |

## 升級決策

```
團隊剛建立 → 留在 Stage 0（穩定 1~2 週）
  ↓
Telegram 互動不夠智慧？ → 升級到 Stage 1
Agent 花太多錢或常崩潰？ → 升級到 Stage 2
知識不斷重複解決？ → 升級到 Stage 3
需要發布到其他機器？ → 升級到 Stage 4
老闆要看 Dashboard？ → 升級到 Stage 5
```

## 參考文件

完整遷移步驟見知識庫外部文件：
- Skill references: `migration-guide.md`
- 成熟套件原始碼：`ark-team-agent` (pip)

## 注意事項

- 每個 Stage 獨立可用，不需一次升級到最終
- Stage 0 → 1 改動最小（加 3 個檔案）
- Stage 4 改動最大（目錄重構）
- 建議每個 Stage 穩定運行 1 週以上再升級
