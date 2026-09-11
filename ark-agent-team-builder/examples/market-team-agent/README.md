# 範例包：market-team-agent（市場情報團隊完整實例）

> 這是用 `ark-agent-team-builder` v3.0 **實際建出來的完整團隊實例**，
> 領域為**市場情報**。放在這裡當「長好的樣子」給人對照 ——
> 與 `references/templates/*.tpl`（填空用範本）互補：**範本教填空，本例教全貌**。
>
> 🔴 這是**特定領域**（市場情報）的實例，不是通用範本。建別種團隊時，
> 結構可照抄，但 6 個角色的 SOUL 人格要換成你的領域（或用 `ark-agent-init` 重產）。

## 這個實例示範了什麼

| 面向 | 實例怎麼做 |
|------|-----------|
| **編制** | 6 instance：manager（總機 dir=".") + leader + admin + 3 worker |
| **manager dir="."** | `market-agent` 的 steering 在**根目錄** `.kiro/steering/`，不在 `agents/` |
| **雙知識櫃** | `knowledge/market-team-agent/`（自產）+ `shared/`（共用），對應 team.yaml 的 `knowledge_search_order` |
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

1. 對照 `team.yaml` 看「6 instance + 完整設定區塊」怎麼組
2. 對照目錄結構看「雙知識櫃 + memory/archive + artifacts」怎麼擺
3. 對照各 SOUL 看「角色人格段」怎麼寫
4. **不要直接複製當你的專案** —— 換領域、換角色、換 port、填自己的 TG token

## 不含（刻意排除）

- `.index/`（BM25 索引，自動產物，跑 `wiki_index.py build` 會生）
- `.env`（機密；只留 `.env.example` 骨架）
- `.venv/`（各自裝 wheel）

> 建立紀錄見專案 MEMORY「2026-09-11 建 market-team-agent」段。
