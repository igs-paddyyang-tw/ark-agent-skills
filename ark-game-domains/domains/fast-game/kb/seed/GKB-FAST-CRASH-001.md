---
id: GKB-FAST-CRASH-001
title: Crash 類回合時序與 cashout
type: pattern
domain: fast-game
tags: [crash, round-timing, cashout, auto-cashout]
trust: deterministic
status: mature
proposes:
  - {key: round.betting_window_s, value: 5, confidence: medium}
---
下注窗 5 秒 → 曲線上升（爆點由伺服端種子決定）→ 爆點後 3 秒結果停留。UI 重點：cashout 延遲補償與 auto-cashout 門檻同步。
