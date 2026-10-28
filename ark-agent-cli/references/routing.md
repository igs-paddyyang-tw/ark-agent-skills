# 選角路由（roster + --route）

> Manager 選角直派：bot 本地、半自動、人主導。從 `agents.yaml` 選一個適合的專家，直派、收 result。**只做一層。**

## 一句話

skill 幫 manager 把「派給誰」落地：腳本列出可派工名單 → **manager（LLM）在對話層挑一個** → 腳本驗名字、從 `agents.yaml` 的 `dir` 補好 `cwd` → spawn。選不出來就把名單交回使用者挑，不硬塞。

## 三方分工（為什麼這樣切）

| 做什麼 | 誰 | 性質 |
|---|---|---|
| 列可派工名單（含 codename / desc / role / cwd） | **腳本**（`roster`） | 確定性、可測 |
| 從名單挑「最適合的專家」 | **LLM（manager）** | 語意，LLM 擅長 |
| 驗 name 合法、補 cwd、派出 | **腳本**（`spawn --route`） | 確定性 |
| LLM 也拿不準 / 回非法名字 | **退回給人選** | 半自動、人主導 |

選角是語意判斷（「修一個 bug」要配「碼哥」），本該 LLM 做；腳本只做「名單怎麼來、名字合不合法、cwd 填哪」這段黑白分明的事。

## 編制來源：`agents.yaml`（唯一來源，不改）

roster 讀 workspace 根的 `agents.yaml`（TG Bot / Web API 也讀同一份）。找檔順序：

1. env `ARK_AGENTS_YAML`（明確指定）
2. 否則從當前工作目錄逐層往上找第一個 `agents.yaml`

依賴的欄位：`role`、`dir`（相對 yaml 目錄）、`codename` / `name`、`desc`、`emoji`、`dispatchable`。
**加 / 移除 agent 只改 `agents.yaml`**，skill 自動認得，不用動任何 prompt 字串。

## 角色分區

| role | 進哪區 | 可被派工？ |
|---|---|---|
| `worker` | workers（預設選角池） | ✅ |
| `leader` | workers | ✅（派給它之後要不要再開第二層，是 leader 自己的事，skill 不管） |
| `admin` | **ops**（維運，另一區） | ⚠️ 不進預設池，但 manager / 人可明確 `--route agent:admin` |
| `manager` / `default` | 不列 | ❌ 互動入口本體，不是被派工對象 |
| `dispatchable: false` | 不列 | ❌ |

## 用法

```bash
S=.kiro/skills/ark-agent-cli/scripts

# ① 腳本出名單（manager 看著選角）
python $S/agent_spawn.py roster               # workers + ops 兩區
python $S/agent_spawn.py roster --role worker # 只列 role=worker（不含 leader）

# ② manager 決定後派工（腳本驗 name + 自動補 cwd）
python $S/agent_spawn.py spawn --name fix-login --task task.md --route agent:coder
#   → 驗 coder 可派工 → 填 --agent coder、--cwd <agents.yaml 所在>/agents/coder-agent → detach worker

# 明確派維運任務給管家
python $S/agent_spawn.py spawn --name check-cost --task task.md --route agent:admin
```

- `--route agent:<name>` 與手動 `--agent` / `--cwd` 可並存；`--route` 只在未給時才自動補，不覆蓋你手填的。
- 沒用 `--route` → spawn 行為與 v2.0.0 完全一致。

## 選角對話模式（manager 側）

1. `roster --role worker` 拿名單
2. 看 `desc` / `codename` 對照任務，挑一個 name
3. `spawn --route agent:<name>`；派出後立刻回使用者 job_id（不 wait）
4. **拿不準就把 workers 名單貼給使用者**，讓人選 —— 這是對話行為，不是腳本邏輯

## 錯誤與退回

| 情況 | 腳本行為 | 下一步 |
|---|---|---|
| name 不在 yaml / dispatchable=false | `BAD_INPUT`（exit 2）回「可派工清單」 | manager 重選或退回給人 |
| name 是 manager / default | `BAD_INPUT`「互動入口不可派工」 | 選 worker |
| `--route` 格式不是 `agent:<name>` | `BAD_INPUT` | 修正格式 |
| 找不到 agents.yaml | `BAD_INPUT` | 設 `ARK_AGENTS_YAML` 或放一份到根 |

## 邊界：這裡是方法 2，方法 1 在 team 套件

- **方法 2（本 skill）**：manager 選一個專家直派，一層，bot 半自動。
- **方法 1（不在此）**：leader 兩層轉包、全自動 orchestration，是 `ark_team_agent` team 套件的事。當團隊合作明確、要全自動時再升級過去。
- 交界：若 manager 選到 leader，skill 就正常把任務派給 leader；leader 要不要在自己那段再 `agent_spawn` 分包給下面的 worker，由 leader 自己（讀它的 steering / judgment）決定，**本 skill 不內建轉包邏輯、不管第二層、不做兩層預算**。

## cwd 為什麼重要

`--route` 自動補的 `cwd` 來自 `agents.yaml` 的 `dir`。worker 以這個 cwd 跑 CLI（`subprocess` 進程層），子 agent 從這個目錄定位它自己的 `.kiro/steering` / memory / knowledge。**忘了給 cwd 會讓子 agent 在錯目錄讀錯人格** —— 路由自動補對 cwd，正是為了根治這點。
