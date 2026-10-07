---
id: GKB-SLOT-HW-001
title: Hold & Win（金幣鎖定重轉）
type: pattern
domain: slot-game
tags: [hold-win, respin, bonus, jackpot, trigger]
trust: deterministic
status: mature
proposes:
  - {key: bonus.hold_win.initial_respins, value: 3, confidence: medium}
---
6 個金幣符號觸發；每次新增金幣重置 respin 數；填滿全盤給 grand jackpot。實作經驗：金幣面額分佈與 jackpot 入口機率是 math 的核心參數，UI 需支援金幣鎖定動畫與重置計數。
