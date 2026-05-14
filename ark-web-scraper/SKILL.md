---
name: ark-web-scraper
description: |
  產出通用網頁爬蟲 Skill，使用 httpx + BeautifulSoup 抓取任何網頁內容。
  支援 CSS selector 提取、自動帶 User-Agent、403 fallback。
  可搭配 ark-browser-tool 處理需要 JS 渲染的頁面。
  使用此 Skill 當使用者提及網頁抓取、爬蟲、web scraping、
  抓取網頁、擷取網頁內容、或任何需要從網頁取得資料的場景。
---

# ark-web-scraper

產出 `src/skills/internal/web_scraper.py`，通用網頁爬蟲，可獨立運作。

## 觸發條件

- 「網頁抓取」、「爬蟲」、「web scraping」
- 「抓取網頁」、「擷取網頁內容」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `url` | `str` | ✅ | — | 目標網址 |
| `selector` | `str` | ❌ | `None` | CSS selector（提取特定元素） |
| `extract` | `str` | ❌ | `"text"` | 提取方式：`text` / `html` / `attrs` |
| `headers` | `dict` | ❌ | 瀏覽器 UA | 自訂 HTTP headers |
| `max_items` | `int` | ❌ | `20` | 最大提取數量 |

## 產出指引

### Skill 類別

```python
class WebScraperSkill(BaseSkill):
    skill_id = "web_scraper"
    skill_type = SkillType.PYTHON
    description = "通用網頁爬蟲，抓取任何網頁內容"
    version = "1.0.0"
    input_schema = WebScraperParams
```

### execute 方法

- `httpx.AsyncClient` + `follow_redirects=True` + 瀏覽器 User-Agent
- 有 `selector` → `BeautifulSoup.select()` 提取
- 無 `selector` → 回傳整頁文字
- HTTP 4xx → 回傳 `fallback_url` 而非報錯

### 輸出格式

```json
{
  "items": [{"text": "...", "href": "...", "attrs": {...}}],
  "count": 10,
  "url": "https://example.com",
  "status_code": 200
}
```

## 注意事項

- 必須帶瀏覽器 User-Agent headers
- 403 時回傳 fallback_url
- 需要 JS 渲染的頁面搭配 `ark-browser-tool`
