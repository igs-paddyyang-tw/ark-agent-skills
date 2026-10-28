# 實戰案例：aiqa 管家 sub-agent（1 小時以上無人值守試玩）

## 問題

playtest 是「截圖 → 主對話看圖 → 判斷 → 下一步」的迴圈。跑 1 小時會：對話塞爆 context（幾十張圖）、使用者一插話迴圈就斷、主 agent 不能無人值守。

## 解法：混合（方案 3）

```
主對話（bot 管家 agent）
  │ ① agent_spawn exec  → 背景腳本 job：aiqa_run loop_spin 60 分鐘（零 LLM，判定在 oracle）
  │ ② agent_spawn spawn --attach-exec <①>  → 背景 sub-agent：每段只看 3 張圖 + 讀 observations，記異常
  │ ③ 立刻回使用者：「已派工，job_id …」；之後 status / result 回報
  ▼
  使用者中途聊別的、插話、關掉對話 —— ①② 照跑
```

| 誰 | 做什麼 | 為什麼放這 |
|---|---|---|
| exec job（aiqa_run） | 連續旋轉、讀數、卡幀偵測、logcat crash、產 results.json | 確定性、不吃 context、天生能跑數小時 |
| sub-agent（steward） | 每 8 分鐘一段：腳本還活著？數字合理？畫面有沒有彈窗 / 黑屏？記 notes | 找「腳本沒想到的」異常；一段 3 張圖，context 永遠乾淨 |
| 主 agent | 啟動兩個 job、收 result.md、跑 aiqa_report | 零負擔，對話可中斷 |

**判定權**：PASS/FAIL 在 `aiqa_oracle` / `aiqa_report`；steward 的 notes 是「值得人看的線索」，不是判定。這條界線讓 steward 看錯一張圖也不會污染結果。

## 操作步驟（主 agent 的 bash）

```bash
S=.kiro/skills
# ① 背景腳本（T5 掛測項，已校準 gamepack）
E=$(python $S/ark-agent-cli/scripts/agent_spawn.py exec --name ghy-aztec2-longrun --max-minutes 70 \
     --cwd $S/ark-mobile-adb \
     --cmd "python scripts/aiqa_run.py --checklist cl.json --backend adb --device 127.0.0.1:5555 --reader tesseract --visual llm --items GHY-AZTEC2-LONG_R-001 --out artifacts/aiqa" \
     | jq -r .data.job_id)
# ② 管家 sub-agent（task 由 examples/tasks/aiqa-steward.md 填好佔位）
J=$(python $S/ark-agent-cli/scripts/agent_spawn.py spawn --name aiqa-steward --task tasks/aiqa-steward.md \
     --backend kiro --agent aiqa --cwd $S/ark-mobile-adb \
     --max-minutes 75 --max-segments 10 --segment-minutes 7 --segment-timeout 900 \
     --attach-exec $E --notify-cmd "python notify_tg.py {job_id} {state}" | jq -r .data.job_id)
# ③ 回使用者；之後
python $S/ark-agent-cli/scripts/agent_spawn.py status --job $J
python $S/ark-agent-cli/scripts/agent_spawn.py result --job $J      # 終態後，summary 原樣轉述
python $S/ark-mobile-adb/scripts/aiqa_report.py --run artifacts/aiqa/<run_id>
```

## 預算怎麼算

- 60 分鐘掛測 → steward `--max-minutes 75`（比腳本多 15 分鐘收尾）、`--segment-minutes 7`、`--max-segments 10`
- 每段 CLI 呼叫 ≈ 讀檔 + 3 張圖 + 寫 checkpoint，LLM 時間 1–3 分鐘；剩下用 `sleep` 等到段末（task 裡明寫，避免狂截圖）
- `--segment-timeout 900`：一段 15 分鐘沒寫 checkpoint 就砍，nudge 一次

## 續跑

- `blocked`（裝置離線 / 腳本死）：人處理完 → `resume --job $J --extra-minutes 30`，從最後 checkpoint 接著看
- `timeout`：`resume --extra-segments 3`
- exec job 死了但 steward 還在：steward 會在下一段發現並 `blocked`，主 agent 重新 `exec` 後把新 job id 寫進 task.md 再 `resume`

## 仍然做不到的

- 純 playtest（AI 親自玩、找未知 bug）在這個架構裡只能是 steward 的「附帶觀察」；要 AI 主動操作仍走 ark-mobile-adb 的 macro（確定性）+ checklist 的 read / ask
- 一段內 LLM 讀圖仍會錯；所以每段限 3 張、判定不給它
