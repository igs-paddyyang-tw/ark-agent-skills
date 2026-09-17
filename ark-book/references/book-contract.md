# 書籍契約（機器可解析）

下游消費者：`book_lint.py`、`book_build.py`、`book_register.py`、圖書館網站（讀 catalog.json）、
ark-wiki-engine ingest。原則：**不讀內文，只讀 book.yaml 與章節 frontmatter，就能決定這本書給誰、教什麼、進度到哪**。

## book.yaml（每本一份，必要）

```yaml
title: "用 ark-agent-skills 建立你的第一位個人助理"   # 人類可讀
slug: first-personal-agent                            # kebab-case，= 目錄名，= catalog key
subtitle: "從一個模糊目標到一位會自我驗收的 Agent"     # 選用
author: paddyyang                                      # 人名或 agent 名
version: 1                                             # 整數；內容有實質修改才遞增
status: draft                                          # draft | review | published
language: zh-Hant
level: beginner                                        # beginner | intermediate | advanced
audience: "研七新成員，會用 ChatGPT，沒建過 Agent"       # 一句話，具體到能判斷「我是不是讀者」
outcomes:                                              # 讀完能做什麼；動詞開頭；2–5 條
  - 用 ark-grill-me 把模糊目標拷問成一句可執行的目標
  - 用 team-design + role-profile 產出自己助理的 team-spec 與人格檔
  - 跑 prompt-spec-validator 驗收助理行為並讀懂 Drift Report
prerequisites: []                                      # 章節 slug 或外部條目；沒有就 []
scope_out:                                             # 明確不教什麼
  - 多 leader 團隊的路由設計
  - wheel 打包與部署細節
tags: [agent-team, onboarding, skill-chain]           # 只能用 wiki 受控詞彙
sources:                                               # 全書層級的主要素材
  - sources/agent-team-closed-loop-workflow.md
  - sources/hoyeah-interview-2026-09-10.md
chapters:                                              # 目錄，順序即閱讀順序；lint 核對檔案存在
  - 00-preface
  - 01-say-the-goal
  - 02-design-the-team
  - 03-give-it-a-soul
  - 99-appendix-glossary
shelf: agent-basics                                    # 圖書館書架分類（catalog 用；受控，見 library-integration.md）
style: felt                                            # 選用；View 軌風格，須在 assets/styles/_manifest.json（預設 library；見 styles.md）
cover:                                                 # 選用：圖書館封面資訊
  spine_color: green                                   # green | wine | navy | brown | brass
  emoji: "📗"
created: 2026-09-17
updated: 2026-09-17
```

### 欄位規則

- `slug` 必須等於目錄名，且全庫唯一 —— 這是 catalog 的 join key
- `outcomes` 每條動詞開頭且可驗證（「理解」「知道」不算，「用 X 產出 Y」「讀懂 Z」算）
- `tags` 對照 wiki 受控詞彙表；表中沒有的概念先用最接近的既有 tag，並在序或附錄的「詞彙表建議」提議新增，人審核入表
- `status: published` 時，所有章節 `status` 必須是 `published`，且 lint 不得有 FAIL
- `version` 遞增時，`updated` 必須更新；build 會把 `v{version}` 印在封面與頁尾
- `style` 不在 `_manifest.json` → FAIL；省略則用 manifest 的 default（library）。全書一種風格，不分章

## 章節 frontmatter（每章必要）

