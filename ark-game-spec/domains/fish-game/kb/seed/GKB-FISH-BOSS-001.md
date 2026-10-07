---
id: GKB-FISH-BOSS-001
title: Boss 魚出場與分段獎勵
type: pattern
domain: fish-game
tags: [boss, reward, trigger, jackpot]
trust: deterministic
status: mature
proposes:
  - {key: boss.reward_type, value: "分段倍率 + 最後一擊 jackpot 入口", confidence: medium}
---
Boss 定時出場，全房公告；血量分段給付倍率，最後一擊者觸發 jackpot 或轉盤。實作重點：多人房的最後一擊判定需伺服端仲裁。
