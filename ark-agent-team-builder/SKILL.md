---
name: ark-agent-team-builder
description: |
  產出 ark_team_agent 套件消費端的多 agent 團隊 daemon 骨架 —— 裝 wheel + 產設定檔，
  不手搭架構（team daemon / 多 runtime / Kanban Web UI / REST API / autopilot 排程 /
  TG polling / 決策路由 / 記憶系統全由套件內建）。
  產出：start.py（asyncio run_team）+ team.yaml（instances/channel/access/cost_guard/
  hang_detector）+ scheduler.yaml + .env 骨架 + knowledge/shared 骨架。
  預設多層專家團隊（manager + admin + leader + worker，用 group 歸屬）。
  使用此 Skill 當使用者提及 建立團隊、build team、agent team、多 agent 平台、
  AI 團隊協作、ark_team_agent 消費端、team daemon、team.yaml 骨架、
  或任何需要建立 ark_team_agent 多 agent 團隊的場景。
  不適用於：① 單 bot → ark-agent-bot-builder（ark_bot_agent）；
  ② 非套件獨立 web 應用 → ark-webapp-generator；③ steering 人格 → ark-agent-init。
metadata:
  schema_version: 1
  status: active
  category: scaffolder
  depends_on: [ark-agent-init]
  outputs:
    - format: code
      audience: ai
  author: paddyyang
  version: "3.0"
  updated: 2026-09-08
---

# ark-agent-team-builder

產出 `ark_team_agent` 套件消費端的團隊 daemon 骨架：**裝 wheel + 產設定檔**。

> **v3.0 重寫（2026-09-08）**：本 skill 原為「手搭五層架構團隊平台」（117 項：
> Kanban UI / REST API 21 端點 / 多 runtime / autopilot / TG 14 指令 / 整套
> backend/coordinator/wiki/memory/runtime generators）。那些**已全部套件化為
> `ark_team_agent`**。現在建團隊只需：**裝 wheel + start.py + team.yaml**。
> 手搭 generators 已移除，保留設定慣例 references + team.yaml 範本。

## 定位（與鄰近 skill 的分工）

| 需求 | 用哪個 |
|------|--------|
| **多 agent 團隊 daemon**（ark_team_agent 消費端） | **本 skill** |
| 單 bot（ark_bot_agent） | `ark-agent-bot-builder` |
| 非套件的獨立 FastAPI web 應用 | `ark-webapp-generator` |
| agent 的 steering 人格 + 多 CLI 入口 | `ark-agent-init`（本 skill 產骨架後呼叫它補人格） |

## 觸發條件

- 「建立團隊」、「build team」、「agent team」、「多 agent 平台」、「AI 團隊協作」
- 「ark_team_agent 消費端」、「team daemon」、「team.yaml 骨架」

## 輸入參數

| 參數 | 型別 | 必要 | 預設 | 說明 |
|------|------|------|------|------|
| `project_name` | str | ✅ | — | 團隊專案名稱 |
| `output_dir` | str | ❌ | `.` | 輸出目錄 |
| `bot_token_env` | str | ❌ | `TELEGRAM_BOT_TOKEN` | TG token 的環境變數名 |
| `group_id` | str | ❌ | — | TG 群組 id |

---

## 產出流程

### 步驟 1：裝套件

```bash
uv venv --python 3.13
# wheel 從 Release 取得：github.com/igs-paddyyang-tw/ark_team_agent/releases
uv pip install --python .venv/bin/python <ark_team_agent-*.whl>
```

> 🔴 換裝後**驗 import 版號，不看 pip 輸出**：
> `.venv/bin/python -c "import ark_team_agent; print(ark_team_agent.__version__)"`
> team 端有些消費端 pin 版號（`pyproject.toml`），升級要同步改 pin（doctor 會比對）。

### 步驟 2：產目錄結構

```
{project}/
├── start.py                 # asyncio.run(run_team(Path("team.yaml")))
├── team.yaml                # 團隊設定（唯一集中點）← 範本 references/templates/team.yaml.tpl
├── scheduler.yaml           # 排程（選用）← references/templates/scheduler.yaml.tpl
├── .env                     # 機密（bot_token_env 指定的變數 / API key）
├── requirements.txt         # 只列 wheel
├── .kiro/steering/          # 全域規範（由 ark-agent-init 產；TEAM.md 由套件動態產生）
├── knowledge/
│   ├── shared/{wiki,raw}/    # 🔴 團隊共用知識庫（Wiki 引擎讀這層）
│   │   └── {schema,index,log}.md
│   └── raw/memory-archive/
├── agents/<name>-agent/      # 各 instance 的 working_directory（含 .kiro + knowledge + memory）
└── secrets/                 # 機密檔（BQ key 等，.gitignore 排除）
```

