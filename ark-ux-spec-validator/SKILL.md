---
author: paddyyang
name: ark-ux-spec-validator
description: |
  驗證 Telegram Bot UX 實作與 UX Spec 文件的一致性。
  比對訊息格式、InlineKeyboard 佈局、進度更新流程、卡片結構是否符合 spec 定義。
  產出 UX Drift Report（0-100 評分）。
  使用此 Skill 當使用者提及驗證 UX、TG 格式對嗎、Bot 回覆跟 spec 一致嗎、
  訊息格式檢查、InlineKeyboard 驗證、UX drift、或任何需要檢查 Bot UX 品質的場景。
metadata:
  version: "1.0"
  updated: 2026-06-07
---

# ark-ux-spec-validator

驗證 Telegram Bot UX 實作與 Spec 的一致性，產出 UX Drift Report。

## 觸發條件

- 「驗證 UX」、「TG 格式對嗎」、「UX drift」
- 「Bot 回覆跟 spec 一致嗎」、「訊息格式檢查」
- 「InlineKeyboard 驗證」、「卡片結構對嗎」

## 4 個驗證維度

| 維度 | 比對內容 | 評分邏輯 |
|------|---------|---------|
| **訊息格式** | handlers.py 回覆 vs spec 卡片模板 | 100 - (不符項 × 10) |
| **InlineKeyboard** | 按鈕定義 vs spec 按鈕場景表 | covered / total × 100 |
| **進度更新** | edit_message_text 使用點 vs spec 即時更新場景 | 有無 × 分段計分 |
| **視覺化** | 流程圖/狀態卡片 vs spec 定義 | 有無 × 分段計分 |

## 操作流程

1. 讀取目標 UX spec 文件
2. 掃描 `src/bot/handlers.py` 中所有 `reply_text` / `send_message`
3. 提取實際回覆格式，比對 spec 模板
4. 掃描 InlineKeyboard 定義，比對 spec 按鈕場景
5. 檢查 `edit_message_text` 是否覆蓋即時更新場景
6. 產出 `docs/ux-drift-report.md`

## 輸出格式

```
📊 UX Drift Report — Score: {score}/100

| 維度 | 分數 |
|------|------|
| {emoji} 訊息格式 | {n}/100 |
| {emoji} InlineKeyboard | {n}/100 |
| {emoji} 進度更新 | {n}/100 |
| {emoji} 視覺化 | {n}/100 |

主要落差：
1. {drift}
2. ...

💡 修復建議：{方向}
```

## 檢查清單

### 訊息格式
- [ ] Agent 回覆含 avatar + name + 耗時
- [ ] /team 使用表格格式
- [ ] 排程通知含 InlineKeyboard

### InlineKeyboard
- [ ] 任務完成：[👍 接受] [🔄 重做] [💬 追問]
- [ ] Agent 回覆：[💾 存知識庫] [📤 轉發] [❌ 忽略]
- [ ] 排程通知：[✅ 確認] [⏭ 跳過]

### 進度更新
- [ ] 接收後「⏳ 處理中」
- [ ] 轉發時「🔄 已轉發給 X」
- [ ] 完成時替換為最終回覆

### 視覺化
- [ ] /team 顯示狀態表格
- [ ] 任務分派顯示流程樹
