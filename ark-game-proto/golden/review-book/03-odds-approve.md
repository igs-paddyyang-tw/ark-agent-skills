---
book: huffnpuff-open-house-decision
chapter: 3
slug: odds-approve
title: "R-2 定版：正式機率 kb-v1 能不能從 candidate 升為 approved"
type: chapter
level: intermediate
est_minutes: 15
punchline: "逐局零誤差證明規則一致，快測 confirmed 才證明機率對。"
objectives:
  - 讀懂快測三向判定、驗證台精算、逐局對帳三種證據各證明什麼
  - 判斷正式機率 kb-v1 是否可以從 candidate 升為定版
prerequisites: [feel-check]
key_terms: [kb-v1, 三向判定, 逐局對帳]
tags: [slot, probability]
sources:
  - ../../quicktest/qt-report/rtp-report.json
  - ../../quicktest/odds/odds_1.0.0.json
  - ../../proto/README.md
  - ../checks/proto-browser-check.json
trust: llm-distilled
confidence: high
status: review
---

# R-2 定版：正式機率 kb-v1 能不能從 candidate 升為 approved

## 這章要解決的問題

Huff N' Puff Open House 的正式機率設定檔 `odds_1.0.0.json`，目前標記是 `status: candidate`。⑧ Game Server 和 ⑦ 試玩版都已經在用它，可是它還沒被正式定版。

如果現在不定版，下游可能有人改了一個數字，大家都不知道；如果太早定版，之後發現體感不對，又要推翻。什麼時候可以定、要看哪些證據才能放心定？

## 路線圖

1. 先分清楚三種證據各自證明什麼
2. 再看 kb-v1 在三種證據上的結果
3. 最後在拍板欄決定是否升為 approved

## 內文

### 三種證據，三個不同的問題

這套正式機率參數我們叫做 **kb-v1**：kb 代表參數由知識庫手法推導，v1 是第一版。它經過三道驗證，每一道回答不同的問題。

| 證據 | 回答的問題 | kb-v1 結果 |
|---|---|---|
| Go 快測 **三向判定** | 機率數字是否達標（RTP、觸發率、倍數分布） | 2,000 萬局 RTP 95.99%（95% 信賴區間 95.60%～96.38%），第二個 seed 96.04%；verdict confirmed |
| 驗證台 L1 精算 | 規格書寫的規則算回來是否等於快測 | 總 RTP 95.85%、五種玩法頻率差 ≤ 0.8%、均倍都在信賴區間內 |
| **逐局對帳** | 兩套程式是否照同一套規則跑 | 驗證台引擎 ⇄ Go 40 萬局 0 不一致；試玩版 ⇄ Go 正式機率 12 萬局 0 不一致 |

另外檢核表 v5 的兩條極端值門檻也過了：主菜 1,000 倍以上佔 RTP 1.59%（門檻 < 3%）、主菜 10 倍以下佔次數 0.00%（門檻 < 10%）。

> [!ASK] 你可能會想說
> 逐局零誤差都做到了，還需要快測嗎？
> 需要。逐局對帳只證明兩套程式「一樣」，如果規格本身參數就錯，兩套會一樣錯。機率對不對，要看快測三向判定。

### 拍板欄

| 項目 | 決議 | 拍板人 | 日期 |
|---|---|---|---|
| R-2 kb-v1 升 approved | （待拍板：建議 R-1 通過後即升） | | |

## 常見誤解

> [!MYTH] 大家通常會以為
> 兩套引擎逐局零誤差，代表機率是對的。但其實零誤差證明的是「規則實作一致」，不是「機率正確」；機率正確要看快測三向判定 confirmed，兩者缺一不可。

## 動手做

1. 打開 [⑥ 驗證台 ↗](../proto.html)，看「L1 精算」分頁的五種玩法表
2. 切到「Go 對照」分頁，確認兩個 seed 各 20 萬局不一致都是 0
3. R-1 體感通過後，在拍板欄寫「kb-v1 升 approved」；工程端把 `odds_1.0.0.json` 的 `_meta.status` 改為 approved

你應該看到：L1 精算五列都是 PASS，Go 對照兩列的「差異」都是 0。

## 重點回顧

- 逐局零誤差證明規則一致，快測 confirmed 才證明機率對。
- kb-v1 三道驗證全過，只差 R-1 體感這一關。
- 定版後任何數字改動都要重跑快測與對帳。

## 下一章

機率定版之後，下一章決定要不要在 v1 加入 Free Games。
