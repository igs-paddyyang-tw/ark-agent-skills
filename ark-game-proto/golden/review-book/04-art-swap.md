---
book: huffnpuff-open-house-decision
chapter: 4
slug: art-swap
title: "R-4 美術：把競品素材換成正式美術"
type: chapter
level: intermediate
est_minutes: 10
punchline: "換皮不換骨：美術只改素材路徑，遊戲邏輯一行不動。"
objectives:
  - 說出試玩版素材可以單獨替換的範圍
  - 排定把競品素材換成正式美術的範圍與時程
prerequisites: [free-games]
key_terms: [素材總覽, assets_base]
tags: [slot, pipeline]
sources:
  - ../../game/pixi-client/stage.yaml
  - ../gdd-overview.html
trust: llm-distilled
confidence: high
status: review
---

# R-4 美術：把競品素材換成正式美術

## 這章要解決的問題

試玩版 `play.html` 看起來很完整：轉輪、房子、彩金列、Open House 的街景都有。但這些畫面素材來自競品影片，只能內部展示，不能拿出去。

要上線就得換成正式美術。換美術會不會又要改遊戲、重跑驗證？要準備多少張圖？

## 路線圖

1. 先看試玩版的素材怎麼和遊戲邏輯分開
2. 再用素材總覽確認要畫哪些東西
3. 最後在拍板欄排時程

## 內文

### 素材和邏輯是分開的

試玩版的遊戲邏輯（機率、規則、演出順序）寫在遊戲包裡；圖片從一個素材資料夾讀進來，位置由設定檔 `stage.yaml` 的 **assets_base** 指定。換美術只要把新圖放進新資料夾、改 assets_base 指過去，遊戲邏輯一行不動，前面的機率驗證也不用重做。

> [!ASK] 你可能會想說
> 那換完美術還要重新驗收嗎？
> 機率不用重驗；但要重跑一次真瀏覽器冒煙（ark-game-proto 的 smoke.js），確認每個情境的畫面都正常、沒有缺圖。

### 要畫哪些東西

要畫的清單在 **素材總覽**（拍板包裡的 `gdd-overview.html`）：一般圖騰、建材、房子框、彩金、各畫面版位，都有編號與說明，美術可以直接照單製作。

### 拍板欄

| 項目 | 決議 | 拍板人 | 日期 |
|---|---|---|---|
| R-4 正式美術時程 | （待拍板：交付日期與負責人） | | |

## 常見誤解

> [!MYTH] 大家通常會以為
> 換美術就要動遊戲程式、重做測試。但其實 Huff N' Puff Open House 的試玩版把素材與邏輯分開，換美術只改素材路徑；機率與規則的驗證結果不受影響。

## 動手做

1. 打開拍板包裡的 `gdd-overview.html`，瀏覽要製作的圖騰與畫面清單
2. 和美術確認交付日期，寫進本章拍板欄
3. 新圖到位後：改 `game/pixi-client/stage.yaml` 的 assets_base → 重新建置試玩版 → 跑 smoke.js 冒煙 → 重新發布拍板包

你應該看到：素材總覽裡每個圖騰都有編號與說明；換圖後 smoke.js 每個情境都是 PASS、0 頁面錯誤。

## 重點回顧

- 換皮不換骨：美術只改素材路徑，遊戲邏輯一行不動。
- 要畫的清單就是素材總覽。
- 換完只需重跑真瀏覽器冒煙，不必重驗機率。

## 下一章

四件事拍板完，附錄列出拍板包裡所有成品與驗收紀錄，供查核。
