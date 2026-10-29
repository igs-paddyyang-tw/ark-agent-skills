# job 契約（agent_spawn / agent_worker）

## 目錄：`$ARK_AGENT_JOBS_DIR/<job_id>/`（預設 `~/.ark/agent-jobs`）

| 檔 | 誰寫 | 內容 |
|---|---|---|
| `job.json` | spawn / worker | 見下；單一真相 |
| `task.md` | spawn（複製） | 主 agent 的任務，worker 只讀 |
| `segments/NNN.prompt.md` / `.out.txt` / `.checkpoint.json` | worker / sub-agent | 每段的 prompt、清理後輸出、checkpoint |
| `artifacts/` | sub-agent | 證據（截圖、log、報告） |
| `events.jsonl` | worker | start / segment_start / nudge / checkpoint / budget / done / blocked / failed / cancelled / notify |
| `result.md` | worker | 終態摘要（summary、逐段進度、證據、備註） |
| `worker.log` | detach | worker 進程 stdout（除錯） |
| `exec.log` | worker（exec 型） | 指令 stdout+stderr |
| `cancel` | spawn cancel | 旗標檔，worker 下一檢查點停 |

## job.json

```json
{"job_id": "20261028-093000-aiqa-steward-ab12cd", "name": "aiqa-steward", "type": "agent | exec",
 "backend": "kiro", "model": null, "agent": "aiqa", "cwd": "...", "task_file": ".../task.md",
 "state": "queued | running | done | blocked | failed | timeout | cancelled",
 "segment": 3, "max_segments": 10, "max_minutes": 75, "segment_minutes": 7, "segment_timeout_s": 900,
 "attached_exec": "<exec job_id>", "notify_cmd": "python notify.py {job_id} {state}",
 "last_checkpoint": {"status": "continue", "...": "..."}, "pid": 1234, "heartbeat_at": "...", "created_at": "...", "started_at": "...", "finished_at": null,
 "resume_count": 0, "error": null, "exit_code": null}
```

## 2.4.0 新欄位

`access` / `allow_tools`（權限）、`idle_segments` / `idle_streak`（空轉熔斷）、`handoff_grace_s`（已交接後最多等幾秒）、`watchdog_cmd` / `watchdog_fail` / `watchdog_fails`、`usage{input_tokens, output_tokens, cost_usd, llm_calls}`（累計；每段另存 `segments/NNN.usage.json`）。
events 新 kind：`killed(why=handoff_grace|timeout)`、`watchdog_fail`、`blocked(reason=idle|watchdog)`、`finalized(reason=worker_died|worker_exception|worker_exit_without_terminal_state|finalize_forced)`。

## 崩潰補收尾（finalize）

worker 的 `finally` 保證離開前一定是終態；worker 被外力殺掉（state=running 但 pid 已死 = 孤兒）時，`status` / `list` 會**自動** finalize：從既有 checkpoints 補 `result.md`、state → `failed(error=worker_died)`、殺 exec 殘留 `child_pid`、清 `cancel`、發 inbox。手動：`finalize --job`（孤兒）或 `--force`（殺活的 worker 強制收尾）。判活：Windows OpenProcess；POSIX `kill 0` + `/proc/<pid>/status` 殭屍視為死。

## 回收

`gc --days 7 --keep failed,blocked [--dry-run]`：刪到期且不在 keep 的終態 job 目錄（含 artifacts）。

## 狀態機

```
queued ──▶ running ──▶ done        （checkpoint.status = done）
                  ├──▶ blocked     （checkpoint.status = blocked；可 resume）
                  ├──▶ timeout     （max_minutes / max_segments 用盡；可 resume --extra-*）
                  ├──▶ failed      （CLI 不存在 / 連續兩段無 checkpoint / 例外 / exec 非零退出；可 resume）
                  └──▶ cancelled   （cancel 旗標）
```

## exit code（wait）

0 done · 3 GATE_BLOCKED（blocked）· 6 QUERY_FAILED（failed / cancelled）· 7 TIMEOUT（timeout，或 wait 本身等超時但 job 仍在跑）· 2 BAD_INPUT（job 不存在）

## 心跳與孤兒

worker 每段開始與每段結束更新 `heartbeat_at`（exec 型每 2 秒）。`wait` 發現 state=running 但 pid 不存在 → 回 QUERY_FAILED 提示 resume；`resume` 會把 state 設回 queued 並重新 detach，從 `segment` 與 `last_checkpoint` 接續。

## notify_cmd

終態時以 shell 執行，佔位 `{job_id}` `{state}` `{result}`。bot 端用它把 result.md 丟回 Telegram（例：`python -m ark_bot_agent.notify --job {job_id}`，由 bot 套件提供；本 skill 不綁 TG）。
