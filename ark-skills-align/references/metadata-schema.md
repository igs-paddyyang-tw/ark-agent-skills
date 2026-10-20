# frontmatter metadata schema（現行 1.2）

> **本檔是 SKILL.md 欄位的唯一權威**；詞彙與判準見 `taxonomy.md`，程式權威是 `scripts/audit_skills.py`。
> （`docs/skill-metadata-schema.md` 已改為指路頁 —— 1.1 時代曾有三份規格互相矛盾。）

每個 active skill 的 SKILL.md frontmatter 必須符合：

```yaml
---
name: <string，必填，必須 == 目錄名>          # 違反 → P0
description: |                                # 必填，觸發描述
  <what + when，含具體觸發詞；遵循觸發詞治理矩陣；含「不適用於→改用 X」>
metadata:
  author: paddyyang
  schema_version: "1.2"                       # 缺或非法 → P2
  category: process|scaffolder|pipeline|view|document|ops   # 產出什麼；缺或非法 → P1
  form: executor|instruction                  # agent 怎麼用；1.2 缺 → P1
  domain: general|game                        # 屬於哪個業務；1.2 缺 → P1
  outputs:                                    # 缺 → P1
    - { format: md|html|png|pdf|code|data|office, audience: ai|human|both, via: <skill>? }
  render: html|none                           # 報告類必填，其餘可省（視同 none）
  depends_on: [<skill-name> | {name, version}, ...]   # 選填；字串形式 → P2 AL-104（建議帶版本範圍）
  status: active|experimental|deprecated      # 省略視同 active；manifest 只收 active
  version: "<x.y.z>"                          # semver；缺或非 semver → P2 AL-101
  updated: <YYYY-MM-DD>                       # 最後「內容」修改日；缺 → P2
  tested_against:                             # 消費端型 skill 必填（D-7）→ 缺 P2 AL-107
    <外部套件/工具名>: "<版本>"                #   例：ark_team_agent: "1.8.4"
  replaces: [<被取代的 MCP／舊工具>]           # 選填
  upstream: <url>                             # 選填：鏡像自外部 skill 時（另有 upstream_sha、upstream_synced）
---
```

### schema_version

| 值 | 意義 |
|---|---|
| `"1"` | 初版欄位 |
| `"1.1"` | 受控詞彙全名化 ＋ `category: executor`（2026-09-04；**已廢止的混軸用法**） |
| `"1.2"` | 三軸：`form`、`domain` 必填，category 不含 executor／domain（2026-10-20） |

舊 schema 的消費端複本：缺 form／domain 報 P3、category 為 executor／domain 報 P2，過渡期不擋。

### 版號規則

- **內容變了就升版**：tree_hash（`gen_manifest.py`，排除 `__pycache__`、`.pyc`、頂層 `release/`）變動即應升 version，
  否則 `release/index.json` 會出現同版號對應多個 hash
- 只改 metadata 也算（升 patch）；腳本行為或契約變更升 minor；破壞性升 major
- `updated` 記最後**內容**修改日 —— 別填批次操作日（會宣稱不存在的新鮮度）

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
