---
id: GKB-CORE-TRIGGER-001
title: 計數累積型觸發（collect-to-trigger）
type: pattern
domain: game-core
tags: [trigger, reward, game-loop]
trust: deterministic
status: mature
---
玩家在主玩法中累積特定物件（scatter / 金幣 / 擊殺數）到門檻即觸發 bonus。實作重點：進度條 UI 必須與伺服端計數同步；重連時需回填進度。
