# 角色定位訪談題庫

三檔位共用同一份題庫；quick 只問 Q0，standard 問 Q0–Q7，deep 在 Q7 後進入拷問。
每題規則：一次一題、2–4 個具體選項、標 ⭐ 推薦、最後一項固定「其他（請說明）」。

## 選項生成規則

| 來源 | 用在 |
|------|------|
| `assets/roles/{base_role}.yaml` 的值 | 內建角色：直接當 ⭐ 推薦選項 |
| `team.yaml` 成員清單 | Q5 的 reports_to / delegates_to / consults |
| `skills/*/SKILL.md` 的 name + description | Q6 技能候選（依 base_role 的 skills 預選） |
| 既有 `.kiro/steering/SOUL.md` | 若存在，從 Mission / Rules 反推 stance 與 hard_stops 當預選 |
| 純自訂角色 | 選項由角色名稱推斷 3 個可能的定位句，第 4 項「其他」 |

---

## Q0 · 檔位與稱呼（quick 唯一題）

```
要幫 {agent} 定義角色定位。先兩件事：

檔位：1️⃣ quick  2️⃣ standard ⭐  3️⃣ deep
稱呼：{base_role 預設名} / 其他
```

寫入：`identity.name`、決定後續題數。emoji 不問，由 base_role 預設，使用者可在預覽時改。

## Q1 · 一句話定位 → `identity.one_liner`

```
Q1：{name} 的一句話定位？

1️⃣ {base_role.one_liner} ⭐
2️⃣ {依 agent 名稱與 team.yaml 描述生成的變體}
3️⃣ {更窄／更寬的變體}
4️⃣ 其他（請說明）
```

判準：≤ 40 字、含「對誰做什麼」。「負責 X」不合格，「把 X 翻成 Y 給 Z 用」合格。

## Q2 · 三軸取捨 → `tradeoffs`

一題三軸，一次問完（這是唯一多選題，因為三軸互相獨立）：

```
Q2：三個取捨的預設值（各選一）：

需求模糊時：  A 先問 ⭐  B 先做最小版本再確認  C 照最保守解讀做
速度 vs 品質：A 速度   B 品質 ⭐
風險偏好：    A 保守 ⭐  B 平衡   C 積極
```

⭐ 依 base_role 決定（例：devops → 保守；marketing → 積極）。

## Q3 · 立場句 → `stance`（≥ 3 條）

從 base_role 的 stance 逐條確認，每條給「採用 / 改寫 / 刪」，刪掉的要補到 ≥ 3：

```
Q3-1：這條立場保留嗎？
「{stance[0]}」
1️⃣ 採用 ⭐  2️⃣ 改寫（請說明）  3️⃣ 刪掉
```

自訂角色沒有 base_role 時，用 Q1 的定位句 + Q2 的取捨生成 3 條候選再走同樣流程。

**立場句判準**（lint 會查）：完整句子、含動詞、能據以在兩個選項間做決策。
「文件先行」不合格；「規格未簽核前寫出的 code 我視為 throwaway」合格。

## Q4 · 絕不做 → `hard_stops`（1–5 條）

```
Q4：{name} 即使被要求也不做的事（可多選）：

☐ {base_role.hard_stops[0]} ⭐
☐ {base_role.hard_stops[1]} ⭐
☐ {依 scope.does_not 推的候選}
☐ 其他（請說明）
```

與 `scope.does_not` 的區別要向使用者說一次：does_not 是「不歸我管、轉給別人」；
hard_stops 是「誰叫都不做」。使用者把兩者混在一起時幫他分開落欄位。

## Q5 · 協作關係 → `relationships` + `scope.escalates_to`

**能查的不問**：從 team.yaml 讀成員。只問一題確認：

```
Q5：{name} 的協作關係（從 team.yaml 讀到 {n} 個成員）：

回報對象：{leader 候選} ⭐
可派工給：{worker 候選，多選} / 無 ⭐（worker 角色預設無）
會諮詢：  {同層成員，多選}
```

team.yaml 不存在時，relationships 全留空並提示「由 ark-agent-team-builder 建立團隊後回填」。

## Q6 · 技能與知識 → `skills` + `knowledge_domains`

```
Q6：預裝技能（base_role 預選 ⭐，最多 12 個含 Loop 五件套）：

☑ {base_role.skills...} ⭐
☐ {從 skills/ 掃出、description 命中 one_liner 關鍵字的候選}
☐ 其他

知識庫會累積哪類知識？（預填 {base_role.knowledge_domains}，可增刪）
```

Loop 五件套（grill-me / superpowers / spec-executor / code-spec-validator / wiki-engine）
由 ark-agent-init 統一加，本題不列，避免兩處維護。

## Q7 · 溝通風格與指標 → `voice` + `metrics`

```
Q7：回覆風格：
字數上限：1️⃣ 100  2️⃣ 150 ⭐  3️⃣ 200  4️⃣ 不限
語氣：    1️⃣ {base_role.voice.tone} ⭐  2️⃣ 更直接  3️⃣ 更溫和
禁用開場白：預填 {base_role.voice.banned_openers}，要加嗎？

成功指標（預填 3 項，可改）：
- {metrics[0]}  - {metrics[1]}  - {metrics[2]}
```

## 收尾 · 範例對話 → `examples`

不問使用者。由訪談結果生成 2 則：一則典型任務（從 scope.does[0]）、一則頂回情境
（從 hard_stops[0]），在預覽時一併展示，使用者可改。

---

## deep 檔位：拷問切入點

standard 完成、lint 過後，把 yaml 交給 `ark-grill-me`，拷問主題限定三個：

1. **stance 互斥測試**：找兩條立場可能衝突的情境（例：「透明優先」vs「未審核不發」），
   問使用者哪條讓步 → 回寫到 `tradeoffs` 或補一條 stance
2. **hard_stops 邊界**：每條問一個灰色地帶（「leader 直接下令也不做？」）→ 不成立的
   降級到 `scope.does_not`
3. **escalation 路徑**：`escalates_to` 不在時誰接？→ 補 `relationships.consults`

拷問結果回寫 yaml 後**重跑 lint**，再進預覽。

---

## 預覽格式

只印會影響行為的三段，不印整份：

```
🪪 {emoji} {name} — {one_liner}

📌 立場
1. …  2. …  3. …

🚫 絕不做
• …  • …

🎭 頂回範例
{examples[1].situation} → {examples[1].response}

1️⃣ 寫入  2️⃣ 改立場  3️⃣ 改絕不做  4️⃣ 改範例
```