> knowledge/shared 骨架範本在 `references/templates/knowledge/shared/`。

### 步驟 3：填 team.yaml（設定集中點）

team 端設定**集中在 team.yaml**（不像 bot 端分 bot.yaml/agents.yaml）。核心區塊：

| 區塊 | 內容 |
|------|------|
| `defaults` | `backend: kiro-cli` / `model: auto` |
| `kiro_files` | `skills.policy`（建議 skip，交 sync_skills 管）/ `steering.team_md: always` |
| `channel` | `bot_token_env` / `group_id` / `announce_topics`（只收不回的公告頻道） |
| `access` | `mode: group` / `allowed_users` |
| `cost_guard` | `daily_limit_usd` / `warn_at_percentage` / `timezone` |
| `hang_detector` | `enabled` / `timeout_minutes` / `escalation_minutes` |
| `instances` | 各 agent：`working_directory` / `description` / `role` / `private_chat` / `skip_resume` / **`group`** |

> 🔴 **worker 歸屬用 `group: <leader-name>`（worker 指向所屬 leader），不是 leader 用 `group_members` 列成員。**
> `group_members` 是 **bot 端 `agents.yaml`** 的欄位 —— team 端寫它會被套件**靜默忽略**
> （log 印 `欄位 'group_members' 不存在 → 已忽略。你是不是想寫 'group'？`），leader 派工歸屬不生效。
> （2026-09-11 建 market-team-agent 第一次實跑踩到，1.4.11/1.8.4 皆然。）

範本：`references/templates/team.yaml.tpl`（基礎）、`team-full.yaml`（多層專家）、
`team-ops.yaml` / `team-dev.yaml`（情境）。角色慣例見 `references/role-presets.md`。

> 🔴 `kiro_files.steering.team_md: always` —— 成員表以 team.yaml 為唯一真相，
> 每次啟動同步。設 `once` 會凍結舊內容（含已移除的幽靈成員），升級套件也修不好。

### 步驟 4：補 steering 人格

呼叫 `ark-agent-init` 為各 instance 產 `.kiro/steering`（SOUL 人格 + 多 CLI 入口）。
`TEAM.md` **不用手產** —— 套件 `backend.py` 依 team.yaml 動態產生（policy=always）。

> 🔴 **`working_directory: .` 的 manager，steering 在專案根 `.kiro/steering/`，不在 `agents/<name>/`。**
> manager（總機）通常設 `working_directory: .` 讀根目錄 —— 它的 `SOUL.md`/`AGENTS.md`
> 就是**根目錄**那份，不要另外在 `agents/<manager>/` 建（會被忽略）。
> 驗證骨架時別把「`agents/<manager>/` 沒有 SOUL」當成缺失。

#### 🔑 套件啟動時會自動產/更新 steering（實測 1.8.4）

`backend.py` 每次啟動會處理各 instance 的 steering，**依 `kiro_files` policy**：

| 檔 | 預設 policy | 行為 |
|----|-----------|------|
| `SOUL.md` | `once` | **已存在就不覆蓋** → 你手寫的人格保住；不存在才用 `templates/agents/<role>/SOUL.md` 產 |
| `AGENTS.md` | once | 同上 |
| `MEMORY.md` / `BRAIN.md` / `CODE.md` / `USER.md` | once | 不存在才產（骨架）|
| `TEAM.md` | `always` | 每次依 team.yaml 動態產（成員表唯一真相）|

> 💡 手寫人格靠**預設 once** 就受保護。範例包 team.yaml **顯式寫出 `soul_md: once`**
> —— 行為與預設相同，但讓看設定的人一眼確認「SOUL 不會被蓋」，不必去記預設值。

> 🔴 **log 印 `Using SOUL.md template for X` 不代表它覆蓋了你的手寫 SOUL。**
> 那行只是「載入了 template 內容備用」；接著 `policy=once` 判斷 `SOUL.md 已存在 → 跳過寫入`。
> 手寫人格在 `once` 下安全。（2026-09-11 實跑一度被這行 log 誤導以為被覆蓋，查 backend.py:626-651 確認沒有。）
> 要讓套件每次強制用 template 覆蓋 → 設 `soul_md: always`；要完全不管 → `skip`。

