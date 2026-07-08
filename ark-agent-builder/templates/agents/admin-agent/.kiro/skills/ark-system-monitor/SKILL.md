---
name: ark-system-monitor
description: |
  系統監控與狀態報告：檢查服務健康、費用統計、Agent 狀態。
  觸發：當使用者提到 狀態、status、健康、health、費用、costs。
---

# 系統監控 Skill

## 步驟
1. 檢查各 Agent 運行狀態
2. 統計今日費用和 API 呼叫次數
3. 檢查知識庫健康度（lint）
4. 產出狀態摘要報告

## 輸出格式
```
📊 系統狀態
├── Agents: N 個運行中
├── 今日費用: $X.XX
├── API 呼叫: N 次
└── Wiki 健康: ✅/⚠️
```
