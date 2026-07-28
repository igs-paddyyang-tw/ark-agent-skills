---
name: ark-task-planning
description: |
  任務規劃與派工：需求分析 → 拆解子任務 → 指派 Agent → 追蹤進度。
  觸發：當使用者提到 規劃、plan、拆解、assign、派工、任務。
---

# 任務規劃 Skill

## 步驟
1. 分析需求（確認目標、範圍、驗收條件）
2. 拆解為子任務（每個標記 S/M/L 大小）
3. 匹配最適 Agent（根據能力標籤）
4. 產出任務清單（含指派和預估時間）
5. 追蹤進度（pending → assigned → done）

## 輸出格式
```
📋 任務規劃
├── T-001 [S] 抓取新聞 → market-agent
├── T-002 [M] 數據分析 → data-agent
└── T-003 [S] 產出報告 → report-agent
```
