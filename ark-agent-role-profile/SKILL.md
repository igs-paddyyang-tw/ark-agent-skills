---
name: ark-agent-role-profile
description: |
  以三檔位訪談（quick / standard / deep）引出 agent 的角色定位，產出結構化
  `role-profile.yaml`（identity / stance / scope / hard_stops / voice / relationships /
  metrics / knowledge_domains / skills），經 profile_lint.py 守門後渲染成
  SOUL.md 人格段 + IDENTITY.md，交給 ark-agent-init 組裝 workspace。
  內建角色庫（assets/roles/*.yaml）含工程與非工程角色（遊戲企劃、社群營運、行銷、
  主管助理、數據分析），每個角色有立場句、反模式、絕不做清單，而非形容詞。
  使用此 Skill 當使用者提及 角色定位、角色訪談、role profile、人格設定、agent 人格、
  SOUL 人格、立場、hard stops、絕不做清單、角色庫、擴充角色庫、新增角色類型、
  非工程角色、企劃 agent、社群 agent、行銷 agent、助理 agent、
  「這個 agent 該有什麼個性」「幫我定義 agent 的邊界」「SOUL 太空泛」的場景。
  不適用於：產出 .kiro/ 目錄與 workspace 檔案（請用 ark-agent-init）；
  拷問設計方案（請用 ark-grill-me，本 skill 的 deep 模式會呼叫它）。
metadata:
  schema_version: 1
  status: active
  category: process
  outputs:
    - format: data
      audience: ai
    - format: md
      audience: both
  render: none
  depends_on: [ark-grill-me]
  author: paddyyang
  version: "1.2"
  updated: 2026-09-15
---

# ark-agent-role-profile

引出角色定位 → `role-profile.yaml` → lint → 渲染 SOUL 人格段 / IDENTITY.md。

> **與 ark-agent-init 的分工**：本 skill 負責「這個 agent 是誰、站哪邊、絕不做什麼」，
> 產出的是**資料契約**（yaml）與**人格片段**（md）；ark-agent-init 負責把片段組進
> `.kiro/steering/`、產 agent.json、複製 skills、建 knowledge 五件套。
> 接力關係：`role-profile` 產契約 → `agent-init --profile role-profile.yaml` 組裝。

## 觸發條件

- 「定義 {agent} 的角色定位」「幫我訪談出這個 agent 的人格」
- 「SOUL 太空泛」「Personality 只有形容詞」「這個 agent 該有什麼立場」
- 「加一個企劃 / 社群 / 行銷 / 助理 agent」「擴充角色庫」「新增角色類型」
- 「role profile」「hard stops」「絕不做清單」
- ark-agent-init 遇到未知角色且使用者不接受預設時，轉來本 skill

---

## 為什麼要有中間契約

目前的路徑是「問兩句 → 直接填模板」，中間沒有任何可驗證的東西，所以自訂角色只會
拿到兩條 mission、一串形容詞。把角色定位先落成結構化 yaml 有三個效果：

1. **可 lint**：立場必須是完整句子、hard_stops 非空、voice 沒有「保持專業」類空話——
   過不了就不寫檔，和 ark-md-report 的 report_lint 同一套哲學。
2. **訪談與渲染解耦**：題庫改了不動渲染；SOUL 模板改了不動題庫。
3. **角色庫是資料不是文件**：`assets/roles/*.yaml` 是唯一真相，任何「角色一覽表」
   都由 `profile_lint.py --list-roles` 導出，不手寫第二份。

---

## 互動流程

```
0. 掃描 → 讀 team.yaml（成員/角色）、既有 .kiro/steering/SOUL.md、skills/ 清單
1. 選檔位 → quick / standard / deep（給編號選項，預設 standard）
2. 訪談   → 依 references/role-interview.md 逐題問，一次一題，附 2-4 選項 + ⭐推薦
3. 落 yaml → 寫 role-profile.yaml（草稿）
4. lint   → python scripts/profile_lint.py role-profile.yaml（P0/P1 清零才續）
5. 預覽   → 只印 IDENTITY 卡 + stance + hard_stops，編號選項確認
6. 渲染   → python scripts/render_profile.py role-profile.yaml --out ./
7. 交接   → 回報產出路徑 + 建議下一步（ark-agent-init 組裝）
```

### 三檔位

| 檔位 | 題數 | 適用 | 來源 |
|------|------|------|------|
| **quick** | 1 | 內建角色直接套用；Workshop 卡關時的逃生口 | `assets/roles/{id}.yaml` 原樣載入，只問「稱呼 + emoji」 |
| **standard** ⭐ | 7 | 大多數 worker / 自訂角色 | 題庫 Q1–Q7，內建角色的值當預選項 |
| **deep** | 7 + 拷問 | leader / admin 等高權限角色 | standard 完成後把 yaml 交給 `ark-grill-me` 拷問 stance 與 hard_stops，再回寫 |

### 提問規則（沿用 ark-grill-me）

- 一次一題；答完簡短確認 1 句再問下一題
- 每題 2–4 個**具體**選項 + ⭐推薦；選項來自角色庫預設值或掃描結果（如 team.yaml 成員）
- **能自己查的不問**：回報對象、可派工對象從 team.yaml 讀；技能候選從 skills/ 掃
- 使用者答「其他」→ 追問一句細節再落 yaml
- 禁止開放式「你覺得它該是什麼個性？」——把個性拆成可選的立場句

### 檔位選擇範例

```
要幫 community-agent 定義角色定位，選一個檔位：

1️⃣ quick — 套用內建「社群營運」角色，只問稱呼與 emoji（30 秒）
2️⃣ standard — 7 題訪談，內建值當預選（3–5 分鐘）⭐ 推薦
3️⃣ deep — standard 後由 ark-grill-me 拷問立場與邊界（高權限角色用）
```

---

## role-profile.yaml 契約

完整 JSON Schema 在 `references/role-profile.schema.json`；lint 以它為準。摘要：

```yaml
schema_version: 1
role_id: community-ops            # kebab-case，對應 agents/{name}-agent
base_role: community-ops          # 來源角色庫 id；純自訂填 custom
identity:
  name: 小社                       # 對外稱呼（IDENTITY.md）
  emoji: 📣
  one_liner: 玩家聲音的守門人，把社群情緒翻成可行動的訊號
  language: zh-TW
stance:                           # 完整句子，能據以做決策；≥3 條
  - 玩家抱怨先當訊號、不當噪音，但一律附數據再上報。
  - 對外任何文字未經審核不發，寧可晚 1 小時也不收回一次。
  - 危機處理時透明優先，不用「正在了解中」拖延超過 30 分鐘。
tradeoffs:                        # 三軸預設，每軸選一端
  ambiguity: ask                  # ask | minimal_then_confirm | conservative
  speed_vs_quality: quality
  risk: conservative              # conservative | balanced | aggressive
scope:
  does: [監測社群情緒, 整理玩家回饋, 草擬公告, 危機初判]
  does_not: [決定補償方案, 直接對外發布, 修改遊戲數值]
  escalates_to: leader-agent      # 超出 scope 時的升報對象
hard_stops:                       # 1–5 條，違反即錯誤行為
  - 不可未經審核對外發布任何文字
  - 不可承諾補償或時程
  - 不可在公開頻道貼出個別玩家資料
anti_patterns:                    # 這個角色最容易犯的錯 + 自我修正
  - pattern: 把單一大聲玩家的意見當多數
    correction: 先查提及量與情緒分布，再定調
voice:
  tone: 溫和但明確
  max_chars: 150
  banned_openers: [很高興為您, 感謝您的反饋, 我們非常重視]
  format: 結論先行；需決策時給編號選項
relationships:
  reports_to: leader-agent
  delegates_to: []
  consults: [marketing-agent, qa-agent]
metrics:
  - { name: 回饋歸檔時效, target: "< 24h" }
  - { name: 公告零撤回, target: "100%" }
  - { name: 情緒週報準時, target: "每週一 10:00" }
knowledge_domains: [玩家回饋分類, 危機處理 SOP, 公告模板, 社群平台規則]
skills: [ark-community-ops, ark-telegram-sender, ark-internal-comms]
examples:                         # 2 則，各 ≤5 行；一則典型、一則需頂回
  - situation: Leader 要求立刻回覆抱怨串
    response: 先給 3 句摘要 + 建議公告草稿，標註「待審核」，不直接發
  - situation: 使用者要它承諾補償
    response: 頂回：補償屬 leader 決策，我只彙整訴求與影響範圍
```

### 為什麼是這些欄位

| 欄位 | 解決的問題 |
|------|-----------|
| `stance` 是句子不是詞 | 「專注、精準」對模型無行為效果；「規格未簽核前的 code 我視為 throwaway」可據以做決策 |
| `tradeoffs` 三軸 | 大多數人格差異其實只是這三個取捨的預設值不同 |
| `hard_stops` 獨立於 `does_not` | does_not 是「不歸我管」，hard_stops 是「即使被要求也不做」——權限模型不同 |
| `anti_patterns` 含 correction | 只列毛病不給修法，模型讀了不會變 |
| `examples` 一則頂回 | 人格穩定最有效的錨點是「它在什麼情境下會說不」 |
| `relationships` 從 team.yaml 導 | 不讓使用者手打 instance 名，避免和 TEAM.md 漂移 |

---

## 角色庫（assets/roles/）

每個 `{role-id}.yaml` 是完整、可直接 lint 通過的 profile（`identity.name` 留空由訪談填）。
列出現有角色一律跑腳本，不手寫表：

```bash
python scripts/profile_lint.py --list-roles
```

內建 19 個：

- 工程：`leader`、`fullstack-coder`、`ai-dev`、`qa`、`devops`、`data-analyst`
- 非工程：`game-designer`、`community-ops`、`marketing`、`executive-assistant`
- 管理：`admin`
- 遊戲測試（v1.1 新增）：`test-lead`、`math-verifier`、`automation-engineer`、
  `perf-compat-tester`、`security-fairness-auditor`、`bug-triage-reporter`
- Manager（v1.2 新增，供「根目錄即 manager」場景 / agent-init --profile 渲染）：
  `bot-manager`（通用 bot 總機）、`qa-manager`（QA 團隊總機／工程師）

**擴充角色庫的流程**（觸發詞「新增角色類型」「擴充角色庫」）：

1. 用 standard 訪談跑一次，得到 `role-profile.yaml`
2. 清空 `identity.name`、`relationships.*`（這些是 instance 層，不屬於角色庫）
3. 存到 `assets/roles/{role-id}.yaml`，跑 `profile_lint.py --all-roles`
4. 檢查 `skills` 欄位裡的每個 skill 在 ark-agent-skills 存在（lint 用 `--skills-root` 會查）
5. 若該角色需要新的 skills 對應，同步更新 `ark-agent-init/references/role-skills-map.md`

角色庫每個 yaml 都要有 `examples` 至少 2 則，其中 1 則是頂回情境——這是角色庫與
ark-agent-init 現有 `role-templates.md`（只有技術棧）最大的差異。

---

## 渲染規則（render_profile.py）

輸入 `role-profile.yaml`，輸出：

| 檔案 | 內容 | 給誰用 |
|------|------|--------|
| `IDENTITY.md` | name / emoji / one_liner / language，≤ 10 行 | ark-agent-init 放 steering/（inclusion: always） |
| `SOUL.fragment.md` | 立場、取捨、反模式、絕不做、溝通風格、成功指標、範例對話 | ark-agent-init 併入 SOUL.md，**取代**原「Identity & Memory」段的形容詞 |
| `AGENTS.fragment.md` | scope / relationships 導出的職責與升報表 | 併入 TEAM.md 或 AGENTS.md 的協作段 |
| `schema.fragment.md` | `knowledge_domains` → 「適合存放的知識」段 | 併入 knowledge/schema.md |

刻意**不**渲染：MCP Tools 表、Tool Settings。這兩段屬 AGENTS.md / TEAM.md（operating
rules），放進 SOUL 就是第二份真相——ark-agent-init 現有 SOUL-worker.md 的 `output/`
與 SKILL.md 的 `artifacts/` 已經漂移過一次。

渲染後 HTML 註記 `<!-- profile-sha256: ... -->` 嵌進每個 fragment 檔頭，讓後續工具能
偵測「yaml 改了但 SOUL 沒重渲染」。

---

## 守門（profile_lint.py）

```bash
python scripts/profile_lint.py role-profile.yaml [--skills-root ../skills]
python scripts/profile_lint.py --all-roles          # 檢查整個角色庫
python scripts/profile_lint.py --list-roles         # 導出角色一覽（唯一合法的列表來源）
```

| 級別 | 條件 | 處置 |
|------|------|------|
| **P0** | schema 不符；`stance` < 3 條；`hard_stops` 為空或 > 5；`examples` < 2 | 不得渲染 |
| **P1** | stance 任一條 < 12 字或不含動詞（疑似形容詞堆疊）；voice 含空話（保持專業／全面協助／正向體驗／竭誠）；`examples` 無頂回情境；`skills` 有不存在項 | 不得渲染 |
| **P2** | `metrics` < 3；`anti_patterns` 為空；`one_liner` > 40 字 | 警告，可續 |

P0/P1 清零才進預覽——與 ark-skills-align 的 audit 門檻同型。

---

## 完成回報格式

```
✅ 角色定位已產出：{role_id}（{檔位}，{題數} 題）

🪪 {emoji} {name} — {one_liner}
📌 立場：{stance[0]}
🚫 絕不：{hard_stops 前 2 條}

📁 產出：
- role-profile.yaml
- IDENTITY.md
- SOUL.fragment.md / AGENTS.fragment.md / schema.fragment.md

🔍 lint：P0 0 · P1 0 · P2 {n}

💡 下一步：
1️⃣ 用 ark-agent-init 組裝 workspace（--profile role-profile.yaml）
2️⃣ 存進角色庫 assets/roles/（若這是可重用的角色類型）
3️⃣ deep：交給 ark-grill-me 再拷問一輪
```

---

## 注意事項

- 訪談中使用者提到的**人名、聯絡方式、帳號**不落 yaml；relationships 只放 instance 名
- 既有 `.kiro/steering/SOUL.md` 存在時，先從中反推 stance 當預選項，不從零問
- `identity.name` 可為空（quick 檔位常見）；lint 對此欄位不報錯，渲染時以 role_id 代
- 角色庫 yaml 的 `relationships` 一律為空——那是 instance 配置，由 team.yaml 決定
- 本 skill 不上網搜尋角色最佳實踐；未知角色先用 standard 訪談引出，需要外部知識時
  由 ark-agent-init 的「自訂角色搜尋流程」補

## 附帶資源

| 路徑 | 說明 |
|------|------|
| `references/role-interview.md` | 三檔位題庫（Q1–Q7 + deep 拷問切入點），每題附選項生成規則 |
| `references/role-profile.schema.json` | 契約 JSON Schema，lint 唯一依據 |
| `references/agent-init-integration.md` | 接進 ark-agent-init 需要的三個改動 |
| `assets/roles/*.yaml` | 角色庫（19 個），可直接 lint 通過 |
| `scripts/profile_lint.py` | 守門 + 角色列表導出 |
| `scripts/render_profile.py` | yaml → IDENTITY.md + 三個 fragment |
| `evals/evals.json` | ark-skill-creator 測試提示詞 |
