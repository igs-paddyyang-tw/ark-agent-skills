---
name: ark-agent-team-design
description: |
  從業務目標設計 agent team 的編制：三檔位訪談（quick 套用編制樣板 / standard 6 題 /
  deep 交 ark-grill-me 拷問），產出 `team-spec.yaml`（層級、instance、關係、升報、決策鎖），
  再由 gen_team.py 生成 team.yaml 骨架（符合 ark-agent-team-builder 範本與 validate_team）
  與 N 個 role-profile stub（交 ark-agent-role-profile 補人格）。內建編制樣板
  assets/patterns/（game-qa 8 人、dev-standard、ops-market）。
  使用此 Skill 當使用者提及 設計團隊、團隊編制、需要哪些角色、team spec、team-spec、
  組建 agent team、幾個 agent、誰向誰報、決策鎖、authority、角色清單、
  「這個目標要幾個 agent」「幫我規劃一支 QA / 營運 / 研發團隊」「team.yaml 該放誰」。
  不適用於：裝 wheel 與啟動 daemon（ark-agent-team-builder）；單一 agent 的人格
  （ark-agent-role-profile）；產 .kiro/ 檔案（ark-agent-init）。本 skill 只決定「誰在團隊裡、
  怎麼連」，不填 stance / hard_stops。
metadata:
  schema_version: 1
  status: active
  category: process
  outputs:
    - format: data
      audience: ai
    - format: code
      audience: both
  render: none
  depends_on: [ark-agent-role-profile, ark-grill-me]
  author: paddyyang
  version: "1.1"
  updated: 2026-09-16
---

# ark-agent-team-design

目標 → 訪談 → `team-spec.yaml` → `team.yaml` 骨架 + N 個 `role-profile.yaml` stub。

> **鏈上的位置**：這是建置鏈的第 0 步。
> `team-design` → `team-builder`（裝 wheel、start.py）→ `role-profile`（補人格）→
> `agent-init`（產 .kiro）→ `sync_skills` → 行為驗收門 → start。
> team-builder 的 `role-presets.md` 那幾張固定編制表，改由本 skill 的 `assets/patterns/` 取代。

## 觸發條件

- 「這個目標需要哪些 agent」「幫我規劃一支 {QA / 營運 / 研發} 團隊」
- 「team spec」「團隊編制」「誰向誰報」「決策鎖 / authority matrix」
- 「team.yaml 該放哪些 instance」
- ark-agent-team-builder 步驟 3 填 instances 前，若使用者沒有現成編制

---

## 邊界（寫死，避免變成第二個 role-profile）

| 本 skill 決定 | 本 skill **不**決定 |
|---|---|
| 有哪些 instance、各屬哪層（manager / admin / leader / worker） | 各角色的 stance、hard_stops、voice |
| worker 歸屬哪個 leader（`group`）、誰是使用者入口 | 各角色裝哪些 skills（由 profile.skills 決定） |
| 升報鏈、決策鎖（誰能批准什麼） | steering 內容、knowledge 內容 |
| 每個 instance 的 `base_role`（指向角色庫） | wheel 版本、port、TG token |

stub 裡 stance 等欄位若角色庫有 `base_role` 就複製，沒有就留 `TODO` 標記——
`profile_lint` 會擋住 TODO，強迫走 role-profile 訪談。

---

## 互動流程

```
0. 掃描 → 現有 team.yaml？角色庫有哪些 base_role？（profile_lint --list-roles）
1. 選檔位 → quick / standard ⭐ / deep
2. 訪談   → references/team-interview.md，一次一題，2–4 選項 + ⭐推薦
3. 落 spec → team-spec.yaml
4. lint   → python scripts/team_spec_lint.py team-spec.yaml（P0/P1 清零）
5. 預覽   → 印編制表（層／instance／base_role／group）+ 決策鎖，編號選項確認
6. 生成   → python scripts/gen_team.py team-spec.yaml --out {project} [--target team|bot|hybrid]
7. 交接   → 回報產出 + 下一步（team-builder 裝 wheel；role-profile 補 TODO stub）
```

