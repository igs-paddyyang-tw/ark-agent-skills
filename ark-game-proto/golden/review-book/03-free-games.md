---
book: huffnpuff-open-house-decision
chapter: 3
slug: free-games
title: "R-3 範圍：Free Games（6 頂安全帽）要不要進 v1"
type: chapter
level: intermediate
est_minutes: 10
punchline: "多一個玩法不是加法，是把 RTP 預算重新分一次。"
objectives:
  - 說出 Free Games 進 v1 要付出的重工範圍
  - 決定 Free Games 是否進 v1
prerequisites: [odds-approve]
key_terms: [Free Games, RTP 預算]
tags: [slot, probability]
sources:
  - ../../spec/game-spec.v1.md
  - ../../quicktest/qt-report/rtp-report.json
trust: llm-distilled
confidence: high
status: review
---

# R-3 範圍：Free Games（6 頂安全帽）要不要進 v1

## 這章要解決的問題

競品影片裡，盤面出現 6 頂小豬安全帽會進 **Free Games**。但影片沒拍到 Free Games 的內容，所以遊戲規格書把它的三個關鍵規則——給幾次、能不能再觸發、有沒有倍數——標成 deferred（決議 D012～D014），v1 沒做。

現在要決定：v1 就加進去，還是留到之後？加進去會牽動什麼？

## 路線圖

1. 先看目前 RTP 預算怎麼分
2. 再看加入 Free Games 要重做哪些階段
3. 最後在拍板欄做決定

## 內文

### RTP 預算是固定的餅

總 RTP 目標 96%，這塊餅目前分成主遊戲 38.88% 與五種特色遊戲 57.11%。這種「把總 RTP 分給各玩法」的規劃，我們叫做 **RTP 預算**。

Free Games 要進來，就要從現有的某一塊切一部分給它。切誰、切多少，會改變第 1 章確認過的體感。

> [!ASK] 你可能會想說
> 那就讓 Free Games 很少出現、只佔一點點 RTP，影響應該不大吧？
> 佔比小影響確實小，但規則（次數、再觸發、倍數）還沒有任何依據，要先回遊戲規格書補決議，才能進機率設計。不是只調一個數字。

### 加進 v1 要重做的範圍

| 階段 | 要做的事 |
|---|---|
| ② 遊戲規格書 | 補 D012～D014 三個決議（需要補競品素材或自行設計） |
| ③ 機率規格書 | 重分 RTP 預算，推導 Free Games 參數 |
| ④ Go 快測 | 引擎加 Free Games、重跑 2,000 萬局 |
| ⑥ 驗證台 | huff-house 玩法模型加 Free Games，重做逐局對帳 |
| ⑦ 試玩版 | 加 Free Games 演出 |

### 拍板欄

| 項目 | 決議 | 拍板人 | 日期 |
|---|---|---|---|
| R-3 Free Games 是否進 v1 | （待拍板：建議 v1 不做） | | |

## 常見誤解

> [!MYTH] 大家通常會以為
> 多加一個玩法只是多一份內容。但其實在固定的 RTP 預算下，多一個玩法等於把整塊餅重切，前面驗證過的體感與機率都要重來。

## 動手做

1. 打開 `../spec/game-spec.v1.md`，搜尋 `D012`，看三個 deferred 決議的原文
2. 判斷現有五種特色遊戲（第 1 章）是否已經撐得起特色遊戲體驗
3. 在拍板欄寫下決定；若要進 v1，另開需求從遊戲規格書重跑

你應該看到：D012～D014 三條都標 deferred，旁邊沒有任何數值依據。

## 重點回顧

- 多一個玩法不是加法，是把 RTP 預算重新分一次。
- Free Games 的三個核心規則還沒有依據，進 v1 要從遊戲規格書重來。
- 建議 v1 不做，留給後續版本。

## 下一章

最後一章處理美術：試玩版目前用的是競品素材。
