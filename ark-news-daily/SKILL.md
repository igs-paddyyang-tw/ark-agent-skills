---
author: paddyyang
name: ark-news-daily
description: |
  產出科技日報 HTML 卡片，將新聞素材結構化後套用模板。
  支援手動輸入或串接爬蟲結果，產出可直接瀏覽器開啟的精美日報頁面。
  使用此 Skill 當使用者提及科技日報、tech daily、產出日報、
  新聞日報 HTML、每日新聞、news daily、日報模板、
  或任何需要將新聞轉化為視覺化 HTML 卡片的場景。
metadata:
  version: "1.0"
  updated: 2026-05-26
---

# ark-news-daily

將新聞素材結構化 → 套用 HTML 模板 → 產出科技日報卡片頁面。

## 觸發條件

- 「科技日報」、「tech daily」、「產出日報」
- 「新聞日報 HTML」、「每日新聞」、「news daily」
- 「日報模板」、「產出日報 HTML」

---

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `news_items` | `list[dict]` | ✅ | — | 結構化新聞清單 |
| `date` | `str` | ❌ | 今日日期 | 日報日期（格式：2026.05.26） |
| `output_path` | `str` | ❌ | `output/tech-daily-{date}.html` | 輸出路徑 |

### news_items 格式

```json
[
  {
    "topic": "AI 焦點",
    "title": "Gemini Omni 登場",
    "img_src": "imgs/cover.jpg",
    "source": "Google 官方部落格",
    "news_date": "2026-05-20",
    "what": "事件摘要，<span class=\"hl\">關鍵詞</span>標紅",
    "why": "影響分析",
    "summary": "一句話總結",
    "tags": [
      {"icon": "🎬", "text": "影片製作門檻大降"},
      {"icon": "💬", "text": "自然語言取代剪輯"},
      {"icon": "✨", "text": "電影級效果普及化"}
    ]
  }
]
```

---

## 產出指引

### 步驟 1：結構化新聞

若使用者提供原始新聞文字，用以下 prompt 結構化：

```
你是科技日報編輯。請將以下新聞轉化為 JSON 格式：

{原始新聞}

產出格式：
{
  "topic": "焦點分類（如 AI 焦點、開發工具）",
  "title": "10 字內標題",
  "source": "來源",
  "news_date": "YYYY-MM-DD",
  "what": "100 字內摘要，關鍵詞用 <span class=\"hl\">包裹</span>",
  "why": "80 字內影響分析，關鍵詞標紅",
  "summary": "15 字內一句話總結",
  "tags": [{"icon": "emoji", "text": "8 字內"}] (3 個)
}
```

### 步驟 2：套用 HTML 模板

使用以下卡片結構，每則新聞一張卡片：

```html
<div class="card">
  <div class="header">
    <div class="header-title">{date} 科技日報</div>
  </div>
  <div class="subtitle-bar">{topic} ｜ <span>{title}</span></div>
  <div class="main">
    <div class="left-panel">
      <img class="cover-img" src="{img_src}" alt="{title}">
      <div class="source-info">...</div>
    </div>
    <div class="right-panel">
      <div class="info-box">📋 發生了什麼：{what}</div>
      <div class="info-box">⭐ 為什麼重要：{why}</div>
      <div class="quote-bar">一句話總結：{summary}</div>
    </div>
  </div>
  <div class="inspiration-bar">💡 對團隊的啟發：{tags}</div>
  <div class="footer">{page} / {total} | IGS</div>
</div>
```

### 步驟 3：產出完整 HTML

組合 CSS 樣式 + 多張卡片 → 存為 `tech-daily-{date}.html`。

設計規格：
- 卡片寬度：860px
- 配色：淺藍白色系（#dde8ff / #f0f4ff / #fff）
- 字型：Noto Sans TC 900（標題）/ 700（內文）
- 標紅色：#e03030
- 每份日報 3-5 則新聞

---

## 模板位置

若專案中有 `template-tech-daily.html`，直接使用該模板。
否則依上述規格產出完整 HTML（含內嵌 CSS）。

---

## Workflow 串接

```yaml
- id: scrape
  type: skill
  skill: web_scraper
  params:
    url: "https://technews.tw"
    selector: "article h2 a"
  output: raw_news

- id: structure
  type: skill
  skill: llm_cli
  params:
    prompt: "將以下新聞結構化為科技日報 JSON：{{ outputs.raw_news }}"
    mode: "chat"
    backend: "gemini"
  output: structured

- id: daily
  type: skill
  skill: news_daily
  params:
    news_items: "{{ outputs.structured }}"
  output: html_report
```

---

## Workshop 引導（ai-bot-workshop）

本 Skill 對應 Workshop Step 6：產出科技日報 HTML。

### 前一步

確認已完成 Step 4（`ark-llm-cli`），Gemini CLI 可用。

### 快速測試（不需 LLM）

使用 `structured-example.json` 的 mock 資料直接產出 HTML：

```
用 structured-example.json 的資料產出科技日報 HTML
```

### 完整流程

```
幫我產出今天的科技日報，新聞素材如下：
（貼上新聞內容）
```

### 預期產出

- `output/tech-daily-2026-05-26.html` — 瀏覽器開啟即可看到精美卡片

### 卡關時

- 沒有圖片 → `img_src` 留空或用 placeholder
- HTML 排版跑掉 → 確認 `<span class="hl">` 標籤有正確關閉
- 想改樣式 → 修改 `<style>` 區塊的 CSS 變數
