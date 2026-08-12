---
name: ark-news-daily
description: |
  產出科技日報：MD-first 雙軌流程。先產出結構化 Markdown（Content 軌，給 AI/知識庫），
  再渲染 HTML 卡片（View 軌，給人看/發 TG）。
  支援手動輸入或消費 web-scraper 產出的新聞資料，含 news_md_writer 步驟自動寫入 knowledge/raw/。
  使用此 Skill 當使用者提及科技日報、tech daily、產出日報、新聞日報、
  或任何需要將新聞轉化為 MD + HTML 雙軌產出的場景。
metadata:
  author: paddyyang
  schema_version: 1
  status: active
  category: document
  version: "2.0"
  updated: 2026-08-12
  render: html
  outputs:
    - { format: md, audience: ai }
    - { format: html, audience: human, via: ark-html-report }
  depends_on: [ark-html-report, ark-telegram-sender]
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

使用 ark-html-report 的 **midnight** 風格渲染 HTML 卡片：

```html
<div class="card">
  <div class="subtitle-bar">{topic} ｜ <span>{title}</span></div>
  <div class="main">
    <div class="info-box">📋 發生了什麼：{what}</div>
    <div class="info-box">⭐ 為什麼重要：{why}</div>
    <div class="quote-bar">💡 {summary}</div>
  </div>
  <div class="inspiration-bar">{tags}</div>
</div>
```

設計規格：
- 卡片寬度：860px
- 風格：midnight（深色儀表板，數據密集）
- 字型：Noto Sans TC
- 每份日報 3-8 則新聞

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
