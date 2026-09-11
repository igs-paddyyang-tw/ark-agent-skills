---
inclusion: always
---
# Memory — 專案狀態

> 持久化上下文，避免每次重問。每完成一個段落更新。
>
> 🔴 **自我保護上限（與套件 `_builtin:memory-consolidate` 一致）：**
> - 日期分節 **> 2 週（`keep_days=14`）** 由舊往新搬到 `memory/archive/`
>   （記憶歸記憶，不進 knowledge；1.8.1 起）。
> - 檔案 **< 8 KB（~2000 tokens）不處理** —— 小檔硬歸檔只會變吵。
> - 超過 **位元組預算（`max_bytes`）** 會繼續由舊往新歸檔到降下來為止；
>   若連 2 週內的段落都超標 → **停住並提醒**「這個約束目前滿足不了」，不動近期內容。
> - **非日期分節（`## 專案快照`、`## 待辦`）永遠保留** —— 它們是當前狀態不是歷史。
>
> 💡 這層是**機械歸檔**（確定式、無 LLM，套件排程自動跑）。看到本檔明顯膨脹
> （> 8 KB 且塞滿舊日期段落）就該讓 consolidate 跑一輪或手動歸檔，別讓 always-on
> 的 MEMORY 一直吃 context。

## 專案狀態（2026-07-15）

- 架構：TG Bot gateway + Gemini Chat + Agent CLI 派工
- 團隊：8 agents，派工由 Ark Agent 統一調度
- 開發模式：個人開發者，無正式 Sprint，按需求逐步迭代

## 技術決策

- 派工機制：dispatch_to_agent tool，由 Ark Agent ReAct Loop 決定
- Spec 格式：Markdown（背景/目標/驗收標準/技術約束）
- 驗收：功能驗證 + 邊界測試 + 文件完整度

## 踩坑紀錄

- 單一 Agent 不宜超過 3 個並行任務（context 會混亂）
