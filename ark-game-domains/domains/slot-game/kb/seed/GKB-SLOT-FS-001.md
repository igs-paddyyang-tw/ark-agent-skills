---
id: GKB-SLOT-FS-001
title: Free Spin 標準觸發與 Retrigger
type: pattern
domain: slot-game
tags: [free-spin, scatter, trigger, retrigger]
trust: deterministic
status: mature
proposes:
  - {key: free_spin.count_awarded, value: 10, confidence: medium}
  - {key: free_spin.retrigger, value: true, confidence: medium}
---
3 scatter 觸發 10 次免費遊戲、free spin 內再出 3 scatter 加 5 次，是市場最常見配置。歷史專案 Slot-A 採此配置；Slot-B 把 retrigger 關掉以壓 volatility。
