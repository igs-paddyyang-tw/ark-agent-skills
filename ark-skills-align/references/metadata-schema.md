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
---
```

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
