# sub-agent 完成後怎麼回報主 agent（主 agent 不等、不卡、不 timeout）

## 先認清一件事

主 agent（bot 管家，kiro-cli one-shot）**回完那一輪就結束了**，它不是常駐進程。所以「回報主 agent」不是把結果塞回某個正在等的呼叫，而是把結果放到**下一輪一定會經過的地方**。等待型設計（`wait`、await Future）在這裡天生會 timeout；正確做法是三條**推 / 拉**路徑，全部不需要任何人等。

```
sub-agent 終態（done / blocked / timeout / failed / cancelled）
   │
   ├─ ① inbox（永遠）   worker 寫 ~/.ark/agent-inbox/<agent>.jsonl ──▶ 主 agent 下一輪開頭 `agent_spawn.py inbox --agent <我> --ack`（毫秒）
   ├─ ② notify_cmd      worker 以 shell 執行 bot 給的指令 ──▶ bot 把 result.md 推回 TG（使用者不用問也會收到）
   └─ ③ to agent        `agent_notify.py --to agent` 再呼叫主 agent 一次，把 result.md 當新訊息餵它 ──▶ 它接著做後續（aiqa_report、resume…）
```

| 路徑 | 誰觸發 | 延遲 | 主 agent 要做什麼 | 適合 |
|---|---|---|---|---|
| ① inbox | worker 自動（預設一定寫） | 下一輪才看到 | steering 加一行：「每輪開頭先 `inbox --ack`，有通知就先回報」 | 所有情境的底線，不會漏 |
| ② notify_cmd | worker 自動（`--notify-cmd`） | 秒級 | 無（bot 直接發 TG） | 使用者要「好了叫我」 |
| ③ to agent | worker 的 notify_cmd 指向它，或 bot 收到 ② 後呼叫 | 秒級 + 一次 LLM | 無（被動被叫醒） | 完成後**還有事要做**（產報告、判斷要不要 resume） |

三條可以疊：`--notify-cmd "python agent_notify.py --job {job_id} --to agent --backend kiro --agent aiqa --session <釘選的 session>"` = ①+③。

## 為什麼不會 timeout

- `spawn` / `exec` 在 1 秒內回 job_id（測試守：`test_spawn_returns_immediately`），主 agent 的 one-shot 不會因為 sub-agent 跑 1 小時而撐著。
- worker 是 detached 進程（`start_new_session` / `DETACHED_PROCESS`），主 agent 的進程結束、bot 重啟、使用者關對話都不影響它。
- `wait` 存在但**不給主 agent 在對話裡用**；它給人（終端機）或 CI 用。SKILL 決策樹明寫：回使用者「已派工 job_id」後就結束這一輪。
- ③ 的再呼叫是 one-shot，有自己的 `--timeout`（預設 600s）；它只是「叫醒」，不是「等」。

## 主 agent steering 要加的那幾行

```markdown
## 背景 job
- 收到會跑很久的事：寫 task.md → agent_spawn.py spawn/exec → 回使用者 job_id，結束這一輪。不在對話裡 wait。
- 每一輪開頭先跑 `python <skill>/scripts/agent_spawn.py inbox --agent <我的代號> --ack`；pending > 0 就先把 notices 的 summary / reason 轉述給使用者，再處理本輪訊息。
- 使用者問「跑到哪」→ status / tail；問「結果」→ result；blocked → 轉述 reason，處理完 resume。
```

## bot 側兩個小掛點（建議下一版）

1. `notify` 入口：吃 `{job_id}`，讀 result.md，發到該 job 發起的 chat（job.json 可帶 `meta.chat_id`，spawn 時由 bot 填）。
2. 排程巡檢：JobQueue 每 N 分鐘 `inbox --agent <各職人>`，有 pending 就代為推 TG——沒人問也會通知。

## 與 ark-agent-bot 既有機制的關係

bot 的 `_spawn_background()` 是「bot 進程內的 asyncio task」，bot 重啟就沒了；本 skill 的 worker 是獨立 OS 進程，狀態在檔案。兩者互補：bot 用自己的機制跑分鐘級的事（蒸餾），用本 skill 跑小時級、要續跑的事。
