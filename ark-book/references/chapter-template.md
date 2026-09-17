# 章節骨架（複製後填寫；`<>` 內是填空提示，交付前不得殘留）

```markdown
---
book: <book-slug>
chapter: <N>
slug: <chapter-slug>
title: "<用讀者的話說這章教會他做什麼：動詞 + 對象 + 工具>"
type: chapter
level: beginner
est_minutes: 15
punchline: "<≤40 字，一週後還記得的一句>"
objectives:
  - <動詞開頭，可驗證>
prerequisites: []
key_terms: [<本章命名儀式引入的術語>]
tags: [<受控詞彙>]
sources:
  - sources/<file>.md
trust: llm-distilled
confidence: high
status: draft
---

# <title 同 frontmatter>

> book: <book-slug> · chapter: <N> · est: <M> min

## 這章要解決的問題

<讀者的具體情境：他在做什麼專案、下什麼指令、看到什麼結果。>
<他第一個會想到的做法。>
<這個做法在哪裡不夠——具體現象。>
怎麼辦？

## 路線圖

這章分三步：

1. 先 <…>
2. 接著 <…>
3. 最後 <…>

## 內文

### <第一個概念：用功能描述當標題，不用術語>

<直覺例子：比如說／假設你今天…>

> [!ASK] 你可能會想說
> <讀者此刻心裡的問題>
> <回答>

<命名儀式：「這個東西我們叫做 X（English term）。白話講，X 其實就是 … 而已。」>

<形式定義／規則／指令>

<第二個例子：不同情境>

簡單來說，<一句話收>。好，這是第一步。

### <第二個概念>

<同上循環>

## 常見誤解

> [!MYTH] 大家通常會以為
> <錯誤理解>。但其實 <正確理解>。為什麼？<原因>。
> 所以記住：<一句記憶點>。

## 動手做

> [!TRY] 動手做
> 1. <步驄>
> ```bash
> <指令>
> ```
> 你應該看到：<成功的樣子>。
> 如果看到 <X>，代表 <Y>，處理方式：<Z>。

做完後你手上會有：<產出物路徑> —— 這就是你為圖書館新增的一本館藏／一支腳本。

## 重點回顧

- <punchline>
- <第二句>
- <第三句，選用>

## 下一章

<一句話：這章有了什麼，還缺什麼，下一章補什麼。>
```

## 序（00-preface.md）骨架

```markdown
---
book: <slug>
chapter: 0
slug: preface
title: "序：為什麼有這本書"
type: preface
level: beginner
est_minutes: 5
punchline: "<全書一句話>"
objectives:
  - 判斷自己是不是這本書的讀者
tags: [<…>]
sources: []
trust: llm-distilled
confidence: high
status: draft
---

# 序：為什麼有這本書

## 為什麼有這本書
<一個真實的起點：誰在什麼情境下卡住，這本書把他走通的路寫下來。>

## 這本書給誰
<audience 展開；也說誰不用讀。>

## 讀完你會
<outcomes 逐條，動詞開頭。>

## 全書路線圖
<每章一句話；為什麼是這個順序（讀者遇到問題的順序）。>

## 這本書不講
<scope_out 展開，並指向該去哪裡看。>
```

## 附錄骨架（99-appendix-*.md）

`type: appendix`，七段中「動手做」「下一章」可省。常見附錄：術語表（每條：術語｜英文｜一句白話｜首次出現章節）、指令速查表、練習解答、詞彙表建議（提議新增的 wiki tags）。
