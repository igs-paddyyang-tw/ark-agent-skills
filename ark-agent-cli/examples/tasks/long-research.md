# 目標

對「{TOPIC}」做資料蒐集與整理，產出一份 {OUTPUT_PATH} 的 Markdown 報告（≥ {MIN_SOURCES} 個來源，每個論點附來源）。
完成定義：報告檔存在、章節齊全（背景 / 現況 / 比較 / 風險 / 建議 / 來源）、每段都有來源連結。

## 環境

- 工作目錄：{CWD}
- 可用：web 搜尋、讀網頁、寫檔；產物放產物目錄，最終報告寫到 {OUTPUT_PATH}
- 中間筆記寫 `<產物目錄>/notes-{N}.md`，每段一份（下一段從 checkpoint 的 next 接）

## 每段要做的事

1. 讀上一段 checkpoint 的 next 與 notes-*.md
2. 搜 2–4 個新來源，摘要到本段 notes，更新大綱
3. 若大綱各節都有 ≥ 2 個來源 → 開始寫 / 續寫報告檔
4. 寫 checkpoint（metrics: sources_count, sections_done）

## 停止條件

- `done`：報告寫完且 sources_count ≥ {MIN_SOURCES}
- `blocked`：連續兩段找不到新來源、或主題定義不清無法取捨
- 總時長 {MINUTES} 分鐘

## 不要做

- 不編造來源；找不到就寫「未找到」
- 不改 {OUTPUT_PATH} 以外的檔案