### 三檔位

| 檔位 | 題數 | 適用 |
|---|---|---|
| **quick** | 1 | 目標命中現有樣板（game-qa / dev-standard / ops-market），只問專案名與入口 |
| **standard** ⭐ | 6 | 多數新團隊：目標 → 交付物 → 入口 → leader 切分 → worker 能力 → 決策鎖 |
| **deep** | 6 + 拷問 | 高權限或跨部門團隊：standard 後把 spec 交 ark-grill-me 拷問「哪個角色多了／少了／可合併」 |

### 編制原則（訪談時的判準，也是 lint 規則）

1. **一個 worker 一個判準**：兩個能力的「完成」定義不同（對／錯 vs 區間內／外）就拆成兩個 worker
2. **權限不同就拆**：能寫 code 的和不能寫的不共用一個 instance
3. **可 deterministic 的能力獨立成低成本 worker**（去重、分級、報告）
4. **leader 不做事只收斂**；一個 leader 最多 6 個 worker，達 6 時其中一個應是 deterministic 的整理型 worker
5. **admin 必有且不接業務**；manager 只在需要「意圖路由多個 leader」時才設
6. 8 個以下 instance；超過就拆兩支團隊

---

## team-spec.yaml 契約

Schema：`references/team-spec.schema.json`。摘要：

```yaml
schema_version: 1
team_id: game-qa
name: 遊戲測試團隊
goal: 每個版本產出有證據的放行建議，人類只做最後放行決策
deliverables: [測試計畫, 放行建議報告, 每日測試日報]
entry: qa-admin                       # working_directory: . 的那個 instance
instances:
  - id: qa-admin                      # 不含 -agent 後綴；gen 時加
    tier: admin                       # manager | admin | leader | worker
    base_role: admin                  # 角色庫 id 或 custom
    purpose: 管 daemon / crash / 版本，不接業務
    persistent: true
  - id: test-lead
    tier: leader
    base_role: test-lead
    purpose: 對照 Spec 定測試計畫、派工、彙整證據、給放行建議
  - id: functional-qa
    tier: worker
    base_role: qa
    group: test-lead                  # worker 必填，指向 leader id
    purpose: 逐條驗收規則／狀態機／UI 流程
    persistent: false
escalation:                           # 升報鏈；worker → leader → admin/manager
  - { from: functional-qa, to: test-lead }
  - { from: test-lead, to: qa-admin }
decision_locks:                       # 生成 authority-matrix 的原料
  - { decision: 放行上線, approver: human, proposer: test-lead }
  - { decision: 修改被測程式碼, approver: test-lead, allowed: [automation-engineer] }
  - { decision: 對外發布數字, approver: human, allowed: [] }
```

---

## 生成物（gen_team.py）

| 輸出 | 內容 | 下游 |
|---|---|---|
| `team.yaml` | 依 team-builder 範本：defaults / kiro_files（skills skip、team_md always、soul_md once）/ channel / access / cost_guard / hang_detector / instances（含 `group`；`profile` 寫成 **`# profile:` 註解**，非裸欄位 —— 套件不認得裸欄位會 WARNING，實測 2026-09-16）/ health_port | team-builder 步驟 3 直接用；過 `validate_team.py`（讀 profile 註解驗 SOUL 戳記） |
| `agents/{id}-agent/role-profile.yaml` | stub：identity / relationships / scope.escalates_to 由 spec 填；stance 等從 base_role 複製或 `TODO` | role-profile 補完 → lint → render |
| `config/authority-matrix.yml` | 由 `decision_locks` 生成 | 套件決策鎖（選配） |
| `NEXT.md` | 依序列出剩餘步驟與指令（裝 wheel → 補 TODO stub → init → sync → eval → start） | 人看 |

> entry instance 的 `working_directory: .`，其 role-profile 放專案根 `role-profile.yaml`
> （對應 init 規則：根目錄 `.kiro/` 就是它的 workspace）。

### `--target {team|bot|hybrid}`：一份 spec 產不同 runtime（v1.1）