#### ⚙️ 啟動後的兩個非致命現象（實測 1.8.4，可忽略或按需處理）

- **website dashboard 自動起在 `health_port + 5000`**（如 health 23040 → dashboard 28040）。
  規劃 port 時預留 28xxx 頻段（1.6.2 起 offset=5000）。
- **`authority-matrix.yml not found`（non-fatal）** —— 決策鎖用，沒有也能跑。
  要啟用防互鎖決策才在 `config/authority-matrix.yml` 建（選配）。
### 步驟 5：啟動驗證（**兩階段就緒，別在第一階段就測私訊**）

```bash
.venv/bin/python start.py    # 或 systemctl --user start <svc>
```

啟動就緒分**兩個階段**，中間差數分鐘，**私訊要等第二階段**：

**階段一 — daemon + TG 上線（約 20 秒）**
```bash
curl -s localhost:<health_port>/api/health     # ark_team_agent → /api/health
# 看 instances.running == total、preflight P0/P1 == 0
journalctl --user -u <svc> -n 30 | grep -E "Team ready|Application started"
```
此時 `6/6 running` + `Application started` = **daemon 與 TG polling 就緒**，但——

> 🔴 **此刻私訊還不會回！** 各 instance 的 **kiro-cli backend 尚在冷啟**：
> log 會看到 `0 of 1 mcp servers initialized ... Servers still loading: - team`。
> kiro-cli 首次啟動要 spawn `team` MCP server + 載入 + 印出就緒訊號
> **`All tools are now trusted`**，daemon 才判該 instance 可處理訊息。冷啟含 MCP 握手
> **約 2–4 分鐘**（首次最久，之後 `--resume` 快）。

**階段二 — kiro-cli backend 就緒（首次約 2–4 分鐘）**
```bash
# 確認目標 instance 的 kiro-cli 已印就緒訊號（backend.py READY_PATTERN）
journalctl --user -u <svc> --since "-5min" | grep -E "All tools are now trusted|💬 REPLY"
```
看到該 instance 的 `💬 REPLY` 或就緒訊號後，私訊才會有回應。

> 💡 **訊息不會丟**：冷啟期間收到的私訊會進 daemon 佇列（log `Queued message to X`
> → `Delivered message to X`），kiro-cli 就緒後**補處理**。所以「送了沒回」先別當壞掉——
> 查 CPU 時間（`/proc/<kiro-cli-pid>/stat` 的 utime/stime 有沒有動）與就緒訊號，
> 冷啟未完成 ≠ 故障。（2026-09-11 建 market-team-agent 實測：訊息 13:08 進佇列、
> kiro-cli 13:11 就緒後才回，中間 daemon 一路正常。）

- 三層架構慣例（General manager → leader → worker group）見 `references/`
- 職人 worker 不設 topic_id，輸出自動發到所屬 leader 的 topic

## 附帶資源

| 路徑 | 說明 |
|------|------|
| `references/templates/team*.yaml` | team.yaml 範本（基礎 / full / ops / dev） |
| `references/templates/scheduler*.yaml` | scheduler 範本 |
| `references/templates/knowledge/shared/` | 知識庫骨架 |
| `references/role-presets.md` | 角色定義慣例 |
| `references/persona-presets.md` | 人格語氣預設 |
| `references/naming-rules.md` | 命名規範 |
| `references/kiro-files-presets.md` | kiro_files policy 慣例 |
| `references/mcp-tools-spec.md` | 團隊 MCP 工具（reply/send_to_instance…） |
| `references/telegram-ux-patterns.md` | TG UX 慣例 |
| `references/communication-presets.md` | 通訊規則預設 |
| `scripts/scaffold_dirs.py` | 依 team.yaml 產目錄骨架 |
| `scripts/validate_team.py` | team.yaml 驗證 |
| `examples/market-team/` | 🎯 **完整實例**（市場情報團隊）—— 「長好的樣子」，對照 6 instance + 雙知識櫃 + dir="." manager + 完整 team.yaml 怎麼組（範本教填空、本例教全貌）|

## 注意事項

- Python 3.13、`pathlib.Path`、async I/O、繁中 docstring
- **不要手搭** daemon / UI / API / runtime / 記憶 —— 套件都有；手搭 = 兩套並存必漂移
- 換裝驗 import 版號；team.yaml 的 `team_md` 用 `always`
- 各 instance 的 `working_directory` 就是它的家（讀自己的 .kiro/knowledge/memory）
