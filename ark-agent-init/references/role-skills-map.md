# 角色 Skills 對照原則

> 🔴 **唯一真相是各專案的 `scripts/sync_skills.py` 的 `MATRIX`**，不是本檔。
> 本檔只給「角色該裝哪個方向的 skill」的**原則**；實際清單以 sync_skills 為準。
> （曾經本檔硬編一份 skill 清單 + 各專案 sync_skills 各一份 → 兩套並存必漂移。）

## 為什麼不在這裡列死清單

- skill 庫（`ark-agent-skills`）會演化：改名、合併、deprecated。
- 各團隊領域不同，同一個 role 該裝的 skill 也不同（市場情報 vs 遊戲研發）。
- 硬編清單無法跟上 → 改成**由專案的 `sync_skills.py` 依領域定義 MATRIX**，
  本檔只保留「角色邊界」的通用原則。

## 角色 → skill 方向（原則）

| 角色 | 方向 | 常見 skill（例，非清單）|
|------|------|------------------------|
| **全員 COMMON** | 知識查詢 | `ark-wiki-engine` |
| **manager**（總機/dir=".") | 通用執行力：RAG + 規格/計畫 + 報告 + 需求澄清 | `ark-superpowers` `ark-project-planning` `ark-md-report` `ark-grill-me` |
| **leader**（統籌） | 拆解/派工/驗收 | `ark-project-planning` `ark-grill-me` |
| **admin**（維運） | 環境/健康/成本 | `ark-env-doctor` `ark-dashboard-health` `ark-cost-tracker` |
| **worker**（職人） | **依領域**（資料/研究/報告/開發…） | 依專案 MATRIX |

> 🔴 **只裝該角色該裝的** —— skill 會進 agent 的 context window，
> 全員裝同一批只是稀釋注意力。MATRIX 就是「角色邊界」的具體化。

## 如何裝（機制）

由專案的 `scripts/sync_skills.py` 從上游複製（不是 build_kiro 直接裝）：

```bash
python3 scripts/sync_skills.py            # 依 MATRIX 從 ~/kiro-cli/.kiro/skills 複製
python3 scripts/sync_skills.py --check    # 驗一致（doctor/CI 用）
```

- 上游庫：`~/kiro-cli/.kiro/skills`（`git clone igs-paddyyang-tw/ark-agent-skills`）
- skill 是**複本非 symlink**（symlink 跨機斷鏈）→ 靠 sync 重建 → gitignore 排除
- 前提：team.yaml `kiro_files.skills.policy: skip`（否則套件 `_deploy_skills` 推翻 MATRIX）
- 完整範例：`ark-agent-team-builder/examples/market-team/scripts/sync_skills.py`（6-agent MATRIX）