```yaml
---
book: first-personal-agent                # = book.yaml slug
chapter: 2                                # 整數，= 檔名前綴；序 = 0；附錄 ≥ 90
slug: design-the-team                     # = 檔名去掉前綴
title: "誰該在你的團隊裡：用 team-design 訪談出編制"
type: chapter                             # preface | chapter | appendix | exercise
level: beginner                           # beginner | intermediate | advanced
est_minutes: 20                           # 讀完 + 動手做的時間
punchline: "一個 worker 一個判準；判準不同就拆。"   # ≤ 40 字；讀者一週後還記得的一句
objectives:                               # 這章讀完能做什麼；1–3 條；動詞開頭
  - 跑一次 team-design standard 檔位並拿到 team-spec.yaml
  - 用六條編制原則判斷自己的編制要不要拆
prerequisites: [say-the-goal]             # 本書章節 slug 或外部條目
key_terms: [worker, leader, admin, 決策鎖]   # 本章「命名儀式」引入的術語
tags: [agent-team, team-design]           # 受控詞彙
sources:                                  # 本章主張的證據
  - sources/agent-team-closed-loop-workflow.md#閉環-a
  - ark-agent-skills/ark-agent-team-design/SKILL.md
trust: llm-distilled                      # deterministic（原文搬運）| llm-distilled（改寫/教學化）
confidence: high                          # high | medium | low（本章內容可信度）
status: draft                             # draft | review | published
---
```

### 欄位規則

- `chapter` 與檔名前綴一致：`02-design-the-team.md` ↔ `chapter: 2`, `slug: design-the-team`
- `punchline` 空白或超過 40 字 → FAIL：punchline 是整章的骨架，寫不出來就是章還沒想清楚
- `objectives` 與 book.yaml `outcomes` 不必一一對應，但全書 outcomes 的每一條至少要被一章 objectives 覆蓋（lint WARN）
- `trust: llm-distilled` 的章節在 wiki ingest 時強制 `status: seedling`，需人審核 —— 與 ark-wiki-engine 兩層信任模型一致
- `confidence: low` 的章節，build 會在章首顯示「本章素材不足，結論待驗證」的 callout

## 內文結構契約

七段標題固定（lint 檢查存在與順序，允許標題後加副標）：

| 順序 | 標題 | 必要 | lint 檢查 |
|---|---|---|---|
| 1 | `## 這章要解決的問題` | ✅ | 存在；含至少一個問號或「怎麼辦」 |
| 2 | `## 路線圖` | ✅ | 存在；2–5 個項目 |
| 3 | `## 內文` | ✅ | 存在；≥1 個 `[!ASK]`；每個 `key_terms` 至少出現一次 |
| 4 | `## 常見誤解` | ✅ | 存在；≥1 個 `[!MYTH]` |
| 5 | `## 動手做` | ✅（appendix 可省） | 存在；含 fenced code 或編號步驟 |
| 6 | `## 重點回顧` | ✅ | 存在；1–3 個項目；第一項含 punchline 關鍵詞 |
| 7 | `## 下一章` | ✅（最後一章與附錄可省） | 存在；≤ 2 句 |

序（`type: preface`）例外：只要求「為什麼有這本書」「這本書給誰」「讀完你會」「全書路線圖」四段。

## 教學元件標記（GitHub alert 語法）

```markdown
> [!ASK] 你可能會想說
> 直接寫 team.yaml 不就好了嗎？

> [!TIP] 白話
> 所謂決策鎖，其實就是「這個決定只有誰能下」而已。

> [!MYTH] 大家通常會以為
> leader 應該最忙。但其實 leader 只收斂不做事……

> [!TRY] 動手做
> ```bash
> python scripts/team_spec_lint.py team-spec.yaml
> ```

> [!NOTE] 補充
> [!WARNING] 注意
```

第一行 `[!TYPE]` 後可接標題文字；renderer 會把它變成 callout 的標題。這些在任何 Markdown 檢視器都仍是合法 blockquote，不依賴 renderer 也能讀。

## chunk 自足（與 ark-md-report 同源）

- 禁詞：如上所述、如前所述、上文提到、詳見上文、（見上）→ FAIL
- 警示：前者、後者、該問題、此問題 → WARN（同句即時對比可接受）
- 每個 `##` 章節可單獨被取出而不失義；主詞寫全名（「ark-agent-role-profile 的 profile_lint.py」，不寫「它的 lint」）
- 章節標題含檢索關鍵詞（「用 team-design 訪談出編制」優於「第二步」）
