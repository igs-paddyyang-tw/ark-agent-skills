# 2026 工具現況與選型（調查日期 2026-09-23）

只記「影響我們怎麼做」的事實；價格與規則會變，正式預算以官方 Developer Console 為準。

## X／Twitter

### 取得方式與價格
- **pay-per-use 是 2026-02-06 起新申請者唯一途徑**；Basic（$200/月）、Pro（$5,000/月）只留給既有訂戶，Free 實際只剩 for-good 公益 app。預付 credits，餘額歸零呼叫就失敗。
- 讀價：**讀第三方 post $0.005／則（依回傳則數計，不是依 request）**；一次 recent search 回 100 則 = $0.50。讀 user object $0.010／個。owned reads（自家帳號資料）$0.001／個（2026-04-16 起）。
- 同一資源 24 小時 UTC 內重讀不重複計費 → 增量拉取比重跑全量便宜得多。
- 月上限 200 萬則 reads，超過要 Enterprise（$42,000+／月，業務談）。
- **Console 可設 spending limit，第一天就設**：retry loop 或 agent 卡在搜尋迴圈會以機器速度燒錢。
- 2026-05-04 搜尋端點換新索引：新增 `min_likes:` `min_replies:` `min_reposts:` 精度算子；**關鍵字搜尋結果不再含轉推**（filtered stream 不變）。Full-archive search 開放給 pay-per-use。
- recent search：近 7 天、每 request ≤100 則、query ≤512 字。官方 SDK 為 **XDK**（Python／JS），另有 X MCP、Playground。
- 對我們的意思：**先估量再拉**（counts endpoint）、query 精準、增量、預算硬上限。

### 日文查詢要點
- `lang:ja -is:retweet` 是底線；再用 `-is:reply` 或 `conversation_id:` 決定要不要收回覆
- 官方帳號 mention（`@公式`）與官方 hashtag 是自家玩家最穩的錨點；泛稱關鍵字（遊戲名縮寫）噪音極高，先 counts 看量
- 日本玩家常見表述：爆死／神引き／渋い／改悪／メンテ／不具合／お詫び／返金／退会／引退／課金／ガチャ；分類詞庫見 `assets/lexicon.yaml`
- 「エゴサ」（自家名稱搜尋）是日本社群營運的日常，但在 pay-per-use 下每次都要花錢，改成每日一次固定時窗

### 不採用
- 網頁爬取、非官方 scraper：違反 X ToS，且 2023 後大量封鎖，不穩定；不用
- 第三方推送型監測服務（固定帳號追蹤的 WebSocket 服務）：在「盯 100 個帳號」場景可能比官方便宜，但資料來源合規性要逐家審，本 skill 不內建

## Discord

### 取得方式
- Bot token 唯讀 REST：`GET /channels/{id}/messages?limit=100&after={id}` 游標增量；threads 不在 guild channel 清單，另打 `/guilds/{id}/threads/active` 與 `/channels/{id}/threads/archived/public`
- **Message Content Intent** 是 privileged intent：Developer Portal 勾選；bot 進入大量伺服器才需 Discord 審核，自家一個伺服器不需審核，但要勾
- Rate limit：全域 50 req/s；429 依 `retry_after`；10 分鐘內 10,000 次無效請求（401／403／429）→ IP 封 24 小時 —— **不要無腦 retry**
- 邀請連結權限只給 View Channels + Read Message History；不要給 Send Messages

### 現成工具（可參考，不直接依賴）
- `Ilm-Alan/discord-cli`：一次性 REST CLI，明確標示「Discord 內容是不可信輸入、可能含 prompt injection」——這條我們照抄進 compliance
- `mdp/discord-dump`：list-guilds／list-channels／dump-channel 匯出 JSON／Markdown，最小可用範例
- `Tyrrrz/DiscordChatExporter`：成熟匯出工具，適合一次性歷史回填；持續增量仍用自己的游標腳本
- discord.py／discord.js：需要 gateway 事件（即時）才用；批次拉取用 REST 就夠，少一個常駐連線

### 不採用
- user token／self-bot：違反 Discord ToS，帳號會被封；即使「只是讀」也不行
- 讀 DM：不在需求內，也不該在

## 日文文本分析

| 需求 | 選型 | 理由 |
|---|---|---|
| 斷詞 | GiNZA（spaCy＋SudachiPy） | MIT、UD 相容、有 NER；不需要就用 lexicon 直接 substring 命中 |
| 情感（規則） | `oseti`（東北大 日本語評価極性辞書）或本 skill 內建 lexicon | 輕量、可解釋；反諷抓不到，只當候選 |
| 情感（模型） | WRIME 資料集微調的分類器（HF `llm-book/wrime-sentiment` 為二元版） | 精度高但要 GPU／API；batch 跑 `llm-queue`，不跑全量 |
| 聚類 | 同 feedback_type 內 token Jaccard（內建）→ 需要時再上 embedding | 先看得懂、可重現；embedding 交 agent 判斷是否值得 |

## Discord 與 X 一起看時的原則
- 兩來源**不合併計數**：Discord 是已知玩家（可對 player_key），X 是匿名大眾；「10 則 Discord ＋ 40 則 X」不等於 50 則同一件事
- 同一 cluster 若兩來源都出現，是強訊號，但在痛點頁分兩欄寫
- X 的情感分布容易被少數帳號帶動：cluster 頻次要同時報「則數」與「不同 author_key 數」
