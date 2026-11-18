# 排程省 LLM：三種排程＋閘門（3.3.0）

> 來源：2026-11-13～11-18 雲端（hoyeah／slotverse／game）與本機五隊（kiro／nana／ninja／paddy／wukong）實測。
> Claude 後端每個新回合光載入上下文就 8～15 萬 token；「確認沒事」也是一個完整回合。

## 1. 每個排程先分類

| 類型 | 判斷 | 寫法 |
|---|---|---|
| **腳本**（零 LLM） | 提詞其實是「在專案根執行 … ／用 bash 執行 …」—— agent 只是代跑指令 | `type: command`，`command: [".venv/bin/python", "scripts/x.py"]` |
| **閘門**（有事才叫） | 閒置時 agent 只會回「沒事／不派工／不需動作」 | `type: command` 跑 `sched_gate.py <job>`，規則在 `config/gated_jobs.json` |
| **固定叫 LLM** | 產出本身就是內容（新聞、教學、研究），和團隊忙不忙無關 | 保留 prompt 排程；同主題的合併成一份 |

🔴 提詞裡寫「無事就安靜／跟上次相同不回報」**不省錢**：回合已經開了、上下文已經載入了，只少了一則 TG 訊息。

## 2. 閘門 `scripts/sched_gate.py`

複製到團隊專案的 `scripts/`，用該專案的 python 跑（需要 pyyaml，team venv 都有）。

```yaml
# scheduler.yaml
- name: progress-check
  type: command
  command: [".venv/bin/python", "scripts/sched_gate.py", "progress-check"]
  cron: "10 9 * * 1-5"
```
```json
// config/gated_jobs.json
{
  "progress-check": { "target": "ceo-agent", "rule": "tasks_open", "max_skip_days": 7 },
  "qa-review":      { "target": "qa-agent",  "rule": "git_paths", "since_days": 7, "paths": ["src/", "tests/"] },
  "wiki-ingest":    { "target": "admin-agent", "rule": "new_files", "globs": ["knowledge/raw/**/*.md", "agents/*/knowledge/raw/**/*.md"] },
  "memory-distill": { "target": "@new_daily", "rule": "new_files", "globs": ["memory/daily/*.md", "agents/*/memory/daily/*.md"] }
}
```
提詞放 `config/gated_prompts/<job>.md`（`{date}` 會換成今天），或 job 直接給 `"prompt"`。

| 規則 | 觸發條件 | 適用 |
|---|---|---|
| `tasks_open` | 任務板有 todo／in_progress／blocked／review | 進度檢查、派工 |
| `fingerprint` | 任務板或 origin 分支自上次觸發後有變化 | 進度檢查（比 tasks_open 更省：有任務但沒進展也跳過） |
| `git_paths` | 近 N 天指定路徑有 commit | QA、美術／音效盤點、changelog |
| `new_files` | 上次觸發後 glob 內有檔案更新 | wiki ingest、知識同步、記憶蒸餾 |
| `metric` | CSV 欄位近 N 天合計 ≥ 門檻 | 業務摘要（agent 間訊息量） |

- 所有規則可加 `max_skip_days`：太久沒觸發就保底一次
- **`target: "@new_daily"`**：只喚醒「自己 memory/daily 有新檔」的 agent —— 取代 `broadcast_all`（一次喚醒全隊，lazy agent 每個都要重載上下文）
- 上線前：`sched_gate.py --check`（target、規則參數、提詞齊全）、`sched_gate.py --list`（乾跑看每個 job 現在會不會觸發）
- 狀態在 `state/gate/<job>.json`；`DRY=1` 或 `--dry` 只判斷不送出

## 3. 另外兩個大頭（不在規則裡，但要一起看）

| 來源 | 現象 | 做法 |
|---|---|---|
| `broadcast_all` 扇出 | 一個每週排程＝全隊 N 個回合（nana 11、ninja 9） | 改 `@new_daily` 或只發給需要的人；「叫大家整理知識」這類只為廣播而叫 LLM 的排程直接刪 |
| 套件啟動提示（`team.py`） | 每次 daemon 啟動都喚醒入口 agent；當天第一次啟動還要求「依優先序發派今日任務」→ 閒置也派工 | 目前沒有開關（已向 ark-agent-os 提需求）；非必要不重啟、要重啟同日一次做完 |
