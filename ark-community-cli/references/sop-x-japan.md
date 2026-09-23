# SOP：X／Twitter 日本社群訊息取得（X API v2 pay-per-use）

目標：用最少的錢，每天固定時窗把跟自家遊戲有關的日文貼文拉回 `raw/x/`；估量在先、預算硬上限、query 命名管理。

## 一次性設定（人做）

1. developer.x.com 建 Project + App，取 **Bearer Token**（app-only 即可，只讀）→ 環境變數 `X_BEARER_TOKEN`
2. Developer Console → Billing：買 credits，**設 spending limit**（建議先 $30／月）
3. 寫 query 清單到 `config.yaml`（命名管理，每條 query 有目的、有預算）：
   ```yaml
   x:
     daily_budget_usd: 1.5           # 腳本硬上限（$0.005/則 → 每天最多約 300 則）
     price_per_post_usd: 0.005       # 依官方價格更新
     default_max_posts: 200
     queries:
       - name: official-mentions      # 最穩：直接對官方講話的人
         query: '(@GameOfficialJP OR #ゲーム名) lang:ja -is:retweet'
         purpose: 自家玩家回饋
         surface: x
       - name: game-ja-pain           # 痛點探針：遊戲名 + 抱怨詞
         query: '"ゲーム名" (不具合 OR バグ OR 落ちる OR 改悪 OR 返金 OR 引退) lang:ja -is:retweet -is:reply'
         purpose: 負面訊號早期偵測
         surface: x
       - name: gacha-buzz             # 活動期才開
         query: '"ゲーム名" (ガチャ OR 爆死 OR 神引き) lang:ja -is:retweet min_likes:3'
         purpose: 活動反應
         surface: x
         enabled: false
   ```

## query 設計規則（日本市場）

- **底線**：`lang:ja -is:retweet`。2026-05 起關鍵字搜尋本來就不含轉推，但顯式寫上保險
- **錨點優先**：`@官方帳號`、官方 hashtag、`conversation_id:{官方公告貼文id}`（收某則公告底下的回覆）比遊戲名關鍵字乾淨十倍
- **遊戲名要加引號**，短縮寫（3 字以內）一定加限定詞，否則噪音吃掉預算
- **新算子省錢**：`min_likes:3` 或 `min_replies:1` 過濾掉沒人理的貼文；早期偵測用途才不加
- **回覆要不要收**：抱怨常在回覆裡，`-is:reply` 省錢但漏；官方 mention query 建議收回覆，探針 query 不收
- 日文詞庫（分類與 query 共用）：
  - 不具合系：不具合／バグ／落ちる／フリーズ／ログインできない／メンテ／お詫び
  - 課金・經濟：課金／返金／ガチャ／爆死／渋い／天井／石／改悪
  - 活動：イベント／周年／コラボ／ランキング／報酬
  - 離開：引退／退会／アンインストール／つまらない
  - 正向：神引き／神アプデ／楽しい／最高／ありがとう

## 每日流程（腳本做）

```bash
# 1. 估量（打 counts endpoint，不拉貼文）
python scripts/community_cli.py pull x --config community/config.yaml --query official-mentions --estimate
# → official-mentions: 近 7 天 412 則 / 日均 59 / 預估全拉 $2.06 / 今日預算剩 $1.50 → 建議 --max-posts 200

# 2. 拉取（增量：since_id 來自 state/x/{query}.cursor）
python scripts/community_cli.py pull x --config community/config.yaml --query official-mentions --max-posts 200
```

腳本行為（`scripts/x_pull.py`）：
1. 讀 `state/x/spend.jsonl` 算今日已花；≥ `daily_budget_usd` → 直接退出並回報
2. `--estimate`：`GET /2/tweets/counts/recent?query=...&granularity=day`，印每日則數與預估費用；**不寫 raw**
3. 拉取：`GET /2/tweets/search/recent?query=...&max_results=100&since_id={cursor}&tweet.fields=created_at,lang,public_metrics,conversation_id,in_reply_to_user_id,author_id&expansions=author_id&user.fields=username`
4. 每頁：寫 `raw/x/{query_name}/{YYYY-MM-DD}.jsonl`（貼文 + includes.users，這是唯一有 username 的層）→ 記 spend（回傳則數 × 單價）→ 更新 cursor 為 `newest_id`
5. 停止條件：`next_token` 沒了、達 `--max-posts`、或今日預算到頂（三者任一）
6. 429 → 讀 `x-rate-limit-reset` 睡到重置；402／403（credits 不足／權限）→ 立刻停
7. 結束印：`x/{query}: {n} 則 / ${cost} / 今日累計 ${total} / 預算剩 ${left}`

## 為什麼不用 filtered stream
即時串流適合大量、常駐；我們是「每天一次、幾百則、要省錢」，recent search + since_id 增量剛好。活動上線當天想盯即時，再臨時開 stream，事後關。

## 檢核
- [ ] 每條 enabled query 今天都跑過 estimate（有 log）
- [ ] `state/x/spend.jsonl` 今日合計 ≤ 預算
- [ ] raw/x/ 有檔；records/ 沒有 username（normalize 自掃）
- [ ] Console 帳單與腳本估算差距 < 20%（每週對一次；差太多代表 dedup 假設錯或價格變了）

## 常見錯誤
| 症狀 | 原因 | 處置 |
|---|---|---|
| 402 | credits 用完 | Console 充值；檢查是否有 retry loop 燒掉 |
| 結果幾乎全是無關貼文 | 遊戲名太短、沒引號 | 加引號 + 限定詞，先 estimate 看量 |
| 同一貼文每天重複出現 | 沒用 since_id | 檢查 cursor 是否寫入；24h 內重讀雖不重複計費，但跨日會 |
| 量突然暴增 | 炎上或炒作 | 探針 query 加 `min_likes:`；不要加預算追全量，抽樣即可 |
