# 範例包：market-team（市場情報團隊完整實例）

> 這是用 `ark-agent-team-builder` v3.0 **實際建出來的完整團隊實例**，
> 領域為**市場情報**。放在這裡當「長好的樣子」給人對照 ——
> 與 `references/templates/*.tpl`（填空用範本）互補：**範本教填空，本例教全貌**。
>
> 🔴 這是**特定領域**（市場情報）的實例，不是通用範本。建別種團隊時，
> 結構可照抄，但 6 個角色的 SOUL 人格要換成你的領域（或用 `ark-agent-init` 重產）。

## 打造完整團隊 = 三個 skill 分工

這個實例是三個 skill 協作的產物，各管一層：

| 階段 | skill | 管什麼 | 對應本實例 |
|------|-------|--------|-----------|
| ① 架構 | `ark-agent-team-builder` | 裝 wheel + 產 team.yaml/scheduler/start.py + 驗證架構 | `team.yaml`（6 instance）· `start.py` · `validate_team.py` |
| ② 基礎 | `ark-agent-init` | 每個 agent 的人格 + 基礎知識 + 多 CLI 入口 | 6 個 `SOUL.md` · `AGENTS.md` · `knowledge/` 骨架 |
| ③ 專業 | `ark-agent-skills`（`sync_skills.py`）| 依角色矩陣裝各 agent 的專業技能 | `scripts/sync_skills.py`（6-agent 矩陣 → 38 skill）|

```
① 定架構（誰在團隊）→ ② 給靈魂（人格/知識）→ ③ 給工具（專業 skill）
   team.yaml            SOUL/AGENTS/knowledge      sync_skills.py 依矩陣
```


## 這個實例示範了什麼

| 面向 | 實例怎麼做 |
|------|-----------|
| **編制** | 6 instance：manager（總機 dir=".") + leader + admin + 3 worker |
| **manager dir="."** | `market-agent` 的 steering 在**根目錄** `.kiro/steering/`，不在 `agents/` |
| **雙知識櫃** | `knowledge/market-team/`（自產）+ `shared/`（共用），對應 team.yaml 的 `knowledge_search_order` |
| **記憶歸記憶** | `memory/archive/`（不放 knowledge） |
| **完整 team.yaml** | defaults / kiro_files / channel / access / cost_guard / hang_detector / instances / health_port 全區塊 |
| **scheduler** | 2 個啟用 job + 3 個 `enabled: false` 骨架（等資料源就緒再開） |
| **steering 人格** | 每個角色含「🎭 人格與語氣」段（基調 / 回報風格 / 無事回報） |

## 對應編制表

| instance | role | working_directory | 職責 |
|----------|------|-------------------|------|
| market-agent | manager | `.`（根目錄） | 🗺️ 總機、意圖路由、知識查詢 |
| leader-agent | leader | agents/leader-agent | 🎯 統籌、派工、驗收 |
| admin-agent | admin | agents/admin-agent | 👑 維運、監控、費控 |
| competitor-agent | worker | agents/competitor-agent | 🔍 競品分析 |
| trend-agent | worker | agents/trend-agent | 📈 趨勢研究 |
| report-agent | worker | agents/report-agent | 📝 情報報告 |

## 怎麼用這個範例

有兩種用法：**A. 對照學習**（看骨架怎麼組）、**B. 直接跑起來**（複製改成你的團隊）。

### A. 對照學習

1. 對照 `team.yaml` 看「6 instance + 完整設定區塊」怎麼組
2. 對照目錄結構看「雙知識櫃 + memory + artifacts」怎麼擺
3. 對照各 SOUL 看「角色人格段」怎麼寫

### B. 從骨架跑起來（範例只含骨架，依賴/機密/產物要自己補齊）

```bash
# 0. 複製這個範例當你的專案起點
cp -r examples/market-team ~/my-team && cd ~/my-team

# 1. 裝套件（擇一）
#    a) 系統層（本機慣例）：
pip install --user --break-system-packages <ark_team_agent-*.whl>
#    b) 或建 venv：
uv venv --python 3.13 && uv pip install --python .venv/bin/python <ark_team_agent-*.whl>

# 2. 補 skill 複本（範例不含 4.5MB skill，靠 sync 從上游重建）
#    前提：本機有 ~/kiro-cli/.kiro/skills（git clone ark-agent-skills）
python3 scripts/sync_skills.py            # 依角色矩陣拉齊 38 個 skill
python3 scripts/sync_skills.py --check    # 驗一致

# 3. 填機密（範例只給 .env.example）
cp .env.example .env
#    編輯 .env：填 MARKET_TELEGRAM_BOT_TOKEN（BotFather 申請的專屬 token）

# 4. 啟動
python3 start.py                          # 或 systemctl --user start <svc>

# 5. 兩階段驗證（🔴 別在第一階段就測私訊）
#    階段一（~20s）：daemon + TG 上線
curl -s localhost:23040/api/health        # 看 instances.running == total
#    階段二（首次 2–4 分鐘）：kiro-cli backend 冷啟就緒才會回私訊
#    看到 log 印 "All tools are now trusted" 或 "💬 REPLY" 才代表可處理
```

> 🔴 **改成你的團隊時要換**：6 個角色 SOUL 人格、`health_port`、`knowledge_search_order`
> 的櫃名、`.env` 的 TG token、`sync_skills.py` 的 `MATRIX`（各 agent 該裝哪些 skill）。

### 為什麼範例不含這些（不是缺，是刻意）

| 沒放 | 原因 | 怎麼取得 |
|------|------|---------|
| `.kiro/skills/`（4.5MB） | skill 是**複本非 symlink**（symlink 跨機斷鏈） | 跑 `scripts/sync_skills.py` |
| `.venv/` | 虛擬環境因機而異 | `uv venv` + 裝 wheel |
| `.env` | 機密（TG token） | 從 `.env.example` 複製填 |
| `state/` `instances/` `output/` | 套件執行期自動產 | 啟動時自動生 |
| `.index/` | BM25 索引自動產物 | `wiki_index.py build` 或啟動時生 |

> 💡 這是慣例：**範例放骨架（能長好的樣子），不放依賴/機密/執行產物。**
> 骨架 + `sync_skills.py` + `.env.example` 三者合起來就能重建出可跑的完整體。