```bash
python scripts/gen_team.py spec.yaml --out {project} --target hybrid
```

| target | 產出 | 用途 |
|---|---|---|
| **team**（預設） | team.yaml | 純 team daemon（ark_team_agent）|
| **bot** | agents.yaml（只 default+manager）+ bot.yaml（`team_leader: ""`）| 純 bot（ark_bot_agent），關派工 |
| **hybrid** | 上兩者 + scheduler.yaml | team + bot 雙 runtime 共用工作區 |

- **hybrid single-owner 原則**（避免兩 runtime 互搶）：
  - 派工只有 team daemon 做 → bot 的 `agents.yaml` 只放 `default`（不填 leader/group_members）
  - `bot.yaml` 的 `modes.team_leader: ""`（空）→ bot 側不啟 team 派工
  - bot `features.web_ui: true`、TG 不啟 → 不與 team 搶 TG poller
- **長任務移出 instances**：`scheduled_jobs[]`（spec）→ `scheduler.yaml`（模擬/壓測等長任務由排程觸發，不占常駐 instance）。
- 三個 target 產出都過各自 validator（`validate_team.py` / `validate_agent.py`）。

---

## 守門（team_spec_lint.py）

| 級別 | 條件 |
|---|---|
| **P0** | schema 不符；無 admin；無 leader；worker 缺 `group` 或指向非 leader；`entry` 不在 instances；id 重複或不合 `^[a-z][a-z0-9-]*$` |
| **P1** | instance > 8；leader 有 `group`；同一 leader 下 worker > 6；escalation 有環；decision_locks 的 approver/allowed 引用不存在的 id；base_role 不在角色庫且非 `custom` |
| **P2** | 同一 leader 下 worker = 6（上限，需有整理型 worker 分擔）；worker 的 purpose 與另一 worker 相似度 > 0.8（疑似可合併）；deliverables 為空；沒有任何 decision_lock 的 approver 是 human |

---

## 完成回報格式

```
✅ team-spec 已產出：{team_id}（{檔位}）

編制 {n} 人：
👑 {admin}   🧭 {leaders}   🔧 {workers（依 group 分列）}
🔒 決策鎖 {m} 條（human 批准 {k} 條）

📁 產出：team-spec.yaml · team.yaml · agents/*/role-profile.yaml（{t} 個含 TODO）· config/authority-matrix.yml · NEXT.md
🔍 lint P0 0 · P1 0 · P2 {p}；validate_team ✅

💡 下一步：
1️⃣ ark-agent-team-builder 裝 wheel + start.py
2️⃣ ark-agent-role-profile 補 {t} 個 TODO stub
3️⃣ deep：交 ark-grill-me 拷問編制
```

## 注意事項

- 不上網搜「某產業該有哪些角色」——編制由目標與判準推，外部知識在 role-profile 階段補
- 已有 team.yaml 時走 diff 模式：只新增 instance，不改既有 port / token / access
- 樣板不是名冊：`assets/patterns/*.yaml` 本身就是合法 team-spec，可直接 lint；README
  的樣板列表用 `team_spec_lint.py --list-patterns` 導出

## 附帶資源

| 路徑 | 說明 |
|---|---|
| `references/team-interview.md` | 三檔位題庫 Q0–Q6 + deep 拷問切入點 |
| `references/team-spec.schema.json` | 契約 JSON Schema |
| `assets/patterns/game-qa.yaml` | 遊戲測試團隊 8 人（admin + test-lead + 6 worker） |
| `assets/patterns/dev-standard.yaml` | 研發 5 人（admin + leader + coder / qa / devops） |
| `assets/patterns/ops-market.yaml` | 市場情報 6 人（manager + admin + leader + 3 worker，對齊 team-builder 範例） |
| `scripts/team_spec_lint.py` | 守門 + `--list-patterns` |
| `scripts/gen_team.py` | spec → team.yaml + stubs + authority-matrix + NEXT.md |
| `evals/evals.json` | 測試提示詞 |
