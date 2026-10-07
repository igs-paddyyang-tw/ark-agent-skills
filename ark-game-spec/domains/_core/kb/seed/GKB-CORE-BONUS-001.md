---
id: GKB-CORE-BONUS-001
title: 轉盤 Bonus 通用 pattern
type: pattern
domain: game-core
tags: [bonus, wheel-bonus, reward]
trust: deterministic
status: mature
proposes:
  - {key: bonus.wheel.segments, value: "8-12 段，含一格 jackpot 入口", confidence: medium}
---
轉盤 bonus 在 slot / fish / fast 三類遊戲皆常見：觸發後進入獨立畫面，玩家或系統啟動轉盤，落點決定獎勵。
研發經驗：段數與獎勵權重由 math 決定，UI 需支援「假減速」動畫；跨 domain 可共用同一組狀態機（enter → spin → stop → award → exit）。
