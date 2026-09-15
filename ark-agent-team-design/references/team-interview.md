# 團隊編制訪談題庫

quick 只問 Q0；standard 問 Q0–Q6；deep 在 Q6 後交 ark-grill-me。
規則同 ark-grill-me：一次一題、2–4 具體選項、標 ⭐、末項「其他」。能自己查的不問。

## 選項生成來源

| 來源 | 用在 |
|---|---|
| `assets/patterns/*.yaml` | Q0 樣板命中；Q3–Q5 的預選 |
| `ark-agent-role-profile` 角色庫（`profile_lint --list-roles`） | Q4/Q5 的 base_role 候選 |
| 既有 `team.yaml` | diff 模式：既有 instance 當已選 |

## Q0 · 目標與檔位（quick 唯一題）

```
這支團隊的目標一句話是什麼？（我會拿它比對現有樣板）

命中樣板時：
1️⃣ quick — 套用「{pattern.name}」（{n} 人），只問專案名與入口 ⭐
2️⃣ standard — 6 題自訂
3️⃣ deep — standard 後拷問編制
```
寫入：`goal`、`team_id`（由專案名轉 kebab）。

## Q1 · 交付物 → `deliverables`

```
Q1：這支團隊對外交付的是什麼？（可多選）
☐ {依 goal 推的 3 個候選，如：放行建議報告 / 每日日報 / 測試計畫}
☐ 其他
```
判準：每個 deliverable 之後至少對到一個 worker 的 purpose，否則 lint P2。

## Q2 · 使用者入口 → `entry` + 是否需要 manager

```
Q2：使用者第一句話打給誰？
1️⃣ admin（小團隊；admin 兼入口，不接業務只轉交）⭐（≤ 1 leader 時）
2️⃣ leader（使用者就是要談業務）
3️⃣ 獨立 manager（多個 leader 需要意圖路由）⭐（≥ 2 leader 時）
```
選 3 才產 manager instance。entry 的 `working_directory` 會是 `.`。

## Q3 · leader 切分 → tier=leader 的 instances

```
Q3：需要幾個統籌者？
1️⃣ 1 個 leader 收斂全部 ⭐（worker ≤ 5）
2️⃣ 依 {deliverable 群} 切 2 個 leader
3️⃣ 其他
```
每個 leader 問一句 purpose（給 base_role 候選：leader / test-lead / …）。

## Q4 · worker 能力拆分 → tier=worker 的 instances

先列候選能力（從 goal + deliverables 推，樣板命中時直接帶），再逐一問「留／合併／刪」：

```
Q4-1：這個能力要獨立一個 worker 嗎？
「{能力}」— 完成判準：{對錯 / 區間 / 可重現 / 統計顯著}
1️⃣ 獨立 ⭐（判準或權限與其他 worker 不同）
2️⃣ 併入 {另一 worker}
3️⃣ 刪
```
**拆分判準**（訪談時說給使用者聽一次）：
- 判準不同 → 拆（功能「對／錯」vs 數值「區間內／外」）
- 權限不同 → 拆（能寫 code vs 不能）
- 可 deterministic → 拆成低成本 worker（去重、分級、日報）

每個留下的 worker：問 `group`（哪個 leader，1 個 leader 時不問）與 base_role（角色庫候選 ⭐／custom）。

## Q5 · 升報鏈 → `escalation`

不問，直接推：worker → 其 group leader → admin（或 manager）。只在預覽時展示，使用者可改。

## Q6 · 決策鎖 → `decision_locks`

```
Q6：哪些決定不能由 agent 自己拍？（可多選，每項附 approver 預設）
☐ {對外發布 / 上線放行 / 動 production / 花錢 / 改被測物}  approver: human ⭐
☐ {改 Spec / 改需求}  approver: {leader}
☐ 其他
```
每條再問「哪些 instance 可以提案（proposer）或被允許執行（allowed）」，候選來自 instances。

---

## deep：拷問切入點（交 ark-grill-me）

限定三題：
1. **多了誰**：哪個 worker 的 purpose 可由另一個 worker 加一個 skill 完成？→ 合併或說明權限差
2. **少了誰**：哪個 deliverable 沒有 worker 對到？→ 補 worker 或刪 deliverable
3. **鎖漏了誰**：哪個 hard_stop 級的決定沒在 decision_locks？→ 補鎖

回寫 spec 後重跑 lint。

## 預覽格式

```
🏗️ {name}（{n} 人）
👑 {admin}
🧭 {leader}  ← {workers…}
🧭 {leader2} ← {workers…}
入口：{entry}
🔒 human 批准：{decisions…}

1️⃣ 生成  2️⃣ 改 worker  3️⃣ 改決策鎖  4️⃣ 改入口
```
