---
inclusion: always
---
# market-team-agent 共用規範

> 所有回覆使用**繁體中文**。每完成一個段落更新 `memory/`。
> All tools are trusted.

## 回覆使用者規則

- 結論先行、繁體中文、精簡
- 需要決策時用編號選項：`1️⃣ … 2️⃣ … 3️⃣ …`
- 不貼 raw stdout / stack trace / JSON —— 先分類再說重點

## 情報工作流（SDD 精神）

① 查知識庫（market-team-agent / shared）→ ② web 查最新 → ③ 蒸餾入 wiki → ④ 產報告 → ⑤ 更新記憶

## 知識庫規則（記憶歸記憶、知識歸知識）

> 🔴 情報知識存 `knowledge/`；經驗記憶存 `memory/`（歸檔在 `memory/archive/`，**不進 knowledge**）。

### 分櫃判準（依產出來源）

| 這份知識是… | → 櫃 |
|---|---|
| market-team-agent 自己分析產出的情報 | `knowledge/market-team-agent/`（或各 agent 私有）|
| 排程蒸餾 / 使用者放入 / 跨 agent 共用 | `knowledge/shared/` |

| 路徑 | 用途 | 權限 |
|------|------|------|
| `knowledge/shared/wiki/` | 共用情報結構化知識 | 只由 ingest 產出，禁止手寫 |
| `knowledge/shared/raw/` | 共用原始素材（給人查證） | 只新增，不改既有檔 |
| `memory/archive/` | 記憶歷史歸檔 | 記憶層，不在 knowledge |
| `agents/<name>/knowledge/` | 各 agent 私有情報 | 各自維護 |

- `raw/` 唯讀；**知識庫都經蒸餾**：raw（給人）→ ingest → wiki（給 AI）
- 改 wiki 後同步該櫃 `index.md` + `log.md`（append-only）；所有 wiki 頁面要有 frontmatter

## 禁止事項

- 🚫 情報無來源就當事實
- 🚫 貼 raw stdout / JSON

## 失敗模式

- 同類錯誤連續 2 次 → 停止，換根本不同的方法

---

> 💡 團隊派工規範（`reply()` 出口、`send_to_instance`、成員編制）屬團隊模式，
> 見 `TEAM.md`（由 ark_team_agent 依 team.yaml 動態產生，inclusion: manual）。
