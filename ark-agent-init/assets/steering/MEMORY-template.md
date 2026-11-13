---
inclusion: always
---
# 🧭 {PROJECT} — 記憶導覽

> 這份是「**記憶導覽**」，不是事件流水。每次對話都會注入 context，所以只放**指路 + 判準級精華**。
> 記憶規則的**單一權威**是 `AGENTS.md`「記憶怎麼用」—— 本檔、`BRAIN.md`、`SOUL.md` 都引用那裡，不另立一套。
> 架構說明見 ark-agent-init `references/memory-architecture.md`（ark_team_agent ≥ 1.11.0）。

## 🧭 記憶住在哪

| 想找什麼 | 去哪 | 誰寫 | 進 context |
|---|---|---|---|
| 可複用判準（怎麼判斷） | `.kiro/steering/BRAIN.md` | ✋ 人 | ✅ 常駐 |
| 導覽 + 常駐定案 + 最近 20 行里程碑 | 本檔 | ✋ 人 | ✅ 常駐（≤ 20 KB，`memory_check.py` 守門） |
| 持久事實（下個月還有用） | `memory/memory.md` | 🤖 `memory-distill` 蒸餾 | 🔸 可選 |
| 近期事件流水 | `memory/daily/YYYY-MM-DD.md` | 🤖 bot 自動／✋ team 收尾手寫 | ❌ 不注入 |
| 舊事件、輪替出去的里程碑 | `memory/archive/YYYY-MM.md` | 🤖 `_builtin:memory-consolidate`／✋ `memory_check.py --rotate` | ❌ 按需查 |

## 📌 專案快照

- **建立日期：** {DATE}
- **狀態：** 初始化

## 🔒 常駐定案（一行一條；有新定案就改寫該條，不追加）

- （尚無）

## 📌 近期里程碑（最近 20 行、每行 ≤ 160 字；滿了 `memory_check.py --rotate`）

- （尚無）—— 格式：`- **YYYY-MM-DD** {一句話判準級結論} → {細節指路}`

## 待辦

- [ ] （填入）

---

> 🔴 **什麼不寫這裡**：每次任務的進度、排程巡檢結果、一次性操作 → 寫 `memory/daily/`。
> 只有「下週還要被常駐讀到的判準」才升級成一句里程碑；加之前跑 `memory_check.py`（rc≠0 不提交）。
> 上限：整檔 ≤ 20 KB、里程碑 ≤ 20 行、每行 ≤ 160 字、待辦 ≤ 15 項、`## YYYY-MM-DD` 分節 ≤ 5 —— 超過照 `references/memory-architecture.md` §2.1 處理。
