# frontmatter metadata schema v1

每個 active skill 的 SKILL.md frontmatter 必須符合：

```yaml
---
name: <string，必填，必須 == 目錄名>          # 違反 → P0
description: |                                # 必填，觸發描述
  <what + when，含具體觸發詞；遵循觸發詞治理矩陣>
metadata:
  author: paddyyang
  schema_version: 1                           # 缺 → P2
  category: process|scaffolder|pipeline|view|document|domain|ops   # 缺或非法 → P1
  outputs:                                    # 缺 → P1
    - { format: md|html|png|pdf|code|data|office, audience: ai|human|both }
  render: html|none                           # 報告類必填，其餘可省（視同 none）
  depends_on: [<skill-name>, ...]             # 選填
  status: active|deprecated                   # 省略視同 active
  version: "<x.y>"                            # 選填，沿用既有
  updated: <YYYY-MM-DD>                       # 選填，沿用既有
  tested_against:                             # 消費端型 skill 必填（D-7）→ 缺 P2 AL-107
    <外部套件/工具名>: "<版本>"                #   例：ark_team_agent: "1.8.4"
---
```

### `tested_against` 的形狀（2026-09-17 提案）

D-7 只定了「消費端型必填」，**沒有定值的格式**，而 audit 只檢查「有沒有值」。
這裡先定成 **name → version 的 mapping**（一個 skill 可能同時依賴多個外部件，
例如 `ark-db-query` 有六種 driver），要改由訂 D-7 的人決定。

🔴 **只填「真的測過的」** —— 這個欄位的語意是「針對哪一版寫並驗過」。
沒有實測來源就**留空**（維持 AL-107 的 P2），不要為了消掉計數而填一個看起來合理的版本：

> 憑空的版本比空白更糟 —— 空白代表「還沒驗」，而填了代表「驗過這一版」。
> 後者會讓下一個人跳過驗證。（同本 repo 記過的「憑空的預設值比沒有設定更糟」。）

現況：`ark-agent-bot-builder`／`ark-agent-team-builder`／`ark-db-query` 有實測來源已填；
`ark-weknora-cli`／`ark-docker-deploy` **查無來源，刻意留空**。

## deprecated stub 規格

被合併/移除的 skill 目錄，二擇一：

**A. 純 README stub（建議）**：目錄只留 README.md，內容含
「DEPRECATED」字樣、遷移去向連結、deprecation 日期（YYYY-MM-DD）、保留期限。

**B. SKILL.md 標記**（過渡期用）：frontmatter `metadata.status: deprecated`，
description 首行必須是 `[DEPRECATED → <target>] ...`，audit 才會跳過 schema 檢查。

## 報告類 MD frontmatter（產出物，非 SKILL.md）

報告類 skill 的**產出 MD** 遵循 `docs/report-frontmatter-standard.md`
（type、date、title、tags、score?、source_skill），tags 只能用 wiki 受控詞彙表。
本 schema 管 SKILL.md 自身；兩者不要混淆。
