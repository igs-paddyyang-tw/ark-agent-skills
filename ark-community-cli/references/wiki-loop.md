# 與知識庫閉環

```
Discord / X ──pull──▶ raw/ ──normalize──▶ records/ ──classify──▶ classify/
                                                                  │
                                              digest ◀────────────┘
                                                │
                     reports/weekly/{week}-community-digest.md  +  cases/{week}/F-*.md
                                                │
                                        loop handoff（清單）
                                                │
                              leader：wiki_guard → wiki_ingest（trust 依來源）
                                                │
                    knowledge/hoyeah/player-voice/pain-points/  events/
                                                │
                           營運／開發看 → 決定 → decisions/D-*.md（人寫）
                                                │
                        loop compare：決策前後 7 天同 cluster 頻次／情感
                                                │
                              reports/decisions/D-*-followup.md ──▶ 下週摘引用
```

## 兩個 role gate 造成的分工
- **worker 沒有 `wiki_ingest`**（team_mcp role gate）。所以 `loop handoff` 只產清單，不入庫；community-agent 把清單交 market-leader
- **wiki_guard 先跑**：清單裡每個檔案 leader 先 `wiki_guard scan`，掃到 Discord snowflake、username、注入句就退回

## handoff 清單格式（reports/weekly/{week}-handoff.json）

```json
{
  "week": "2026-W39",
  "items": [
    { "path": "cases/2026-W39/F-2026-W39-1.md", "target": "pain-points/", "suggested_tags": ["player-voice","bug","discord"],
      "trust": "llm-distilled", "provenance": "owned", "status_on_ingest": "seedling", "guard_required": true },
    { "path": "reports/weekly/2026-W39-community-digest.md", "target": "events/", "suggested_tags": ["player-voice","weekly"],
      "trust": "deterministic", "provenance": "mixed", "status_on_ingest": "seedling", "guard_required": true }
  ],
  "pii_scan": "PASS",
  "notes": "X 來源 provenance=public-third-party，痛點頁需分欄呈現"
}
```

trust 規則：統計數字（則數、分布）= `deterministic`；任何「代表句選取」「cluster 命名」「痛點描述」= `llm-distilled` → 入庫一律 `seedling`，人審才 mature。X 來源另標 `provenance: public-third-party`，wiki 頁要能一眼看出這是外部匿名聲音。

## decisions 回寫與比對

人在 `knowledge/hoyeah/player-voice/decisions/D-{date}-{n}.md` 寫：

```yaml
---
decision_id: D-2026-09-22-01
decided_on: 2026-09-22
based_on: [F-2026-W38-2]          # 哪些痛點
action: "9/25 熱修登入卡頓；公告補償 100 石"
owner: ops
expect: "F-2026-W38-2 頻次下降 ≥ 50%，neg 比例下降"
---
```

`loop compare --decision D-2026-09-22-01`：
1. 讀 `based_on` 的 cluster 代表句與 members 的 token 集
2. 在 records 中取決策日前 7 天、後 7 天，重跑同一 cluster 判定（token Jaccard 對代表句）
3. 產 `reports/decisions/D-2026-09-22-01-followup.md`：前後則數、distinct_authors、sentiment 分布、達成 `expect` 與否（deterministic 判定）、新冒出的相鄰 cluster
4. 下週 digest 自動引用這份 followup

這一步是整個閉環的意義：**決策的效果由資料驗證，不由決策者或報告宣稱。**

## 排程建議（scheduler.yaml）
- 每日 09:30：`pull discord` → `pull x --estimate`（每條 query）→ `pull x`（在預算內）→ `normalize` → `classify`
- 每週一 10:00：`digest --week` → `loop handoff` → 交 market-leader；`loop compare` 對所有 `decided_on` 在 7–14 天前的 decision
- 每月 1 日：raw/ 依 retention 清理；對一次 X Console 帳單 vs spend.jsonl
