---
name: ark-news-daily
description: |
  產出科技日報：MD-first 雙軌流程。先產出結構化 Markdown（Content 軌，給 AI/知識庫），
  再渲染 HTML 卡片（View 軌，給人看/發 TG）。
  支援手動輸入或串接資料來源結果，含 news_md_writer 步驟自動寫入 knowledge/raw/。
  使用此 Skill 當使用者提及科技日報、tech daily、產出日報、新聞日報、
  或任何需要將新聞轉化為 MD + HTML 雙軌產出的場景。
metadata:
  author: paddyyang
  schema_version: 1
  category: document
  version: "2.0"
  updated: 2026-08-12
  outputs:
    - { format: md, audience: ai }
    - { format: html, audience: human }
  render: html
  status: active
  depends_on: [ark-md-report, ark-html-report]
---

# ark-news-daily

科技日報 — MD-first 雙軌產出。

## 核心流程

```
爬蟲 → 解析 → 結構化 → 【save_md】→ 【render_html】→ 發 TG
                            ↓                ↓
                  knowledge/raw/         output/*.html
                  (AI 看/wiki ingest)    (人看/瀏覽器)
```

**原則：MD 是 source of truth，HTML 只是渲染視圖。**

## 觸發條件

- 「科技日報」「tech daily」「產出日報」
- 「新聞日報」「每日新聞」「news daily」
- 「日報模板」「產出日報 HTML」
- 「今日科技新聞」

---

## 步驟一：結構化新聞

將原始新聞轉為結構化 JSON：

```json
[{
  "topic": "AI 焦點",
  "title": "10 字內標題",
  "source": "來源",
  "news_date": "YYYY-MM-DD",
  "what": "100 字內摘要，關鍵詞用 <span class=\"hl\">包裹</span>",
  "why": "80 字內影響分析",
  "summary": "15 字內一句話總結",
  "urgency": "一般|關注|立即",
  "action": "具體行動建議（null 則不顯示）",
  "tags": [{"icon": "emoji", "text": "8 字內"}]
}]
```

## 步驟二：save_md（Content 軌）

將結構化結果寫入 `knowledge/raw/news-daily-{date}.md`。

### MD 格式規範

```markdown
---
title: 科技日報 2026-08-12
type: news-daily
date: 2026-08-12
count: 5
status: raw
---

# 📡 科技日報 — 2026-08-12

> 5 則新聞

## 1. 標題

**分類**：AI 焦點
**來源**：Google Blog
**緊急度**：立即

### 📋 發生了什麼
事件摘要...

### ⭐ 為什麼重要
影響分析...

### 💡 一句話總結
...

### 🎯 行動建議
...

**標籤**：`🤖 AI 模型` `💡 突破`

---
```

此 MD 可被：
- wiki-engine ingest 為知識頁面 source
- 其他 agent 直接讀取分析
- ark-md-report 的日報 CollectorRunner 消費

## 步驟三：render_html（View 軌）

**用 `assets/news-daily.html` 樣板**，替換佔位符即可，不要每次重寫 CSS。
樣板本身帶完整結構範例（事實／指標／決策三種卡片變體、chip 規則、空欄目處理）。

版式是「報頭 + 欄目 + 卡片牆」：日報常態 8~24 則，長列表要一路捲到底才知道
今天有什麼，而讀者多半先掃一遍再挑著讀。

| 項目 | 規格 |
|------|------|
| 佈局 | `grid auto-fill minmax(320px, 1fr)` —— 桌面多欄、手機自動單欄 |
| 主題 | 三態（系統偏好 + `data-theme` 蓋章），深色 token 只定義一份 |
| 字體 | 系統 stack，**不載入網路字體** |
| 外部資源 | **零** |

> ⚠️ **零外部請求是硬性條件**：這份 HTML 走 TG 檔案附件，讀者常在手機上離線開啟。
> 不得加入 CDN、`@import` 網路字體、遠端圖片或任何 `<script src>`。
> 完整規範與交付前檢查指令見 `../ark-html-report/references/offline-mode.md`。

所有由 LLM 或外部來源產生的文字，插入前必須逸出 `&` `<` `>` —— 一個沒逸出的 `<`
會吃掉後面整段內容。

## 步驟四：發送 Telegram

1. **先發文字摘要**（立即處理 + 精選 N 則）
2. **再發 HTML 附件**（完整日報）

文字摘要格式：
```
📡 科技日報 {date}

⚡ 立即處理
• {urgent_title} → {action}

今日精選 N 則，完整分析見附件 👇
```

---

## Workflow 定義

```yaml
steps:
  - id: scrape
    skill: news_scraper
  - id: parse
    skill: news_parser
  - id: structure
    skill: news_structurer
  - id: save_md          # ← MD-first
    skill: news_md_writer
    params:
      articles: "{{ outputs.structured.articles }}"
      output_dir: "knowledge/raw"
  - id: render           # ← View 軌
    skill: news_renderer
    params:
      articles: "{{ outputs.structured.articles }}"
  - id: send_message
    skill: news_telegram_sender
  - id: send_file
    skill: telegram_send_file
    params:
      file_path: "{{ outputs.render.path }}"
```

---

## 與其他 Skill 的關係

| Skill | 角色 |
|-------|------|
| ark-web-scraper | 提供爬蟲能力（上游） |
| ark-md-report | 定義 MD frontmatter 契約 |
| ark-html-report | 定義 HTML 渲染風格（midnight） |
| ark-wiki-engine | 消費 MD 產出，ingest 為知識 |
| ark-telegram-sender | 發送 TG 文字摘要 |
