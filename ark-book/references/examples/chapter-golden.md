---
book: first-personal-agent
chapter: 3
slug: give-it-a-soul
title: "讓助理知道自己絕不做什麼：用 role-profile 寫人格檔"
type: chapter
level: beginner
est_minutes: 20
punchline: "人格不是形容詞，是一份寫著『絕不做什麼』的資料。"
objectives:
  - 用 ark-agent-role-profile 訪談出一份含 hard_stops 的 role-profile.yaml
  - 跑 profile_lint.py 並讀懂它報的錯
prerequisites: [design-the-team]
key_terms: [role-profile, hard_stops, stance]
tags: [agent-team, role-profile]
sources:
  - sources/agent-team-closed-loop-workflow.md
  - ark-agent-skills/ark-agent-role-profile/SKILL.md
trust: llm-distilled
confidence: high
status: published
---

# 讓助理知道自己絕不做什麼：用 role-profile 寫人格檔

> book: first-personal-agent · chapter: 3 · est: 20 min

## 這章要解決的問題

上一章你用 team-design 拿到了 team-spec.yaml，裡面有一個叫 `qa-worker` 的位子。現在要填它的人格。

你第一個念頭大概是打開 steering 檔，寫一句：「你是一位專業、嚴謹的遊戲測試工程師。」寫完看起來很像那回事。

然後你把一份 RTP 測試結果丟給它，它回你：「數值偏差在可接受範圍內，建議放行。」

問題來了。它憑什麼說「可接受」？樣本數多少？信賴區間呢？「建議放行」——放行這件事，是它可以決定的嗎？

「專業、嚴謹」四個字，一個字都沒有回答這些問題。形容詞不會約束行為。怎麼辦？

## 路線圖

這章分三步：

1. 先看清楚一份人格檔到底裝了什麼，為什麼「形容詞」不夠
2. 接著用 ark-agent-role-profile 訪談，把 `hard_stops` 逼出來
3. 最後跑 profile_lint.py，看它怎麼幫你抓漏

## 內文

### 把「你是誰」變成資料

假設你今天要交接工作給一位新同事，你不會只說「你要專業一點」。你會說：哪些事你可以直接做、哪些事要先問我、哪些事絕對不能碰。

一個 agent 的人格檔要裝的，就是這三層。

> [!ASK] 你可能會想說
> 那我在 system prompt 裡多寫幾句不就好了？
> 可以，但寫在 prompt 裡的東西沒辦法被 lint、沒辦法被別的 agent 讀、也沒辦法在下一位成員建助理時直接借走。寫成結構化資料，這三件事就都能做。

這份結構化資料，我們叫做 **role-profile**。白話講，role-profile 其實就是把「這個 agent 是誰、站哪邊、絕不做什麼」寫成 yaml 而已。

它有四個欄位：

| 欄位 | 回答的問題 | 例（qa-worker） |
|---|---|---|
| `identity` | 你是誰、負責什麼 | 遊戲數值測試 worker，負責 RTP 與機率驗證 |
| `stance` | 有爭議時你站哪邊 | 寧可多報一個假警報，不漏一個真偏差 |
| `hard_stops` | 絕不做什麼 | 放行決策只有人類能下；偏差判定必附樣本數與信賴區間 |
| `voice` | 說話的樣子 | 先給數字再給判斷；不用「應該沒問題」這類模糊詞 |

再換一個情境看。泰丞的競品分析助理，`stance` 是「引用要能回到原始來源」，`hard_stops` 是「沒有來源連結的情報不寫進報告」。欄位一樣，內容完全不同——這就是為什麼它是資料而不是一段散文：同一個模板，換內容就是另一個人。

簡單來說，role-profile 把人格從「形容詞」變成「可以被檢查的欄位」。好，這是第一步。

### hard_stops 是整份檔案最值錢的一行

四個欄位裡，`hard_stops` 最難寫，也最重要。

為什麼？因為 identity 和 voice 寫錯，agent 只是講話怪；hard_stops 寫錯，agent 會替人做決定。

> [!TIP] 白話
> 所謂 hard_stop，其實就是「就算使用者叫你做，你也要停下來說不行」的那條線。

ark-agent-role-profile 用訪談把它逼出來。它不會問你「hard_stops 是什麼」，它會問：

- 「這個 agent 最糟的一次出錯會長什麼樣？」
- 「那次出錯，是因為它做了什麼它不該做的事？」
- 「誰才有權做那件事？」

三個問題問完，「放行決策只有人類能下」就自己跑出來了。你會發現，hard_stops 從來不是憑空想的，它是「最糟情況」倒推回來的。

> [!ASK] 你可能會想說
> 那我多寫幾條 hard_stops 比較安全？
> 不是。每多一條，agent 就少一件能自己做的事。hard_stops 只放「做錯會傷到人或錢」的事。RTP 放行是；「回覆要用繁體中文」不是，那是 voice。

### 17 個角色庫：先借再改

ark-agent-role-profile 內建 17 個角色（coder、qa、devops、math-verifier、market-analyst……）。你的 qa-worker 不用從零寫，先套 `qa` 再改。

這也是圖書館的意思：庚霖寫好的 qa 人格檔，下一位做測試的成員直接借走，只改專案名和那幾條 hard_stops。

## 常見誤解

> [!MYTH] 大家通常會以為
> 人格檔寫得越詳細越好，最好把所有情境都列進去。但其實 role-profile 只管「你是誰、站哪邊、絕不做什麼、怎麼說話」四件事；「怎麼做事」是 skill 和 steering 的工作。把流程寫進人格檔，agent 換一個任務就整份失效。
> 所以記住：人格檔回答「是誰」，不回答「怎麼做」。

> [!MYTH] 大家通常會以為
> profile_lint.py 過了就代表人格寫得好。但其實 lint 只查結構：skills 引用存在、沒有 TODO 殘留、欄位齊全。「放行決策只有人類能下」寫成「盡量不要自己放行」，lint 照樣過——那是第 7 章 prompt-spec-validator 行為 eval 才抓得到的事。

## 動手做

> [!TRY] 動手做
> 1. 在你的 team 目錄跑訪談（standard 檔位）：
> ```bash
> python ark-agent-role-profile/scripts/interview.py --role qa --out roles/qa-worker.yaml
> ```
> 2. 打開 `roles/qa-worker.yaml`，確認 `hard_stops` 至少有一條是「誰才能做這個決定」。
> 3. 跑 lint：
> ```bash
> python ark-agent-role-profile/scripts/profile_lint.py roles/qa-worker.yaml
> ```
> 你應該看到：`PASS  roles/qa-worker.yaml  (4 fields, 0 TODO)`。
> 如果看到 `FAIL skills: ark-xxx not found`，代表你在 `skills` 欄引用了根目錄沒裝的 skill——回第 2 章的 skill 清單對一次。

做完後你手上會有 `roles/qa-worker.yaml`。把它 commit 進 repo，它就是圖書館裡下一位測試成員可以借走的那份人格檔。

## 重點回顧

- 人格不是形容詞，是一份寫著「絕不做什麼」的資料。
- hard_stops 從「最糟的一次出錯」倒推，只放做錯會傷人傷錢的事。
- lint 查結構、不查行為；行為驗收在第 7 章。

## 下一章

你現在有編制、有人格，但它們還是兩份 yaml。下一章用 ark-agent-init 把它們組進 `.kiro/steering/`，讓 agent 真的讀得到。
