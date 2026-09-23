# SOP：Discord 訊息取得（自家伺服器，bot 唯讀）

目標：每天（或每小時）把白名單頻道的新訊息增量拉回 `raw/discord/`，不漏、不重、不越權、不留 PII 在下游。

## 一次性設定（人做，約 20 分鐘）

1. Developer Portal 建 Application → Bot → Reset Token，token 放環境變數 `DISCORD_BOT_TOKEN`（不進 git、不進 config.yaml）
2. Bot → Privileged Gateway Intents → 勾 **Message Content Intent**（不勾 Presence、Server Members）
3. OAuth2 URL Generator：scope `bot`，權限只勾 **View Channels、Read Message History**；用產生的連結邀進自家伺服器
4. 伺服器端：在要蒐集的頻道確認 bot 角色可見；不給 bot 看 staff／內部頻道
5. 取頻道 ID：Discord 開發者模式 → 右鍵頻道 → Copy Channel ID；寫進 `config.yaml`：
   ```yaml
   discord:
     guild_id: "123456789012345678"
     channels:
       - { id: "111...", name: feedback,    surface: discord, feedback_hint: null }
       - { id: "222...", name: bug-report,  surface: discord, feedback_hint: bug }
       - { id: "333...", name: general,     surface: discord, feedback_hint: null, sample_rate: 0.3 }
     include_threads: true
     backfill_days: 30          # 首次回填；之後只增量
   ```
   `feedback_hint` 讓 classify 對該頻道給預設分類（#bug-report 進來的先當 bug）；`sample_rate` 讓閒聊頻道只抽樣

## 每日流程（腳本做）

```bash
python scripts/community_cli.py pull discord --config community/config.yaml
```

腳本行為（`scripts/discord_pull.py`）：
1. 讀 `state/discord/{channel_id}.cursor`（沒有 → 用 `backfill_days` 算 snowflake 起點）
2. `GET /channels/{id}/messages?limit=100&after={cursor}`，直到回傳 < 100 則
3. `include_threads` 時另打 `/guilds/{guild}/threads/active`，對屬於白名單頻道的 thread 同樣增量
4. 每頁原樣寫 `raw/discord/{channel_name}/{YYYY-MM-DD}.jsonl`（一則一行，含 author 物件——這是唯一有 PII 的層）
5. 每頁成功後更新 cursor 為最大 message id（**先寫檔再推游標**，中斷可續）
6. 429 → 讀 `retry_after` 睡再試（最多 5 次）；401／403 → 立刻停、報錯、不重試；其餘 5xx → 指數退避 3 次
7. 結束印：`discord: {channels} 頻道 / {n} 則新訊息 / {threads} threads / 429 x{k}`

## 訊息類型處理
- `type` 非 0（DEFAULT）／19（REPLY）的系統訊息（加入、pin、boost）跳過
- bot 自己或其他 bot 的訊息（`author.bot: true`）跳過，除非 config 指定要收某個 bot（例如客服機器人的回覆）
- 附件與 embed 只留 URL 與 filename 到 raw；不下載
- `referenced_message` 留 id 當 `reply_to`，讓 normalize 能重建對話串
- 表情反應（reactions）留 count 進 `metrics`，是「多少人同感」的廉價訊號

## 回填與重跑
- 首次回填用 `backfill_days`，一天一天拉，避免一次幾萬則
- 想重跑某天：刪該天 raw 檔 + 把 cursor 改回前一天最後 id；不要刪整個 state/
- 歷史一次性大量匯出可用 DiscordChatExporter，匯出 JSON 後放 `raw/discord/_import/`，normalize 支援讀取

## 檢核（每日結束）
- [ ] 每個白名單頻道 cursor 都前進了（沒前進 = 該頻道沒新訊息，或 bot 看不到 → 查權限）
- [ ] raw/ 當日檔案存在且非空
- [ ] 沒有 401／403
- [ ] `records/` 內沒有任何 17–19 位純數字（PII 漏出檢查，normalize 會自動掃）

## 常見錯誤
| 症狀 | 原因 | 處置 |
|---|---|---|
| 回傳訊息 `content` 全空 | Message Content Intent 沒勾 | Portal 勾選後重啟不需要（REST 即時生效） |
| 403 Missing Access | bot 角色看不到該頻道 | 伺服器端頻道權限加 bot 角色 |
| 一直 429 | 併發太高或共用 IP | 單線程、每請求間隔 ≥ 50ms |
| thread 訊息沒收到 | threads 不在 channel 清單 | 確認 `include_threads: true` |
